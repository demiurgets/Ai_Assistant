from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.assistants import Assistants
from DataAccessLayer.models.candidates import Candidates
from DataAccessLayer.models.positions import Positions
from DataAccessLayer.models.locations import Locations
from DataAccessLayer.models.locations_positions import LocationsPositions
from DataAccessLayer.services.positionServices import (update_position_context, get_positions_by_location)
from DataAccessLayer.services.locationsServices import (update_location_context, get_locations_by_position)



import os
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine
from sqlalchemy import func
import json
from flask import Flask, request, jsonify
from AI.openai_utils import OpenAIUtility
from openai import OpenAI
from datetime import datetime
import logging
from sqlalchemy import desc
import re


# Load environment variables
load_dotenv()

# Database configuration
dbname = os.getenv('dbname', 'qonda')
user = os.getenv('user', 'postgres')
password = os.getenv('password', 'Not24get!')
host = os.getenv('host', 'localhost')
port = os.getenv('pg_port', '5432')

assistant_id = os.getenv("ASST_INTERVIEWER")
api_key = os.getenv("OPENAI_KEY")

# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)

SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)

logging.basicConfig(level=logging.INFO)

def assistant_get_positions(thread_id, text, asstId):
    numbers = re.findall(r'\d+', text)
    location_id = int(numbers[0]) if numbers else None
      # If a valid location_id is found, retrieve positions for that location
    response = ""
    if location_id is not None:
        positions = get_positions_by_location(location_id)
        positions_json = json.dumps(
            positions,
            default=lambda obj: obj.isoformat() if isinstance(obj, datetime) else str(obj)  # Handle datetime serialization
        )
        print("Queried positions!")
        query = (
            "Here are all the positions for the location, please present each with a short summary to the user and remember the position ID of their choice: " + positions_json
        )
        openAiUtils = OpenAIUtility()

        
        response = openAiUtils.send_to_ai(query, thread_id, asstId)
        return response
    else:
        return response


def assistant_get_locations(thread_id, text, asstId):
    numbers = re.findall(r'\d+', text)
    position_id = int(numbers[0]) if numbers else None
      # If a valid location_id is found, retrieve positions for that location
    response = ""
    if position_id is not None:
        locations = get_locations_by_position(position_id)
        locations_json = json.dumps(
            locations,
            default=lambda obj: obj.isoformat() if isinstance(obj, datetime) else str(obj)  # Handle datetime serialization
        )
        print("Queried locations!")
        query = (
            "Here are all the locations for the position, please ask the user where they live and send a short summary of near by locations and remember the location ID of their choice. if they want to browse different positions just resend the trigger: " + locations_json
        )
        openAiUtils = OpenAIUtility()

        
        response = openAiUtils.send_to_ai(query, thread_id, asstId)
        return response
    else:
        return response

    

def getCvAnalyzer():
    return db_session.query(Assistants).filter(Assistants.name.like('%Cv_analyzer%')).first().assistant_id

#will change whether the greeter convo starts with locations and queries position, or vice versa
def toggle_instructions(text: str) -> str:
    replacements = {
        "location": "position",
        "locations": "positions",
        "position": "location",
        "positions": "locations",
        "city and state": "professional interests",
        "professional interests": "city and state"
    }
    pattern = re.compile("|".join(re.escape(k) for k in replacements))
    return pattern.sub(lambda m: replacements[m.group(0)], text)

def toggle_greeter_direction():
    try:
        client = OpenAI(api_key=api_key)
        
        assistant = db_session.query(Assistants).filter(
            Assistants.name.like('%greeter%')
        ).first()
        assistant_id = assistant.assistant_id
        my_assistant = client.beta.assistants.retrieve(assistant_id)
        current_instructions = getattr(my_assistant, "instructions", None)

        updated_instructions = toggle_instructions(current_instructions)

        print("Updated instructions:")

        my_updated_assistant = client.beta.assistants.update(
            assistant_id, instructions=updated_instructions
        )
        update_position_context()
        update_location_context()

        return updated_instructions

    except Exception as e:
        print(f"Error toggling greeter direction: {e}")
        return None