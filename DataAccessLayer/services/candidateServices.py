from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.candidates import Candidates
from DataAccessLayer.models.positions import Positions
from DataAccessLayer.models.locations import Locations
from DataAccessLayer.models.locations_positions import LocationsPositions
import os
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy import create_engine
from sqlalchemy import func
import json
from flask import Flask, request, jsonify
from AI.openai_utils import OpenAIUtility
from datetime import datetime




# Load environment variables
load_dotenv()

# Database configuration
dbname = os.getenv('dbname', 'qonda')
user = os.getenv('user', 'postgres')
password = os.getenv('password', 'Not24get!')
host = os.getenv('host', 'localhost')
port = os.getenv('pg_port', '5432')

# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
db_session = Session()

# Function to convert candidate model to dictionary
def candidate_to_dict(candidate):
    return {
        "id": candidate.id,
        "first_name": candidate.first_name,
        "last_name": candidate.last_name,
        "thread_id": candidate.thread_id,
        "age": candidate.age,
        "email": candidate.email,
        "experience": candidate.experience,
        "lead_source": candidate.lead_source,
        "availability": candidate.availability,
        "address": candidate.address,
        "city": candidate.city,
        "state": candidate.state,
        "zip": candidate.zip,
        "phone": candidate.phone,
        "position_id": candidate.position_id,
        "location_id": candidate.location_id,
        "position_id": candidate.position_id,
        "status_id": candidate.status_id,
        "interview_date": candidate.interview_date,
        "enrollment_start": candidate.enrollment_start,
        "enrollment_end": candidate.enrollment_end,
        "created_date": candidate.created_date,
        "updated_date": candidate.updated_date,
        "profile_img_url": candidate.profile_img_url,
        "files_id": candidate.files_id,
        "conversation": candidate.conversation,
    }
    
def candidate_position_location_to_dict(candidate, position_data, location):
    return {
        "id": candidate.id,
        "first_name": candidate.first_name,
        "last_name": candidate.last_name,
        "thread_id": candidate.thread_id,
        "age": candidate.age,
        "email": candidate.email,
        "experience": candidate.experience,
        "lead_source": candidate.lead_source,
        "availability": candidate.availability,
        "address": candidate.address,
        "city": candidate.city,
        "state": candidate.state,
        "zip": candidate.zip,
        "phone": candidate.phone,
        "status_id": candidate.status_id,
        "interview_date": candidate.interview_date,
        "enrollment_start": candidate.enrollment_start,
        "enrollment_end": candidate.enrollment_end,
        "created_date": candidate.created_date,
        "updated_date": candidate.updated_date,
        "profile_img_url": candidate.profile_img_url,
        "files_id": candidate.files_id,
        "conversation": candidate.conversation,
        "location_id": candidate.location_id,
        "position_id": candidate.position_id,
        "position": position_data,
            
        # {  
        #    "id": position.id,
        #    "name": position.name,
        #    "description": position.description,
        #    "location_id": position.location_id,
        #    "filled_openings": position.filled_openings,
        #    "max_openings": position.max_openings,
        #    "created_date": position.date_created,
        #    "updated_date": position.date_updated,
        # }
        
        "location": {
            "id": location.id,
            "name": location.name,
            "address": location.address,
            "city": location.city,
            "state": location.state,
            "zip": location.zip,
            "phone": location.phone,
        }
    }

# 1. Get all candidates
def get_all_candidates():
    try:
        candidates = db_session.query(Candidates).all()
        return [candidate_to_dict(candidate) for candidate in candidates]
    except SQLAlchemyError as e:
        print(f"Error fetching all candidates: {e}")
        return []



def replace_nulls_with_empty_string(data):
    if isinstance(data, dict):
        
        return {key: replace_nulls_with_empty_string(value) for key, value in data.items()}
    elif isinstance(data, list):
        
        return [replace_nulls_with_empty_string(item) for item in data]
    elif data is None:
        
        return ""   
    return data


