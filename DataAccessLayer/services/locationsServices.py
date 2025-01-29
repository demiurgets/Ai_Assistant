import json
import re
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.locations import Locations  # Importing the Locations model
from DataAccessLayer.models.positions import Positions  # Importing the Positions model
from DataAccessLayer.models.locations_positions import LocationsPositions
from DataAccessLayer.models.assistants import Assistants



import os
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker, scoped_session
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

api_key = os.getenv('OPENAI_KEY')

# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)

assistant = db_session.query(Assistants).filter(Assistants.name.like('%greeter%')).first()
assistant_id = assistant.assistant_id

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
        "is_active": location.is_active
    }
    
def location_with_positions_to_dict(location, position_data):
        return {
        "id": location.id,
        "name": location.name,
        "address": location.address,
        "city": location.city,
        "state": location.state,
        "zip": location.zip,
        "phone": location.phone,
        "positions": position_data,
        "is_active": location.is_active

    }

# 1. Get all locations
def get_all_locations():
    try:
        locations = db_session.query(Locations).filter(Locations.is_active == True).all()
        
        locations_data = []
        for location in locations:
            # Query positions associated with the current location, including names and openings
            positions_locations = db_session.query(
                LocationsPositions.position_id,
                Positions.name,
                Positions.is_active,
                LocationsPositions.max_openings,
                LocationsPositions.filled_openings
            ).join(Positions, LocationsPositions.position_id == Positions.id).filter(
                LocationsPositions.location_id == location.id
            ).all()
            
            position_data = [
                {
                    "id": pl.position_id,
                    "name": pl.name,
                    "max_openings": pl.max_openings,
                    "filled_openings": pl.filled_openings,
                    "is_active": pl.is_active
                } for pl in positions_locations
            ]
            
            # Append location data with associated positions
            locations_data.append(location_with_positions_to_dict(location, position_data))
        
        return locations_data
    
    except SQLAlchemyError as e:
        db_session.rollback()  # Rollback en caso de error
        print(f"Error fetching all locations: {e}")
        return []
    finally:
        db_session.remove()  # Asegurar limpieza de la sesión




# 2. Get location by ID
def get_location_by_id(location_id):
    try:
        # Fetch the location based on the provided ID
        location = db_session.query(Locations).filter(Locations.id == location_id).first()
        if not location:
            return None
        
        # Fetch positions associated with the location
        location_positions = db_session.query(
            LocationsPositions.position_id,
            Positions.name,
            Positions.is_active,
            LocationsPositions.max_openings,
            LocationsPositions.filled_openings
        ).join(Positions, LocationsPositions.position_id == Positions.id).filter(LocationsPositions.location_id == location_id).all()
        
        # Structure position data into a list of dictionaries
        position_data = [{"id": lp.position_id, "name": lp.name, "max_openings": lp.max_openings, "filled_openings": lp.filled_openings, "is_active": lp.is_active} for lp in location_positions]

        # Combine location and position data into the final dictionary
        return location_with_positions_to_dict(location, position_data)
    
    except SQLAlchemyError as e:
        db_session.rollback()  # Rollback in case of an error
        print(f"Error fetching location by ID: {e}")
        return None
    finally:
        db_session.remove()  # Ensure session cleanup



# 3. Create a new location
def create_location(location_data):
    try:
        # Create a new location
        new_location = Locations(
            name=location_data.get("name"),
            address=location_data.get("address"),
            city=location_data.get("city"),
            state=location_data.get("state"),
            zip=location_data.get("zip"),
            phone=location_data.get("phone"),
            is_active=True
        )
        db_session.add(new_location)
        db_session.commit()  
        
        # Handle associated positions if provided
        positions_data = location_data.get("positions", [])
        if positions_data:
            for pos in positions_data:
                location_position = LocationsPositions(
                    location_id=new_location.id,
                    position_id=pos.get("id"), 
                    max_openings=pos.get("max_openings", 0),  # Default to 0 if not provided
                    filled_openings=pos.get("filled_openings", 0)
                )
                db_session.add(location_position)
        
            db_session.commit()
        
        location_positions = db_session.query(
            LocationsPositions.position_id,
            Positions.name,
            LocationsPositions.max_openings,
            LocationsPositions.filled_openings
        ).join(Positions, LocationsPositions.position_id == Positions.id).filter(LocationsPositions.location_id == new_location.id).all()
        
        position_data = [
            {
                "id": lp.position_id,  
                "name": lp.name, 
                "max_openings": lp.max_openings, 
                "filled_openings": lp.filled_openings
            } 
            for lp in location_positions
        ]
        update_location_context()
        return location_with_positions_to_dict(new_location, position_data)
    
    except SQLAlchemyError as e:
        print(f"Error creating location: {e}")
        db_session.rollback()  # Rollback in case of an error
        return None
    finally:
        db_session.remove()  # Ensure session cleanup



