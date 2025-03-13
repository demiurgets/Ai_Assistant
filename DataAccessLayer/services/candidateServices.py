import requests
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.assistants import Assistants
from DataAccessLayer.models.candidates import Candidates
from DataAccessLayer.models.positions import Positions
from DataAccessLayer.models.locations import Locations
from DataAccessLayer.models.locations_positions import LocationsPositions
from DataAccessLayer.services.match_positions_with_cv import run_similarity_search
import os
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine
from sqlalchemy import func
import json
from flask import Flask, request, jsonify
from AI.openai_utils import OpenAIUtility
from datetime import datetime
import logging
from sqlalchemy import desc

# Load environment variables
load_dotenv()

# Database configuration
dbname = os.getenv('dbname', 'qonda')
user = os.getenv('user', 'postgres')
password = os.getenv('password', 'Not24get!')
host = os.getenv('host', 'localhost')
port = os.getenv('pg_port', '5432')
save_data_url = os.getenv('save_data_url')
get_data_url = os.getenv('get_data_url')
delete_data_url = os.getenv('delete_data_url')
customer_id = os.getenv('customer_id')

# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)

SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)

logging.basicConfig(level=logging.INFO)

# Function to convert candidate model to dictionary
def candidate_to_dict(candidate):
    return {
        "id": candidate.id,
        "candidate_identifier": candidate.candidate_identifier,
        "first_name": candidate.first_name,
        "last_name": candidate.last_name,
        "thread_id": candidate.thread_id,
        "age": candidate.age,
        "email": candidate.email,
        "experience": candidate.experience,
        "lead_source": candidate.lead_source,
        "lead_source_id": candidate.lead_source_id,
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
    
def candidate_position_location_to_dict(candidate, position_data, location,position):
    return {
        "id": candidate.id,
        "candidate_identifier": candidate.candidate_identifier,
        "first_name": candidate.first_name,
        "last_name": candidate.last_name,
        "thread_id": candidate.thread_id,
        "age": candidate.age,
        "email": candidate.email,
        "experience": candidate.experience,
        "lead_source": candidate.lead_source,
        "lead_source_id": candidate.lead_source_id,
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
        "position": {
            **position_data,
            "key_responsibilities": position.key_responsibilities,
            "qualifications": position.qualifications,
            "benefits": position.benefits,
            "salary_range": position.salary_range,
            "salary_currency": position.salary_currency,
            "salary_period": position.salary_period,
            "job_type": position.job_type,
            "location_type": position.location_type,
            "is_active": position.is_active,
            "working_hours": position.working_hours
        },
        
        "location": {
            "id": location.id,
            "name": location.name,
            "address": location.address,
            "city": location.city,
            "state": location.state,
            "zip": location.zip,
            "phone": location.phone,
            "is_active": location.is_active,
        }
    }

# 1. Get all candidates
def get_all_candidates():
    try:
        candidates = db_session.query(Candidates).order_by(desc(Candidates.created_date)).all()
        return [candidate_to_dict(candidate) for candidate in candidates]
    except SQLAlchemyError as e:
        db_session.rollback()
        logging.error(f"Error fetching all candidates: {e}")
        return []
    finally:
        db_session.remove()



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

        
        
        position_data = {
            "position_id": location_position.position_id if location_position else None,
            "name": location_position.name if location_position else None,
            "description": location_position.description if location_position else None,
            "location_id": location_position.location_id if location_position else None,
            "max_openings": location_position.max_openings if location_position else None,
            "filled_openings": location_position.filled_openings if location_position else None
}
        
        location = db_session.query(Locations).filter(Locations.id == candidate.location_id).first()
        position = db_session.query(Positions).filter(Positions.id == candidate.position_id).first()
        candidate_dict_with_position_location = candidate_position_location_to_dict(candidate, position_data, location, position)
        return replace_nulls_with_empty_string(candidate_dict_with_position_location)
    
    except SQLAlchemyError as e:
        db_session.rollback()
        logging.error(f"Error fetching candidate by ID: {e}")
        return None
    finally:
        db_session.remove()





# 3. Get candidates by status
def get_candidates_by_status(status_id):
    try:
        candidates = db_session.query(Candidates).filter(Candidates.status_id == status_id).all()
        return [candidate_to_dict(candidate) for candidate in candidates]
    except SQLAlchemyError as e:
        db_session.rollback()
        logging.error(f"Error fetching candidates by status (status_id={status_id}): {e}")
        return []
    finally:
        db_session.remove()

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
            lead_source_id=candidate_data.get("lead_source_id"),
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
            candidate_identifier=candidate_data.get("candidate_identifier"),

        )
        db_session.add(new_candidate)
        db_session.commit()
        return candidate_to_dict(new_candidate)
    except SQLAlchemyError as e:
        db_session.rollback()
        logging.error(f"Error creating candidate: {e}, candidate data: {candidate_data}")
        return None
    finally:
        db_session.remove()