# 2. Get candidate by ID
def get_candidate_by_id(candidate_id):
    try:
        # Retrieve the candidate
        candidate = db_session.query(Candidates).filter(Candidates.id == candidate_id).first()
        if not candidate:
            return None

        # Retrieve the position and location details associated with the candidate
        location_position = db_session.query(
            LocationsPositions.position_id,
            Positions.name,
            Positions.description,
            LocationsPositions.location_id,
            LocationsPositions.max_openings,
            LocationsPositions.filled_openings
        ).join(Positions, Positions.id == LocationsPositions.position_id) \
         .filter(
             LocationsPositions.position_id == candidate.position_id,
             LocationsPositions.location_id == candidate.location_id
         ).first()

        if not location_position:
            return None  # No matching position found for the candidate's location and position ID

        # Create a dictionary with the required fields
        position_data = {
            "position_id": location_position.position_id,
            "name": location_position.name,
            "description": location_position.description,
            "location_id": location_position.location_id,
            "max_openings": location_position.max_openings,
            "filled_openings": location_position.filled_openings
        }

        location = db_session.query(Locations).filter(Locations.id == candidate.location_id).first()
        
        candidate_dict_with_position_location = candidate_position_location_to_dict(candidate, position_data, location)
        return replace_nulls_with_empty_string(candidate_dict_with_position_location)
    
    except SQLAlchemyError as e:
        print(f"Error fetching candidate by ID: {e}")
        return None





# 3. Get candidates by status
def get_candidates_by_status(status_id):
    try:
        candidates = db_session.query(Candidates).filter(Candidates.status_id == status_id).all()
        return [candidate_to_dict(candidate) for candidate in candidates]
    except SQLAlchemyError as e:
        print(f"Error fetching candidates by status: {e}")
        return []

# 4. Create a new candidate
def create_candidate(candidate_data):
    try:
        new_candidate = Candidates(
            first_name=candidate_data.get("first_name"),
            last_name=candidate_data.get("last_name"),
            thread_id=candidate_data.get("thread_id"),
            age=candidate_data.get("age"),
            email=candidate_data.get("email"),
            experience=candidate_data.get("experience"),
            lead_source=candidate_data.get("lead_source"),
            availability=candidate_data.get("availability"),
            address=candidate_data.get("address"),
            city=candidate_data.get("city"),
            state=candidate_data.get("state"),
            zip=candidate_data.get("zip"),
            phone=candidate_data.get("phone"),
            position_id=candidate_data.get("position_id"),
            location_id=candidate_data.get("location_id"),
            status_id=candidate_data.get("status_id"),
            interview_date=candidate_data.get("interview_date"),
            enrollment_start=candidate_data.get("enrollment_start"),
            enrollment_end=candidate_data.get("enrollment_end"),
            profile_img_url=candidate_data.get("profile_img_url"),
            files_id=candidate_data.get("files_id"),
            conversation=candidate_data.get("conversation"),
        )
        db_session.add(new_candidate)
        db_session.commit()
        return candidate_to_dict(new_candidate)
    except SQLAlchemyError as e:
        print(f"Error creating candidate: {e}")
        db_session.rollback()
        return None

def save_to_database(json_data):
    print("Saving candidate to the database...")

    
    new_candidate = Candidates()
   
    for key, value in json_data.items():
        if hasattr(new_candidate, key):
            setattr(new_candidate, key, value if value != "" else None)
        else:
            print(f"Warning: '{key}' Not included in generated JSON. Skipping...")

    
    setattr(new_candidate, 'status_id', 1)
    try:
        db_session.add(new_candidate)
        db_session.commit()
        print("Candidate saved successfully.")
    except SQLAlchemyError as e:
        print(f"Error saving candidate: {e}")
        db_session.rollback()


# 5. Update candidate by ID
def update_candidate(candidate_id, update_data):
    try:
        candidate = db_session.query(Candidates).filter(Candidates.id == candidate_id).first()
        if not candidate:
            return None
        for key, value in update_data.items():
            setattr(candidate, key, value)
        db_session.commit()
        return candidate_to_dict(candidate)
    except SQLAlchemyError as e:
        print(f"Error updating candidate: {e}")
        db_session.rollback()
        return None