# 4. Update location by ID
def update_location(location_id, update_data):
    try:
        location = db_session.query(Locations).filter(Locations.id == location_id).first()
        if not location:
            return None  # Return None if the location doesn't exist

        for key, value in update_data.items():
            if key != 'positions':  # Skip 'positions' for now
                setattr(location, key, value)

        # Only update 'positions' if provided in update_data
        if 'positions' in update_data:
            positions_data = update_data.get("positions", [])

            existing_position_ids = {
                lp.position_id for lp in db_session.query(LocationsPositions).filter(LocationsPositions.location_id == location_id).all()
            }

            new_position_ids = {pos.get("id") for pos in positions_data}

            # Delete any existing position relations not in the new list
            for position_id in existing_position_ids:
                if position_id not in new_position_ids:
                    db_session.query(LocationsPositions).filter(
                        LocationsPositions.location_id == location_id,
                        LocationsPositions.position_id == position_id
                    ).delete()

            # Update existing or add new position relations
            for pos in positions_data:
                position_id = pos.get("id")

                # Check if this position relation already exists
                location_position = db_session.query(LocationsPositions).filter(
                    LocationsPositions.location_id == location_id,
                    LocationsPositions.position_id == position_id
                ).first()

                if location_position:
                    # Update existing position relation
                    location_position.max_openings = pos.get("max_openings", location_position.max_openings)
                    location_position.filled_openings = pos.get("filled_openings", location_position.filled_openings)
                else:
                    # Add new position relation if it doesn't exist
                    new_location_position = LocationsPositions(
                        location_id=location_id,
                        position_id=position_id,
                        max_openings=pos.get("max_openings", 0),
                        filled_openings=pos.get("filled_openings", 0)
                    )
                    db_session.add(new_location_position)

        db_session.commit()  

        updated_locations_positions = db_session.query(
            LocationsPositions.position_id,
            Positions.name,
            LocationsPositions.max_openings,
            LocationsPositions.filled_openings
        ).join(Positions, LocationsPositions.position_id == Positions.id).filter(LocationsPositions.location_id == location_id).all()

        position_data = [{"id": lp.position_id, "name": lp.name, "max_openings": lp.max_openings, "filled_openings": lp.filled_openings} for lp in updated_locations_positions]
        update_location_context()
        return location_with_positions_to_dict(location, position_data)  # Return updated location with positions

    except SQLAlchemyError as e:
        print(f"Error updating location: {e}")
        db_session.rollback()
        return None
    finally:
        db_session.remove()  # Ensure session cleanup


# 5. Delete location by ID
# def delete_location(location_id):
#     try:
#         location = db_session.query(Locations).filter(Locations.id == location_id).first()
#         if not location:
#             return False
#         db_session.delete(location)
#         db_session.commit()
#         update_location_context()
#         return True
#     except SQLAlchemyError as e:
#         print(f"Error deleting location: {e}")
#         db_session.rollback()
#         return False
#     finally:
#         db_session.remove()  # Ensure session cleanup

def delete_location(location_id):
    try:
        location = db_session.query(Locations).filter(Locations.id == location_id).first()
        if not location:
            return False
        
        location.is_active = False
        db_session.commit()
        
        update_location_context()
        return True
    except SQLAlchemyError as e:
        print(f"Error updating is_active for location: {e}")
        db_session.rollback()
        return False
    finally:
        db_session.remove()  # Cleanup del session


