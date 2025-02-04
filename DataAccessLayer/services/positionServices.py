import json
import re

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.positions import Positions
from DataAccessLayer.models.locations_positions import LocationsPositions
from DataAccessLayer.models.locations import Locations
from DataAccessLayer.models.assistants import Assistants
import os
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine
from openai import OpenAI
from sqlalchemy import desc, update
from AI.update_vector_store import generate_all_txt_files, load_to_vector_store
import threading

import openai
import tiktoken
from langchain_core.documents import Document


# Load environment variables
load_dotenv(override=True)

# Database configuration
dbname = os.getenv("dbname")
user = os.getenv("user")
password = os.getenv("password")
host = os.getenv("host")
port = os.getenv("pg_port")

api_key = os.getenv("OPENAI_KEY")

# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)


assistant = db_session.query(Assistants).filter(Assistants.name.like('%greeter%')).first()
assistant_id = assistant.assistant_id

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
        "is_active": position.is_active,
        "working_hours": position.working_hours
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
        "locations": location_data,
        "is_active": position.is_active,
        "working_hours": position.working_hours

    }


# 1. Get all job positions
def get_all_positions():
    try:
        positions = (
            db_session.query(Positions)
            .filter(Positions.is_active == True)
            .order_by(desc(Positions.date_created))
            .all()
        )

        positions_data = []
        for position in positions:
            # Query locations associated with the current position
            locations_positions = (
                db_session.query(
                    LocationsPositions.location_id,
                    Locations.name,
                    Locations.is_active,
                    LocationsPositions.max_openings,
                    LocationsPositions.filled_openings,
                )
                .join(Locations, LocationsPositions.location_id == Locations.id)
                .filter(LocationsPositions.position_id == position.id)
                .all()
            )

            location_data = [
                {
                    "id": lp.location_id,
                    "name": lp.name,
                    "max_openings": lp.max_openings,
                    "filled_openings": lp.filled_openings,
                    "is_active": lp.is_active,
                }
                for lp in locations_positions
            ]

            positions_data.append(
                position_with_locations_to_dict(position, location_data)
            )

        return positions_data

    except SQLAlchemyError as e:
        print(f"Error fetching all positions: {e}")
        db_session.rollback()
        return []
    finally:
        db_session.remove()


# 2. Get job position by ID
def get_position_by_id(position_id):
    try:
        position = (
            db_session.query(Positions).filter(Positions.id == position_id).first()
        )
        if not position:
            return None

        locations_positions = (
            db_session.query(
                LocationsPositions.location_id,
                Locations.name,
                Locations.is_active,
                LocationsPositions.max_openings,
                LocationsPositions.filled_openings,
            )
            .join(Locations, LocationsPositions.location_id == Locations.id)
            .filter(LocationsPositions.position_id == position.id)
            .all()
        )

        location_data = [
            {
                "id": lp.location_id,
                "name": lp.name,
                "max_openings": lp.max_openings,
                "filled_openings": lp.filled_openings,
                "is_active": lp.is_active,
            }
            for lp in locations_positions
        ]

        return position_with_locations_to_dict(position, location_data)

    except SQLAlchemyError as e:
        print(f"Error fetching position by ID: {e}")
        db_session.rollback()
        return None
    finally:
        db_session.remove()