# 6. Delete candidate by ID
def delete_candidate(candidate_id):
    try:
        candidate = db_session.query(Candidates).filter(Candidates.id == candidate_id).first()
        if not candidate:
            return False

        phone_number = candidate.phone
        db_session.delete(candidate)
        db_session.commit()
        delete_by_phone(phone_number)

        return True
    except SQLAlchemyError as e:
        print(f"Error deleting candidate: {e}")
        db_session.rollback()
        return False

# 7. Update candidate status
def update_candidate_status(candidate_id, new_status):
    try:
        candidate = db_session.query(Candidates).filter(Candidates.id == candidate_id).first()
        if not candidate:
            return None
        
        candidate.status_id = new_status
        db_session.commit()
        return candidate_to_dict(candidate)
    
    except SQLAlchemyError as e:
        print(f"Error updating candidate: {e}")
        db_session.rollback()
        return None

#Searches db for phone and deletes, then deletes jsons
def delete_by_phone(phone_number):
    try:
        candidates_to_delete = db_session.query(Candidates).filter(Candidates.phone == phone_number).all()
        
        # Check if there are any candidates to delete
        if candidates_to_delete:
            for candidate in candidates_to_delete:
                db_session.delete(candidate)
            db_session.commit()

        # Now delete the corresponding JSON file(s) in the applicants_in_progress folder
        json_file_path = os.path.join("Stored_context/applicants_in_progress", f"{phone_number}.json")
        if os.path.exists(json_file_path):
            os.remove(json_file_path)
            return jsonify({"message": f"All candidate data for phone number {phone_number} successfully deleted."}), 200
        else:
            return jsonify({"error": f"No screening data found for phone number {phone_number}."}), 404
            
    except SQLAlchemyError as e:
        db_session.rollback()
        return jsonify({"error": f"Failed to delete candidate screening data from the database: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to delete candidate screening data: {str(e)}"}), 500


def load_candidates_json(phone_number):
    # Load JSON data from file or create an empty list if the file doesn't exist
    json_file_path = "Stored_context/applicants_in_progress/" + phone_number + ".json"

    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as f:
            data = json.load(f)
            # Ensure that the data is a list
            if isinstance(data, list):
                return data
            else:
                return []  # If the JSON is not a list, return an empty list
    return []

def save_candidates_json(data, phone_number):
    json_file_path = "Stored_context/applicants_in_progress/" + phone_number + ".json"

    # Save JSON data to file
    with open(json_file_path, 'w') as f:
        json.dump(data, f, indent=4)

def update_conversation(phone_number, user_message, assistant_response):
    data = load_candidates_json(phone_number)
    for candidate in data:
        if candidate["phone_number"] == phone_number:
            # Get the current message count and increment for each new message
            message_id = len(candidate["conversation"]) + 1
            
            candidate["conversation"].append({
                "message_id": message_id,  # Add the new message ID
                "timestamp": datetime.now().isoformat(),
                "message": user_message,
                "role": "external_user"
            })
            candidate["conversation"].append({
                "message_id": message_id + 1,  # Add the new message ID
                "timestamp": datetime.now().isoformat(),
                "message": assistant_response,
                "role": "assistant"
            })
            break
    save_candidates_json(data, phone_number)


def find_or_create_candidate_json(phone_number):
    data = load_candidates_json(phone_number)
    
    # Look for the candidate with the matching phone number
    for candidate in data:
        if candidate["phone_number"] == phone_number:
            print("Candidate exists")
            return candidate
    
    # If no candidate found, create a new one
    print("No existing candidate found. Creating new candidate.")
    # Create a new candidate with a new thread_id
    openAiUtils = OpenAIUtility()

    thread_id = openAiUtils.create_thread()
    
    
    new_entry = {
        "phone_number": phone_number,
        "thread_id": thread_id,
        "first_contact_timestamp": datetime.now().isoformat(),
        "conversation": []  
    }
    
    data.append(new_entry)
    save_candidates_json(data, phone_number)
    return new_entry
    
