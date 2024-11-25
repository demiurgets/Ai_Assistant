import json
import re
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.locations import Locations  # Importing the Locations model
import os
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from openai import OpenAI

# Load environment variables
load_dotenv()

# Database configuration
dbname = os.getenv('dbname')
user = os.getenv('user')
password = os.getenv('password')
host = os.getenv('host')
port = os.getenv('port')

assistant_id = os.getenv('ASST_INTERVIEWER')
api_key = os.getenv('API_KEY')

# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
db_session = Session()

# Function to convert location model to dictionary
def location_to_dict(location):
    return {
        "id": location.id,
        "name": location.name,
        "address": location.address,
        "city": location.city,
        "state": location.state,
        "zip": location.zip,
        "phone": location.phone,
    }

# 1. Get all locations
def get_all_locations():
    try:
        locations = db_session.query(Locations).all()
        return [location_to_dict(location) for location in locations]
    except SQLAlchemyError as e:
        print(f"Error fetching all locations: {e}")
        return []

# 2. Get location by ID
def get_location_by_id(location_id):
    try:
        location = db_session.query(Locations).filter(Locations.id == location_id).first()
        return location_to_dict(location) if location else None
    except SQLAlchemyError as e:
        print(f"Error fetching location by ID: {e}")
        return None

# 3. Create a new location
def create_location(location_data):
    try:
        new_location = Locations(
            name=location_data.get("name"),
            address=location_data.get("address"),
            city=location_data.get("city"),
            state=location_data.get("state"),
            zip=location_data.get("zip"),
            phone=location_data.get("phone"),
        )
        db_session.add(new_location)
        db_session.commit()
        update_location_context()
        return location_to_dict(new_location)
    except SQLAlchemyError as e:
        print(f"Error creating location: {e}")
        db_session.rollback()
        return None

# 4. Update location by ID
def update_location(location_id, update_data):
    try:
        location = db_session.query(Locations).filter(Locations.id == location_id).first()
        if not location:
            return None
        for key, value in update_data.items():
            setattr(location, key, value)
        db_session.commit()
        update_location_context()
        return location_to_dict(location)
    except SQLAlchemyError as e:
        print(f"Error updating location: {e}")
        db_session.rollback()
        return None

# 5. Delete location by ID
def delete_location(location_id):
    try:
        location = db_session.query(Locations).filter(Locations.id == location_id).first()
        if not location:
            return False
        db_session.delete(location)
        db_session.commit()
        update_location_context()
        return True
    except SQLAlchemyError as e:
        print(f"Error deleting location: {e}")
        db_session.rollback()
        return False

# 6. Update assistant context with latest location data
def update_location_context():
    try:
        locations = db_session.query(Locations).all()
        locations_data = [
            {
                "id": location.id,
                "name": location.name,
                "address": location.address,
                "city": location.city,
                "state": location.state,
                "zip": location.zip,
                "phone": location.phone,
            }
            for location in locations
        ]

        locations_json = json.dumps(locations_data, indent=4)

        client = OpenAI(api_key=api_key)

        my_assistant = client.beta.assistants.retrieve(assistant_id)

        current_instructions = getattr(my_assistant, "instructions", None)

        print(current_instructions)
        print("current above, updated instructions below: ")
        locations_pattern = r"(Here are the different locations:\s*\[.*?\])"
        updated_instructions = re.sub(locations_pattern, f"Here are the different locations: {locations_json}", current_instructions, flags=re.DOTALL)
        print(updated_instructions)
        my_updated_assistant = client.beta.assistants.update(
            assistant_id,
            instructions=updated_instructions,
        )

        # Dynamically generate the updated locations JSON
        return locations_json

    except SQLAlchemyError as e:
        print(f"Error generating locations JSON: {e}")
        return None

# Generate the dynamic JSON for locations
#locations_json = update_location_context()