# 3. Create a new job position
def create_position(position_data):
    try:

        formatted_text = formatted_text_for_position_embedding(position_data)
        position_embedding = get_embedding(formatted_text)

        # Create a new position
        new_position = Positions(
            name=position_data.get("name"),
            description=position_data.get("description"),
            key_responsibilities=position_data.get("key_responsibilities"),
            qualifications=position_data.get("qualifications"),
            benefits=position_data.get("benefits"),
            salary_range=position_data.get("salary_range"),
            salary_currency=position_data.get("salary_currency"),
            salary_period=position_data.get("salary_period"),
            job_type=position_data.get("job_type"),
            location_type=position_data.get("location_type"),
            is_active=True,
            position_embedding=position_embedding,
            working_hours = position_data.get("working_hours")
        )

        db_session.add(new_position)
        db_session.commit()  # Commit to generate new_position.id

        locations_data = position_data.get("locations", [])
        if locations_data:
            for loc in locations_data:
                location_position = LocationsPositions(
                    location_id=loc.get("id"),
                    position_id=new_position.id,
                    max_openings=loc.get(
                        "max_openings", 0
                    ),  # Default to 0 if not provided
                    filled_openings=loc.get("filled_openings", 0),
                )
                db_session.add(location_position)

            db_session.commit()
        
        # Run the time-consuming tasks in a separate thread
        def background_task():
            generate_all_txt_files()
            load_to_vector_store()
        
        # Start the background task
        thread = threading.Thread(target=background_task)
        thread.start()  # This runs the task asynchronously
        
        locations_positions = (
            db_session.query(
                LocationsPositions.location_id,
                Locations.name,
                LocationsPositions.max_openings,
                LocationsPositions.filled_openings,
            )
            .join(Locations, LocationsPositions.location_id == Locations.id)
            .filter(LocationsPositions.position_id == new_position.id)
            .all()
        )

        location_data = [
            {
                "id": lp.location_id,
                "name": lp.name,
                "max_openings": lp.max_openings,
                "filled_openings": lp.filled_openings,
            }
            for lp in locations_positions
        ]

        return position_with_locations_to_dict(new_position, location_data)

    except SQLAlchemyError as e:
        print(f"Error creating position: {e}")
        db_session.rollback()
        return None
    finally:
        db_session.remove()


# 4. Update job position by ID
def update_position(position_id, update_data):
    try:
        position = (
            db_session.query(Positions).filter(Positions.id == position_id).first()
        )
        if not position:
            return None  # Return None if the position doesn't exist

        for key, value in update_data.items():
            if key != "locations":  # Skip 'locations' for now
                setattr(position, key, value)

        # Only update 'locations' if provided in update_data
        if "locations" in update_data:
            locations_data = update_data.get("locations", [])

            existing_location_ids = {
                lp.location_id
                for lp in db_session.query(LocationsPositions)
                .filter(LocationsPositions.position_id == position_id)
                .all()
            }

            new_location_ids = {loc.get("id") for loc in locations_data}

            # Delete any existing location relations not in the new list
            for location_id in existing_location_ids:
                if location_id not in new_location_ids:
                    db_session.query(LocationsPositions).filter(
                        LocationsPositions.position_id == position_id,
                        LocationsPositions.location_id == location_id,
                    ).delete()

            # Update existing or add new location relations
            for loc in locations_data:
                location_id = loc.get("id")

                # Check if this location relation already exists
                location_position = (
                    db_session.query(LocationsPositions)
                    .filter(
                        LocationsPositions.position_id == position_id,
                        LocationsPositions.location_id == location_id,
                    )
                    .first()
                )

                if location_position:
                    # Update existing location relation
                    location_position.max_openings = loc.get(
                        "max_openings", location_position.max_openings
                    )
                    location_position.filled_openings = loc.get(
                        "filled_openings", location_position.filled_openings
                    )
                else:
                    # Add new location relation if it doesn't exist
                    new_location_position = LocationsPositions(
                        location_id=location_id,
                        position_id=position_id,
                        max_openings=loc.get("max_openings", 0),
                        filled_openings=loc.get("filled_openings", 0),
                    )
                    db_session.add(new_location_position)

        embedding_fields = {
            "name",
            "description",
            "key_responsibilities",
            "qualifications",
        }

        # If any of the fields in 'embedding_fields' were updated, set the variable to True
        rebuild_embedding = any(field in update_data for field in embedding_fields)

        if rebuild_embedding:
            # Prepare text and rebuild the embedding
            updated_text = formatted_text_for_position_embedding(
                {
                    "name": position.name,
                    "description": position.description,
                    "key_responsibilities": position.key_responsibilities,
                    "qualifications": position.qualifications,
                }
            )

        # Rebuild position embedding
        position.position_embedding = get_embedding(updated_text)

        db_session.commit()
        
        # Run the time-consuming tasks in a separate thread
        def background_task():
            generate_all_txt_files()
            load_to_vector_store()
        
        # Start the background task
        thread = threading.Thread(target=background_task)
        thread.start()  # This runs the task asynchronously

        updated_locations_positions = (
            db_session.query(
                LocationsPositions.location_id,
                Locations.name,
                LocationsPositions.max_openings,
                LocationsPositions.filled_openings,
            )
            .join(Locations, LocationsPositions.location_id == Locations.id)
            .filter(LocationsPositions.position_id == position_id)
            .all()
        )

        location_data = [
            {
                "id": lp.location_id,
                "name": lp.name,
                "max_openings": lp.max_openings,
                "filled_openings": lp.filled_openings,
            }
            for lp in updated_locations_positions
        ]

        return position_with_locations_to_dict(
            position, location_data
        )  # Return updated position with locations

    except SQLAlchemyError as e:
        print(f"Error updating position: {e}")
        db_session.rollback()
        return None
    finally:
        db_session.remove()