def save_to_database(json_data):
    logging.info("Saving candidate to the database...")
    
    new_candidate = Candidates()
    
    for key, value in json_data.items():
        if hasattr(new_candidate, key):
            setattr(new_candidate, key, value if value != "" else None)
        else:
            logging.warning(f"'{key}' is not a valid attribute of Candidates. Skipping...")
    
    setattr(new_candidate, 'status_id', 1)
    
    try:
        db_session.add(new_candidate)
        db_session.commit()
        logging.info("Candidate saved successfully.")
        return True  
    except SQLAlchemyError as e:
        db_session.rollback()
        logging.error(f"Error saving candidate: {e}, data: {json_data}")
        return False  
    finally:
        db_session.remove()  


# 5. Update candidate by ID
def update_candidate(candidate_id, update_data):
    try:
        candidate = db_session.query(Candidates).filter(Candidates.id == candidate_id).first()
        if not candidate:
            logging.warning(f"Candidate with ID {candidate_id} not found.")
            return None
        
        for key, value in update_data.items():
            if hasattr(candidate, key):
                setattr(candidate, key, value)
            else:
                logging.warning(f"Warning: '{key}' not included in Candidates model. Skipping...")
        
        db_session.commit()
        logging.info(f"Candidate with ID {candidate_id} updated successfully.")
        return candidate_to_dict(candidate)
    except SQLAlchemyError as e:
        db_session.rollback()
        logging.error(f"Error updating candidate with ID {candidate_id}: {e}, data: {update_data}")
        return None
    finally:
        db_session.remove()


# 6. Delete candidate by ID
def delete_candidate(candidate_id):
    try:
        candidate = db_session.query(Candidates).filter(Candidates.id == candidate_id).first()
        if not candidate:
            logging.warning(f"Candidate with ID {candidate_id} not found.")
            return False

        candidate_identifier = candidate.candidate_identifier
        
        db_session.delete(candidate)
        db_session.commit()
        logging.info(f"Candidate with ID {candidate_id} deleted successfully.")

        try:
            delete_by_candidate_identifier(candidate_identifier)
            logging.info(f"Associated data with candidate identifier {candidate_identifier} deleted successfully.")
        except Exception as e:
            logging.warning(f"Failed to delete associated data for candidate identifier {candidate_identifier}: {e}")

        return True
    except SQLAlchemyError as e:
        db_session.rollback()
        logging.error(f"Error deleting candidate with ID {candidate_id}: {e}")
        return False
    finally:
        db_session.remove()

# 7. Update candidate status
def update_candidate_status(candidate_id, new_status):
    try:
        # Buscar el candidato
        candidate = db_session.query(Candidates).filter(Candidates.id == candidate_id).first()
        if not candidate:
            logging.warning(f"Candidate with ID {candidate_id} not found.")
            return None

        # Actualizar el estado del candidato
        candidate.status_id = new_status
        db_session.commit()
        logging.info(f"Candidate with ID {candidate_id} updated to status {new_status}.")
        return candidate_to_dict(candidate)
    
    except SQLAlchemyError as e:
        db_session.rollback()
        logging.error(f"Error updating candidate status (ID: {candidate_id}, Status: {new_status}): {e}")
        return None
    finally:
        # Limpiar la sesión
        db_session.remove()

