import json
import re

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.positions import Positions
import os
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from openai import OpenAI


# Load environment variables
load_dotenv(override=True)

# Database configuration
dbname = os.getenv('dbname')
user = os.getenv('user')
password = os.getenv('password')
host = os.getenv('host')
port = os.getenv('pg_port')

assistant_id = os.getenv('ASST_INTERVIEWER')
api_key = os.getenv('API_KEY')

# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
db_session = Session()

# Function to convert job position model to dictionary
def position_to_dict(position):
    return {
        "id": position.id,
        "name": position.name,
        "description": position.description,
        "location_id": position.location_id,
        "filled_openings": position.filled_openings,
        "max_openings": position.max_openings,
        "created_date": position.date_created,
        "updated_date": position.date_updated, 
    }

# 1. Get all job positions
def get_all_positions():
    try:
        positions = db_session.query(Positions).all()
        return [position_to_dict(position) for position in positions]
    except SQLAlchemyError as e:
        print(f"Error fetching all positions: {e}")
        return []

# 2. Get job position by ID
def get_position_by_id(position_id):
    try:
        position = db_session.query(Positions).filter(Positions.id == position_id).first()
        return position_to_dict(position) if position else None
    except SQLAlchemyError as e:
        print(f"Error fetching position by ID: {e}")
        return None

# 3. Create a new job position
def create_position(position_data):
    try:
        new_position = Positions(
            name=position_data.get("name"),
            description=position_data.get("description"),
            location_id=position_data.get("location_id"),
            openings=position_data.get("openings"),
            max_openings=position_data.get("max_openings"),
        )
        db_session.add(new_position)
        db_session.commit()
        return position_to_dict(new_position)
    except SQLAlchemyError as e:
        print(f"Error creating position: {e}")
        db_session.rollback()
        return None

# 4. Update job position by ID
def update_position(position_id, update_data):
    try:
        position = db_session.query(Positions).filter(Positions.id == position_id).first()
        if not position:
            return None
        for key, value in update_data.items():
            setattr(position, key, value)
        db_session.commit()
        return position_to_dict(position)
    except SQLAlchemyError as e:
        print(f"Error updating position: {e}")
        db_session.rollback()
        return None

# 5. Delete job position by ID
def delete_position(position_id):
    try:
        position = db_session.query(Positions).filter(Positions.id == position_id).first()
        if not position:
            return False
        db_session.delete(position)
        db_session.commit()
        return True
    except SQLAlchemyError as e:
        print(f"Error deleting position: {e}")
        db_session.rollback()
        return False

def get_positions_by_location(location_id):
    try:
        # Query positions based on location_id
        positions = db_session.query(Positions).filter(Positions.location_id == location_id).all()
        
        # Convert each position to a dictionary using the existing position_to_dict function
        return [position_to_dict(position) for position in positions]
    
    except SQLAlchemyError as e:
        print(f"Error fetching positions by location ID {location_id}: {e}")
        return []


def update_position_context():
    try:
        positions = db_session.query(Positions).all()
        positions_data = [
            {
                "id": position.id,
                "name": position.name,
                "description": position.description,
                "filled_openings": position.filled_openings,
                "max_openings": position.max_openings,
            }
            for position in positions
        ]
        
        positions_json = json.dumps(positions_data, indent=4).replace("\\", "\\\\")
        
        client = OpenAI(api_key=api_key)

        my_assistant = client.beta.assistants.retrieve(assistant_id)

        current_instructions = getattr(my_assistant, "instructions", None)

        print(current_instructions)
        print("current above, updated instructions below: ")
        positions_pattern = r"(Here are the different positions:\s*\[.*?\])"

        escaped_positions_json = positions_json.replace("\\", "\\\\")

        updated_instructions = re.sub(
            positions_pattern, 
            f"Here are the different positions: {escaped_positions_json}", 
            current_instructions, 
            flags=re.DOTALL
        )

        updated_instructions = re.sub(positions_pattern, f"Here are the different positions: {positions_json}", current_instructions, flags=re.DOTALL)
        print(updated_instructions)
        my_updated_assistant = client.beta.assistants.update(
            assistant_id,
            instructions=updated_instructions,
            )

        # Dynamically generate the updated positions JSON
        return positions_json

    except SQLAlchemyError as e:
        print(f"Error generating positions JSON: {e}")
        return None

# Generate the dynamic JSON for job positions
#positions_json = update_position_context()
