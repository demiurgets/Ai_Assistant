import json
import re

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.positions import Positions
from DataAccessLayer.models.locations_positions import LocationsPositions
from DataAccessLayer.models.locations import Locations
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
        "key_responsibilities": position.key_responsibilities,
        "qualifications": position.qualifications,
        "benefits": position.benefits,
        "salary_range": position.salary_range,
        "salary_currency": position.salary_currency,
        "salary_period": position.salary_period,
        "job_type": position.job_type,
        "location_type": position.location_type,
        "created_date": position.date_created,
        "updated_date": position.date_updated, 
    }
    
def position_with_locations_to_dict(position, location_data):
    return {
        "id": position.id,
        "name": position.name,
        "description": position.description,
        "key_responsibilities": position.key_responsibilities,
        "qualifications": position.qualifications,
        "benefits": position.benefits,
        "salary_range": position.salary_range,
        "salary_currency": position.salary_currency,
        "salary_period": position.salary_period,
        "job_type": position.job_type,
        "location_type": position.location_type,
        "created_date": position.date_created,
        "updated_date": position.date_updated,
        "locations": location_data
    }


# 1. Get all job positions
def get_all_positions():
    try:
        positions = db_session.query(Positions).all()
        
        positions_data = []
        for position in positions:
            # Query location IDs associated with the current position
            location_ids = db_session.query(
                LocationsPositions.location_id
            ).filter(
                LocationsPositions.position_id == position.id
            ).all()
            
            location_data = [loc_id[0] for loc_id in location_ids]
            
            positions_data.append(position_with_locations_to_dict(position, location_data))
        
        return positions_data
    
    except SQLAlchemyError as e:
        print(f"Error fetching all positions: {e}")
        return []


# 2. Get job position by ID
def get_position_by_id(position_id):
    try:
        position = db_session.query(Positions).filter(Positions.id == position_id).first()
        if not position:
            return None
        
        locations_positions = db_session.query(
            LocationsPositions.location_id,
            Locations.name,
            LocationsPositions.max_openings,
            LocationsPositions.filled_openings
        ).join(Locations, LocationsPositions.location_id == Locations.id).filter(LocationsPositions.position_id == position.id).all()
        
        location_data = [{"id": lp.location_id, "name": lp.name, "max_openings": lp.max_openings, "filled_openings": lp.filled_openings} for lp in locations_positions]

        return position_with_locations_to_dict(position, location_data)
    
    except SQLAlchemyError as e:
        print(f"Error fetching position by ID: {e}")
        return None
    
# 3. Create a new job position
def create_position(position_data):
    try:
        # Create a new position
        new_position = Positions(
            name=position_data.get("name"),
            description=position_data.get("description"),
        )
        db_session.add(new_position)
        db_session.commit()  # Commit to generate new_position.id
        
        locations_data = position_data.get("locations", [])
        if locations_data:
            for loc in locations_data:
                location_position = LocationsPositions(
                    location_id=loc.get("location_id"),
                    position_id=new_position.id,
                    max_openings=loc.get("max_openings", 0),  # Default to 0 if not provided
                    filled_openings=loc.get("filled_openings", 0)
                )
                db_session.add(location_position)
        
            db_session.commit()
            
        locations_positions = db_session.query(
            LocationsPositions.location_id,
            Locations.name,
            LocationsPositions.max_openings,
            LocationsPositions.filled_openings
        ).join(Locations, LocationsPositions.location_id == Locations.id).filter(LocationsPositions.position_id == new_position.id).all()
            
        location_data = [{"id": lp.location_id, "name": lp.name, "max_openings": lp.max_openings, "filled_openings": lp.filled_openings} for lp in locations_positions]
        
        return position_with_locations_to_dict(new_position, location_data)
    except SQLAlchemyError as e:
        print(f"Error creating position: {e}")
        db_session.rollback()
        return None


# 4. Update job position by ID
def update_position(position_id, update_data):
    try:
        position = db_session.query(Positions).filter(Positions.id == position_id).first()
        if not position:
            return None  # Return None if the position doesn't exist

        for key, value in update_data.items():
            if key != 'locations':  # Skip 'locations' for now
                setattr(position, key, value)

        # Only update 'locations' if provided in update_data
        if 'locations' in update_data:
            locations_data = update_data.get("locations", [])

            # Get existing location relations for this position
            existing_location_ids = {
                lp.location_id for lp in db_session.query(LocationsPositions).filter(LocationsPositions.position_id == position_id).all()
            }

            # Extract new location IDs from the update data
            new_location_ids = {loc.get("location_id") for loc in locations_data}

            # Delete any existing location relations not in the new list
            for location_id in existing_location_ids:
                if location_id not in new_location_ids:
                    db_session.query(LocationsPositions).filter(
                        LocationsPositions.position_id == position_id,
                        LocationsPositions.location_id == location_id
                    ).delete()

            # Update existing or add new location relations
            for loc in locations_data:
                location_id = loc.get("location_id")

                # Check if this location relation already exists
                location_position = db_session.query(LocationsPositions).filter(
                    LocationsPositions.position_id == position_id,
                    LocationsPositions.location_id == location_id
                ).first()

                if location_position:
                    # Update existing location relation
                    location_position.max_openings = loc.get("max_openings", location_position.max_openings)
                    location_position.filled_openings = loc.get("filled_openings", location_position.filled_openings)
                else:
                    # Add new location relation if it doesn't exist
                    new_location_position = LocationsPositions(
                        location_id=location_id,
                        position_id=position_id,
                        max_openings=loc.get("max_openings", 0),
                        filled_openings=loc.get("filled_openings", 0)
                    )
                    db_session.add(new_location_position)

        db_session.commit()  

        updated_locations_positions = db_session.query(
            LocationsPositions.location_id,
            Locations.name,
            LocationsPositions.max_openings,
            LocationsPositions.filled_openings
        ).join(Locations, LocationsPositions.location_id == Locations.id).filter(LocationsPositions.position_id == position_id).all()

        location_data = [{"id": lp.location_id, "name": lp.name, "max_openings": lp.max_openings, "filled_openings": lp.filled_openings} for lp in updated_locations_positions]

        return position_with_locations_to_dict(position, location_data)  # Return updated position with locations

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
        # Query positions by joining LocationsPositions and Positions tables
        positions = (
            db_session.query(Positions)
            .join(LocationsPositions, Positions.id == LocationsPositions.position_id)
            .filter(LocationsPositions.location_id == location_id)
            .all()
        )
        
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