# def update_location_context():
#     try:
#         # Query locations with their position counts using the LocationsPositions table
#         locations_with_positions = (
#             db_session.query(
#                 Locations,
#                 func.count(LocationsPositions.position_id).label("position_count")
#             )
#             .join(LocationsPositions, Locations.id == LocationsPositions.location_id)  
#             .join(Positions, Positions.id == LocationsPositions.position_id)  
#             .group_by(Locations.id)
#             .having(func.count(LocationsPositions.position_id) > 0)  # Only include locations with associated positions
#             .all()
#         )

#         # Create the JSON structure
#         locations_data = [
#             {
#                 "id": location.id,
#                 "name": location.name,
#                 "address": location.address,
#                 "city": location.city,
#                 "state": location.state,
#                 "zip": location.zip,
#                 "phone": location.phone,
#                 "position_count": position_count,  # count of positions
#             }
#             for location, position_count in locations_with_positions
#         ]

#         locations_json = json.dumps(locations_data, indent=4).replace("\\", "\\\\")

#         print(locations_json)
#         # Interact with OpenAI API to update assistant context
#         client = OpenAI(api_key=api_key)
#         my_assistant = client.beta.assistants.retrieve(assistant_id)
#         current_instructions = getattr(my_assistant, "instructions", None)

       
#         print(current_instructions)
#         print("current above, updated instructions below: ")
#         locations_pattern = r"(Here are the different locations:\s*\[.*?\])"
#         updated_instructions = re.sub(locations_pattern, f"Here are the different locations: {locations_json}", current_instructions, flags=re.DOTALL)
        

#         # Print updated instructions for debugging
#         print(updated_instructions)

#         # Update the assistant (commented out for now)
#         my_updated_assistant = client.beta.assistants.update(
#             assistant_id,
#             instructions=updated_instructions,
#         )

#         return locations_json  # Return the updated JSON for debugging/logging

#     except SQLAlchemyError as e:
#         print(f"Error updating location context: {e}")
#         db_session.rollback()
#         return None
#     finally:
#         db_session.remove()

def get_locations_by_position(position_id):
    try:
        locations = (
            db_session.query(Locations)
            .join(LocationsPositions, Locations.id == LocationsPositions.location_id)
            .join(Positions, Positions.id == LocationsPositions.position_id)
            .filter(Positions.id == position_id)
            .filter(Positions.is_active == True)
            .filter(LocationsPositions.max_openings > 0)
            .filter(LocationsPositions.filled_openings < LocationsPositions.max_openings)
            .all()
        )

        # Convert each location to a dictionary (implement location_to_dict accordingly)
        return [location_to_dict(location) for location in locations]

    except SQLAlchemyError as e:
        print(f"Error fetching locations by position ID {position_id}: {e}")
        db_session.rollback()
        return []
    finally:
        db_session.remove()
     
     
def get_locations_by_city_state(city, state):
    """
    Retrieves active locations matching the specified city and state.
    Similar in structure to get_locations_by_position, returns a list of location dictionaries.
    
    Args:
        city (str): The city name to filter by.
        state (str): The state name to filter by.

    Returns:
        list: A list of dictionaries representing matching locations.
    """
    print("Matching by city state")
    print(city)
    print(state)
    try:
        # Query locations that match the provided city and state
        # and filter only active ones.
        matching_locations = (
            db_session.query(Locations)
            .filter(Locations.city == city)
            .filter(Locations.state == state)
            .filter(Locations.is_active == True)
            .all()
        )

        # Convert each location to a dictionary
        return [location_to_dict(location) for location in matching_locations]

    except SQLAlchemyError as e:
        print(f"Error fetching locations by city/state ({city}, {state}): {e}")
        db_session.rollback()
        return []
    finally:
        db_session.remove()   
        
        