def get_corresponding_assistant(candidate_identifier):
    """
    Determines the assistant ID based on the candidate's assistant_stage.
    If the assistant_stage is 0, it queries for an assistant with 'greeter' in the name.
    If the assistant_stage is 1, it queries for an assistant with 'documents' in the name.
    If the assistant_stage is 2, it queries for an assistant with 'review' in the name.
    
    """
    try:
        # Load JSON data for the candidate
        data = load_candidates_json(candidate_identifier)
        candidate = next((c for c in data if c["candidate_identifier"] == candidate_identifier), None)
        
        if not candidate:
            print(f"No candidate found for candidate identifier {candidate_identifier}.")
            return None
        
        # Get the candidate's status
        assistant_stage = candidate.get("assistant_stage", 0)
        
        # Query the database based on status
        if assistant_stage == 0:
            assistant = db_session.query(Assistants).filter(Assistants.name.like('%greeter%')).first()
        elif assistant_stage == 1:
            assistant = db_session.query(Assistants).filter(Assistants.name.like('%documents%')).first()
        elif assistant_stage == 2:
            assistant = db_session.query(Assistants).filter(Assistants.name.like('%review%')).first()
        elif assistant_stage == 10:
            assistant = db_session.query(Assistants).filter(Assistants.name.like('%training%')).first()
        else:
            print(f"Unhandled assistant_stage: {assistant_stage} for candidate identifier {candidate_identifier}.")
            return None
        
        if assistant:
            print(f"Assistant ID found: {assistant.assistant_id} for assistant_stage: {assistant_stage}")
            return assistant.assistant_id
        else:
            print(f"No assistant found matching the criteria for assistant_stage: {assistant_stage}.")
            return None
            
    except SQLAlchemyError as e:
        db_session.rollback()
        logging.error(f"Error retrieving assistant: {e}")
        return None
    finally:
        db_session.remove()


def upgrade_candidate(candidate_identifier, candidate_data):
    # Load existing JSON data for the given candidate identifier
    data = load_candidates_json(candidate_identifier)
    
    # Find the candidate in the JSON file
    for candidate in data:
        if candidate["candidate_identifier"] == candidate_identifier:
            # Increment the status field or initialize it if not present
            candidate["assistant_stage"] = candidate.get("assistant_stage", 0) + 1
            
            # Create a new thread
            openAiUtils = OpenAIUtility()
            new_thread_id = openAiUtils.create_thread()
            
            candidate_data_str = json.dumps(candidate_data, indent=4)

            # Compose the message
            message = (
                "The candidate has just finished a part of the interview. "
                "Please seamlessly continue into your instructions without saying hello. "
                "Here is the candidate's info for your reference:\n\n"
                f"{candidate_data_str}"
            )
            assistant_response = openAiUtils.send_to_ai(
                message, 
                new_thread_id, 
                get_corresponding_assistant(candidate_identifier)
            )
            
            # Update the candidate's thread ID
            candidate["thread_id"] = new_thread_id
            
            print(f"Candidate upgraded. New assistant_stage: {candidate['assistant_stage']}, New thread ID: {new_thread_id}")
            
            # Save the updated JSON data
            save_candidates_json(data, candidate_identifier)
            return candidate  # Return updated candidate for reference
    
    # If no candidate is found, create a new one
    print(f"No candidate found for candidate_identifier {candidate_identifier}. Creating a new candidate.")
    new_candidate = find_or_create_candidate_json(candidate_identifier)
    new_candidate["status"] = 1  # Initialize status for a new candidate
    save_candidates_json(data, candidate_identifier)
    return new_candidate

#Searches db for candidate identifier and deletes, then deletes jsons