# 5. Delete job position by ID
# def delete_position(position_id):
#     try:
#         position = db_session.query(Positions).filter(Positions.id == position_id).first()
#         if not position:
#             return False
#         db_session.delete(position)
#         db_session.commit()
#         return True
#     except SQLAlchemyError as e:
#         print(f"Error deleting position: {e}")
#         db_session.rollback()
#         return False
#     finally:
#         db_session.remove()


def delete_position(position_id):
    try:
        # Buscar la posición en la base de datos
        position = (
            db_session.query(Positions).filter(Positions.id == position_id).first()
        )
        if not position:
            return False

        position.is_active = False
        db_session.commit()
        
        # Run the time-consuming tasks in a separate thread
        def background_task():
            generate_all_txt_files()
            load_to_vector_store()
        
        # Start the background task
        thread = threading.Thread(target=background_task)
        thread.start()  # This runs the task asynchronously  
        
        
        return True
    except SQLAlchemyError as e:
        print(f"Error updating is_active for position: {e}")
        db_session.rollback()
        return False
    finally:
        db_session.remove()  # Cleanup del session


# def get_positions_by_location(location_id):
#     try:
#         # Query positions by joining LocationsPositions and Positions tables
#         positions = (
#             db_session.query(Positions)
#             .join(LocationsPositions, Positions.id == LocationsPositions.position_id)
#             .filter(LocationsPositions.location_id == location_id)
#             .all()
#         )

#         # Convert each position to a dictionary using the existing position_to_dict function
#         return [position_to_dict(position) for position in positions]

#     except SQLAlchemyError as e:
#         print(f"Error fetching positions by location ID {location_id}: {e}")
#         db_session.rollback()
#         return []
#     finally:
#         db_session.remove()

# def get_positions_by_location(location_id):
#     try:
#         # Query positions by joining LocationsPositions and Positions tables, filtering active positions
#         positions = (
#             db_session.query(Positions)
#             .join(LocationsPositions, Positions.id == LocationsPositions.position_id)
#             .filter(LocationsPositions.location_id == location_id)
#             .filter(Positions.is_active == True)  # Filtrar solo posiciones activas
#             .all()
#         )

#         # Convert each position to a dictionary using the existing position_to_dict function
#         return [position_to_dict(position) for position in positions]

#     except SQLAlchemyError as e:
#         print(f"Error fetching positions by location ID {location_id}: {e}")
#         db_session.rollback()
#         return []
#     finally:
#         db_session.remove()


def get_positions_by_location(location_id):
    try:
        # Query positions by joining LocationsPositions and Positions tables, filtering active positions
        positions = (
            db_session.query(Positions)
            .join(LocationsPositions, Positions.id == LocationsPositions.position_id)
            .filter(LocationsPositions.location_id == location_id)
            .filter(Positions.is_active == True)  # Filtrar solo posiciones activas
            .filter(LocationsPositions.max_openings > 0)  # Filtrar por max_openings > 0
            .filter(
                LocationsPositions.filled_openings < LocationsPositions.max_openings
            )  # Filtrar por filled_openings < max_openings
            .all()
        )

        # Convert each position to a dictionary using the existing position_to_dict function
        return [position_to_dict(position) for position in positions]

    except SQLAlchemyError as e:
        print(f"Error fetching positions by location ID {location_id}: {e}")
        db_session.rollback()
        return []
    finally:
        db_session.remove()



# def update_position_context():
#     try:
#         # Retrieve current assistant instructions
#         client = OpenAI(api_key=api_key)
#         my_assistant = client.beta.assistants.retrieve(assistant_id)
#         current_instructions = getattr(my_assistant, "instructions", None)
        
