from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from DataAccessLayer.models.candidates import Candidates
import os
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy import func

# Load environment variables
load_dotenv()

# Database configuration
dbname = os.getenv('dbname', 'qonda')
user = os.getenv('user', 'postgres')
password = os.getenv('password', 'Not24get!')
host = os.getenv('host', 'localhost')
port = os.getenv('port', '5432')

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
        "location_id": candidate.location_id,
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

# 1. Get all candidates
def get_all_candidates():
    try:
        candidates = db_session.query(Candidates).all()
        return [candidate_to_dict(candidate) for candidate in candidates]
    except SQLAlchemyError as e:
        print(f"Error fetching all candidates: {e}")
        return []

# 2. Get candidate by ID
def get_candidate_by_id(candidate_id):
    try:
        candidate = db_session.query(Candidates).filter(Candidates.id == candidate_id).first()
        return candidate_to_dict(candidate) if candidate else None
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
        db_session.delete(candidate)
        db_session.commit()
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
