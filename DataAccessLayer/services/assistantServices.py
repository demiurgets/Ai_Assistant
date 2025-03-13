from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.assistants import Assistants
from DataAccessLayer.models.candidates import Candidates
from DataAccessLayer.models.positions import Positions
from DataAccessLayer.models.locations import Locations
from DataAccessLayer.models.locations_positions import LocationsPositions
from DataAccessLayer.services.positionServices import (get_positions_by_location)
from DataAccessLayer.services.locationsServices import (get_locations_by_position, get_locations_by_city_state)



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


def getCvAnalyzer():
    try:
        return db_session.query(Assistants).filter(Assistants.name.like('%Cv_analyzer%')).first().assistant_id
    except SQLAlchemyError as e:
        db_session.rollback()
        logging.error(f"Error cv analyzer from db: {e}")
        return None
    finally:
        db_session.remove()