#         # Check if the phrase exists
#         if "Here are the different positions:" not in current_instructions:
#             print("Positions not in context, not updating...")
#             return None

#         # Query positions with their associated location counts
#         positions_with_locations = (
#             db_session.query(
#                 Positions,
#                 func.count(LocationsPositions.location_id).label("location_count")
#             )
#             .join(LocationsPositions, Positions.id == LocationsPositions.position_id)
#             .join(Locations, Locations.id == LocationsPositions.location_id)
#             .filter(Positions.is_active == True)  # Include only active positions
#             .group_by(Positions.id)
#             .having(func.count(LocationsPositions.location_id) > 0)  # Only include positions with associated locations
#             .all()
#         )

#         # Create the JSON structure
#         positions_data = [
#             {
#                 "id": position.id,
#                 "title": position.name,
#                 "department": position.description,
#                 "qualifications": position.qualifications,
#                 "job_type": position.job_type,
#                 "location_count": location_count,  # Count of locations
#             }
#             for position, location_count in positions_with_locations
#         ]

#         # Convert the JSON to a string and escape backslashes
#         positions_json = json.dumps(positions_data, indent=4).replace("\\", "\\\\")
#         print("Generated positions JSON:", positions_json)

#         # Update only the relevant part of the instructions
#         positions_pattern = r"(Here are the different positions:\s*).*"
#         updated_instructions = re.sub(
#             positions_pattern,
#             f"Here are the different positions: {positions_json}",
#             current_instructions,
#             flags=re.DOTALL
#         )

#         # Log updated instructions for debugging
#         print("Updated instructions:", updated_instructions)

#         # Update the assistant with the new instructions
#         my_updated_assistant = client.beta.assistants.update(
#             assistant_id,
#             instructions=updated_instructions,
#         )

#         return positions_json  # Return the updated JSON for debugging/logging

#     except SQLAlchemyError as e:
#         print(f"Database error: {e}")
#         db_session.rollback()
#         return None
#     except Exception as e:
#         print(f"Error updating position context: {e}")
#         return None
#     finally:
#         db_session.remove()

##### Logic for position embeddings #####

openai.api_key = os.getenv("OPENAI_KEY")

tokenizer = tiktoken.encoding_for_model("text-embedding-3-small")


def get_embedding(text, model="text-embedding-3-small"):
    # Clean up text, calculate number of tokens and generate embedding
    text = text.replace("\n", " ")
    num_tokens = len(tokenizer.encode(text))
    print(f"Number of tokens for text: {num_tokens}")

    response = openai.embeddings.create(input=[text], model=model)
    return response.data[0].embedding


def formatted_text_for_position_embedding(position):
    # Use default values for potentially null fields
    name = position.get("name") or "No name provided"
    description = position.get("description") or "No description found"
    key_responsibilities = position.get("key_responsibilities") or []
    qualifications = position.get("qualifications") or []

    formatted_text = f"Name: {name} - Description: {description}"

    # Add key responsibilities and qualifications if provided
    if key_responsibilities:
        formatted_text += f" - Key Responsibilities: {', '.join(key_responsibilities)}"
    if qualifications:
        formatted_text += f" - Qualifications: {', '.join(qualifications)}"

    return formatted_text


def initialize_position_embeddings():
    try:
        embeddings = {}
        position_dicts = get_all_positions()
        for pos in position_dicts:
            # Format the text and print
            formatted_text = formatted_text_for_position_embedding(pos)
            print(f"Prepared Text for Position ID {pos['id']}: {formatted_text}")

            # Add the embedding to the dict
            embeddings[pos["id"]] = get_embedding(formatted_text)

        with Session(engine) as session:
            for position_id, embedding in embeddings.items():
                # Update the position_embedding column for the given position ID
                session.execute(
                    update(Positions)
                    .where(Positions.id == position_id)
                    .values(position_embedding=embedding)
                )

            session.commit()

    except SQLAlchemyError as e:
        print(f"Error initializing embeddings: {e}")
        db_session.rollback()
        return []
    finally:
        db_session.remove()


# It creates the embeddings for all the positions in the table and updates the db
#initialize_position_embeddings()


# Generate the dynamic JSON for job positions
#positions_json = update_position_context()