def update_location_context_cities():
    """
    Updates the assistant instructions with a JSON array of unique city/state pairs
    that have open positions (is_active == True, max_openings > 0, filled_openings < max_openings).

    This function mimics the logic of the existing update_location_context function
    but focuses on gathering cities and states instead of a full list of active locations.
    """

    # Make sure you've already got a db_session, engine, and API key loaded elsewhere
    # (as shown in the existing code this function replaces).
    # Replace variables api_key and assistant_id with your real values or rely on environment configs.
    try:
        client = OpenAI(api_key=api_key)
        my_assistant = client.beta.assistants.retrieve(assistant_id)
        current_instructions = getattr(my_assistant, "instructions", None)

        # Optionally check if the instructions text contains the expected marker
        if "Here are the different locations:" not in current_instructions:
            print("Expected marker not found in instructions. Not updating instructions.")
            return None

        # Query distinct city/state pairs for active locations with open positions
        cities_with_open_positions = (
            db_session.query(Locations.city, Locations.state)
            .distinct()
            .join(LocationsPositions, Locations.id == LocationsPositions.location_id)
            .join(Positions, Positions.id == LocationsPositions.position_id)
            .filter(Locations.is_active == True)
            .filter(Positions.is_active == True)
            .filter(LocationsPositions.max_openings > 0)
            .filter(LocationsPositions.filled_openings < LocationsPositions.max_openings)
            .all()
        )

        # Convert the data to a list of dicts
        cities_data = [
            {"city": city, "state": state}
            for city, state in cities_with_open_positions
        ]

        # Convert to JSON and escape backslashes
        cities_json = json.dumps(cities_data, indent=4).replace("\\", "\\\\")

        # Use a regex to replace the content after "Here are the different locations:" 
        # with the new JSON. Adjust the marker text as needed.
        print("Updating instructions with city-state data:")
        print(cities_json)
        locations_pattern = r"(Here are the different locations:\s*).*"
        # updated_instructions = re.sub(
        #     locations_pattern,
        #     "Here are the different locations: " + cities_json,
        #     current_instructions,
        #     flags=re.DOTALL
        # )

        # # Send updated instructions to the assistant
        # my_updated_assistant = client.beta.assistants.update(
        #     assistant_id,
        #     instructions=updated_instructions,
        # )

        return cities_json

    except SQLAlchemyError as e:
        print(f"Error updating location context for city/state pairs: {e}")
        db_session.rollback()
        return None
    finally:
        db_session.remove()
        
        
def update_location_context():
    try:
        # Interact with the OpenAI API to update the assistant context
        client = OpenAI(api_key=api_key)
        my_assistant = client.beta.assistants.retrieve(assistant_id)
        current_instructions = getattr(my_assistant, "instructions", None)
        if "Here are the different locations:" not in current_instructions:
            print("locations not in context, not updating...")
            return None

        # Query locations with their position counts using the LocationsPositions table, filtering by is_active
        locations_with_positions = (
            db_session.query(
                Locations,
                func.count(LocationsPositions.position_id).label("position_count")
            )
            .join(LocationsPositions, Locations.id == LocationsPositions.location_id)  
            .join(Positions, Positions.id == LocationsPositions.position_id)  
            .filter(Locations.is_active == True)  # just include active locations
            .group_by(Locations.id)
            .having(func.count(LocationsPositions.position_id) > 0)  # Only include locations with associated positions
            .all()
        )

        # create the JSON structure
        locations_data = [
            {
                "id": location.id,
                "name": location.name,
                "address": location.address,
                "city": location.city,
                "state": location.state,
                "zip": location.zip,
                "phone": location.phone,
                "position_count": position_count,  # count of positions
            }
            for location, position_count in locations_with_positions
        ]

        # Convert the JSON to a string and escape backslashes
        locations_json = json.dumps(locations_data, indent=4).replace("\\", "\\\\")

        print("current above, updated instructions below: ")
        locations_pattern = r"(Here are the different locations:\s*).*"
        updated_instructions = re.sub(
            locations_pattern,
            f"Here are the different locations: {locations_json}",
            current_instructions,
            flags=re.DOTALL
        )
        # locations_pattern = r"(Here are the different locations:\s*\[.*?\])"
        # updated_instructions = re.sub(
        #     locations_pattern, 
        #     f"Here are the different locations: {locations_json}", 
        #     current_instructions, 
        #     flags=re.DOTALL
        # )

        
        # Update the assistant (commented out for now)
        my_updated_assistant = client.beta.assistants.update(
            assistant_id,
            instructions=updated_instructions,
        )

        return locations_json  # Return the updated JSON for debugging/logging

    except SQLAlchemyError as e:
        print(f"Error updating location context: {e}")
        db_session.rollback()
        return None
    finally:
        db_session.remove()



# Generate the dynamic JSON for locations
#locations_json = update_location_context()
cities = update_location_context_cities()