## Candidate JSON Files
def get_candidate_data(candidate_identifier):
    
    url = get_data_url
    payload = {
        "candidate_id": candidate_identifier
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Raise error for HTTP error codes

        data = response.json()
        if data.get("success") and "data" in data:
            extracted_info = json.loads(data["data"])
            return extracted_info if isinstance(extracted_info, list) else []
        
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching candidate data: {e}")
        return []
    
## Save JSONN Files
def save_candidate_data(candidate_identifier, data):
    
    url = save_data_url
    
    # Convert list/dict to a properly escaped JSON string
    json_string = json.dumps(data, ensure_ascii=False)

    payload = {
        "customer_id": customer_id,
        "candidate_id": candidate_identifier,
        "data": json_string  # JSON properly formatted as a string
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Raise error for HTTP error codes

        result = response.json()
        return result.get("success", False)  # Return True if the request was successful
    except requests.exceptions.RequestException as e:
        print(f"Error saving candidate data: {e}")
        return False
    
## Delete JSON Files
def delete_candidate_data(candidate_identifier):
   
    url = delete_data_url
    
    payload = {
        "customer_id": customer_id,
        "candidate_id": candidate_identifier
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Raise error for HTTP error codes

        result = response.json()
        return result.get("success", False)  # Return True if deletion was successful
    except requests.exceptions.RequestException as e:
        print(f"Error deleting candidate data: {e}")
        return False

def delete_by_candidate_identifier(candidate_identifier):
   
    try:
        # Delete candidate data from the database
        candidates_to_delete = db_session.query(Candidates).filter(Candidates.candidate_identifier == candidate_identifier).all()
        
        if candidates_to_delete:
            for candidate in candidates_to_delete:
                db_session.delete(candidate)
            db_session.commit()

        # Delete the JSON file using the API
        json_deleted = delete_candidate_data(candidate_identifier)

        # Check if the JSON deletion was successful
        if json_deleted:
            return jsonify({"message": f"All candidate data for candidate identifier {candidate_identifier} successfully deleted from the database and API."}), 200
        else:
            return jsonify({"error": f"Candidate data deleted from the database, but failed to delete JSON from the API."}), 500

    except SQLAlchemyError as e:
        db_session.rollback()
        return jsonify({"error": f"Failed to delete candidate screening data from the database: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to delete candidate screening data: {str(e)}"}), 500
    finally:
        db_session.remove()


def load_issues():
    """Load candidate submitted issue report from the JSON file. If the file does not exist, return an empty list."""

    ISSUE_FILE_PATH = "Stored_context/issue_reports/candidate_issues.json"

    if not os.path.exists(ISSUE_FILE_PATH):
        return []
    with open(ISSUE_FILE_PATH, 'r') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []

def save_new_issue(data):
    ISSUE_FILE_PATH = "Stored_context/issue_reports/candidate_issues.json"

    issue = data.get('issue')
    candidate_identifier = data.get('candidate_identifier')

    if not issue or not candidate_identifier:
        return jsonify({'error': 'Issue and candidate identifier are required'}), 400

    new_issue = {
        'candidate_identifier': candidate_identifier,
        'issue': issue,
        'timestamp': request.args.get('timestamp', None)  # Optional timestamp
    }

    # Load existing issues, add the new issue, and save back to the file
    issues_data = load_issues()

    # Extract the issues list from the JSON structure
    issues = issues_data.get('issues', []) if isinstance(issues_data, dict) else issues_data

    issues.append(new_issue)

    with open(ISSUE_FILE_PATH, 'w') as file:
        json.dump({'issues': issues}, file, indent=4)  # Save as a dictionary

    return new_issue
    



def load_candidates_json(candidate_identifier):
    
    extracted_info = get_candidate_data(candidate_identifier)

    # Ensure that the data is a list
    return extracted_info if isinstance(extracted_info, list) else []

def save_candidates_json(data, candidate_identifier):
   
    return save_candidate_data(candidate_identifier, data)

def update_conversation(candidate_identifier, user_message=None, assistant_response=None):
    data = load_candidates_json(candidate_identifier)
    print("adding new info for cv")
    for candidate in data:
        if candidate["candidate_identifier"] == candidate_identifier:
            # Get the current message count and increment for each new message
            message_id = len(candidate["conversation"]) + 1
            
            if user_message is not None:
                candidate["conversation"].append({
                    "message_id": message_id,  # Add the new message ID
                    "timestamp": datetime.now().isoformat(),
                    "message": user_message,
                    "role": "external_user"
                })
            if assistant_response is not None:
                candidate["conversation"].append({
                    "message_id": message_id,  # Add the new message ID
                    "timestamp": datetime.now().isoformat(),
                    "message": assistant_response,
                    "role": "assistant"
                })
            break
    save_candidates_json(data, candidate_identifier)

def add_cv_analysis(candidate_identifier, cv_analysis_data):
    data = load_candidates_json(candidate_identifier)
    
    for candidate in data:
        if candidate["candidate_identifier"] == candidate_identifier:
            candidate["cv_analysis"] = cv_analysis_data
            save_candidates_json(data, candidate_identifier)
            matched_positions = match_cv_to_positions(candidate_identifier)
            message = (
                "The candidate has uploaded their CV, if it has all the information needed for the candidate such as: name, brief experience (1-3 sentences), email, etc. skip these questions and only ask for age, lead source and availability if not asked already."
                f"CV Analysis:\n{cv_analysis_data}\n\n"
                f"Similarity Search Results:\n{matched_positions}"
            )

            openAiUtils = OpenAIUtility()
            assistant_response = openAiUtils.send_to_ai(
                            message, 
                            candidate["thread_id"], 
                            get_corresponding_assistant(candidate_identifier)
                        )
            break
    else:
        print("Candidate not found. Cannot add CV analysis.")
        return
    update_conversation(candidate_identifier, user_message="CV Upload", assistant_response=assistant_response)


def extract_text_from_json(data):
    """
    Recursively extracts string values from the JSON structure
    to build a query string. This method handles nested structures.
    """
    query_parts = []

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                query_parts.append(value)
            elif isinstance(value, (list, dict)):
                query_parts.append(extract_text_from_json(value))

    elif isinstance(data, list):
        for item in data:
            query_parts.append(extract_text_from_json(item))

    # Filter out None and join the results
    return " ".join(filter(None, query_parts))

def match_cv_to_positions(candidate_identifier):
    data = load_candidates_json(candidate_identifier)
    for candidate in data:
        if candidate["candidate_identifier"] == candidate_identifier:
            if "cv_analysis" in candidate:
                try:
                    analysis = candidate["cv_analysis"]
                except json.JSONDecodeError:
                    print("Error decoding cv_analysis JSON")
                    return "**Error**: Invalid CV analysis data format."
                
                # Extract all text-based fields from the analysis dynamically
                query = extract_text_from_json(analysis)

                if not query:
                    return "**Error**: No valid information to generate query."
                
                print("running positions query...")

                # Assuming `run_similarity_search` takes the query as an input
                filter_metadata = {"source": dbname}
                similar_documents = run_similarity_search(query, k=5, filter=filter_metadata)
                
                if not similar_documents:
                    return "No similar positions found."

                # Format the results into a Markdown string
                formatted_results = "**Top Similar Positions**\n\n"
                matched_positions = []  # We'll store structured data here

                for res, score in similar_documents:
                    doc_id = res.metadata.get("id")
                    content = res.page_content
                    percent_match = ((2.0 - score) / 2.0 * 100)*2

                    score_rounded = round(score, 2)
                    percent_match_rounded = round(percent_match, 2)

                    # Markdown formatting for each result
                    formatted_results += f" **Position ID**: {doc_id}\n"
                    formatted_results += f"- **Score**: {score_rounded:.2f}\n"
                    formatted_results += f"- **Match**: {percent_match_rounded:.2f}%\n"
                    formatted_results += f"- **Content**: {content}\n\n"

                    # Store the two-decimal values
                    matched_positions.append({
                        "position_id": doc_id,
                        "score": float(score_rounded),  
                        "percent_match": float(percent_match_rounded),
                        "content": content
                    })

                candidate["matched_positions"] = matched_positions
                save_candidates_json(data, candidate_identifier)
                return formatted_results
            else:
                return "**Error**: Candidate must upload/analyze CV first."
    return "**Error**: Candidate not found."

def find_or_create_candidate_json(candidate_identifier):
    data = load_candidates_json(candidate_identifier)
    
    # Look for the candidate with the matching candidate identifier
    for candidate in data:
        if candidate["candidate_identifier"] == candidate_identifier:
            print("Candidate exists")
            return candidate
    
    # If no candidate found, create a new one
    print("No existing candidate found. Creating new candidate.")
    # Create a new candidate with a new thread_id
    openAiUtils = OpenAIUtility()

    thread_id = openAiUtils.create_thread()
    
    
    new_entry = {
        "candidate_identifier": candidate_identifier,
        "thread_id": thread_id,
        "assistant_stage": 0,
        "first_contact_timestamp": datetime.now().isoformat(),
        "conversation": []  
    }
    
    data.append(new_entry)
    save_candidates_json(data, candidate_identifier)
    return new_entry
    
