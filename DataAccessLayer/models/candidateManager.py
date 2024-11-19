import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import psycopg2
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from .candidates import Candidates
from .locations import Locations
from .status import Status


app = Flask(__name__)


    
# Load environment variables from .env file
load_dotenv(override=True)

# Load database configuration from environment variables
dbname = os.getenv('dbname')
user = os.getenv('user')
password = os.getenv('password')
host = os.getenv('host')
port = os.getenv('port')

# Construct the database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"

engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class CandidateManager:
    def update_candidate(self, candidate_id, data):
        session = Session()
        try:
            candidate = session.query(Candidates).filter_by(id=candidate_id).first()
            if not candidate:
                return jsonify({"error": "Candidate not found"}), 404

            for key, value in data.items():
                setattr(candidate, key, value)

            session.commit()

            updated_candidate = session.query(
                Candidates.id, Candidates.first_name, Candidates.last_name, Candidates.age,
                Candidates.email, Candidates.phone, Candidates.address, Candidates.city,
                Candidates.state, Candidates.zip, Locations.name.label('location_name'),
                Status.name.label('status_name')
            ).join(Locations, Locations.id == Candidates.location_id, isouter=True
            ).join(Status, Status.id == Candidates.status_id, isouter=True
            ).filter(Candidates.id == candidate_id).first()

            if updated_candidate:
                return jsonify({
                    "message": "Candidate updated successfully",
                    "candidate": {
                        "id": updated_candidate.id,
                        "first_name": updated_candidate.first_name,
                        "last_name": updated_candidate.last_name,
                        "age": updated_candidate.age,
                        "email": updated_candidate.email,
                        "phone": updated_candidate.phone,
                        "address": updated_candidate.address,
                        "city": updated_candidate.city,
                        "state": updated_candidate.state,
                        "zip": updated_candidate.zip,
                        "location_name": updated_candidate.location_name,
                        "status_name": updated_candidate.status_name
                    }
                }), 200
        except SQLAlchemyError as e:
            session.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()

    def get_all_candidates(self):
        session = Session()
        try:
            candidates = session.query(
                Candidates.first_name, Candidates.last_name, Candidates.email,
                Candidates.phone, Candidates.age, Candidates.location_id, Candidates.status_id
            ).all()

            return jsonify([
                {
                    "first_name": candidate.first_name,
                    "last_name": candidate.last_name,
                    "email": candidate.email,
                    "phone": candidate.phone,
                    "age": candidate.age,
                    "location_id": candidate.location_id,
                    "status_id": candidate.status_id
                } for candidate in candidates
            ]), 200
        finally:
            session.close()

    def specific_candidate(self, candidate_id):
        session = Session()
        try:
            candidate = session.query(
                Candidates.id, Candidates.first_name, Candidates.last_name, Candidates.age,
                Candidates.email, Candidates.phone, Candidates.address, Candidates.city,
                Candidates.state, Candidates.zip, Locations.name.label('location_name'),
                Status.name.label('status_name')
            ).join(Locations, Locations.id == Candidates.location_id, isouter=True
            ).join(Status, Status.id == Candidates.status_id, isouter=True
            ).filter(Candidates.id == candidate_id).first()

            if candidate:
                return jsonify({
                    "id": candidate.id,
                    "first_name": candidate.first_name,
                    "last_name": candidate.last_name,
                    "age": candidate.age,
                    "email": candidate.email,
                    "phone": candidate.phone,
                    "address": candidate.address,
                    "city": candidate.city,
                    "state": candidate.state,
                    "zip": candidate.zip,
                    "location_name": candidate.location_name,
                    "status_name": candidate.status_name
                }), 200
            else:
                return jsonify({"error": "Candidate not found"}), 404
        finally:
            session.close()

    def delete_candidate(self, candidate_id):
        session = Session()
        try:
            candidate = session.query(Candidates).filter_by(id=candidate_id).first()
            if not candidate:
                return jsonify({"error": "Candidate not found"}), 404

            session.delete(candidate)
            session.commit()

            return jsonify({
                "message": "Candidate deleted successfully",
                "id": candidate_id
            }), 200
        except SQLAlchemyError as e:
            session.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()


    def update_candidate_status(self, candidate_id, new_status):
        session = Session()
        try:
            candidate = session.query(Candidates).filter_by(id=candidate_id).first()
            if not candidate:
                return jsonify({"error": "Candidate not found"}), 404
            
            candidate.status_id = new_status
            session.commit()  # Commit the changes to the database
            
            
        except SQLAlchemyError as e:
            session.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()


manager = CandidateManager()

@app.route('/candidate/<int:candidate_id>', methods=['PUT'])
def update_candidate(candidate_id):
    data = request.json
    return manager.update_candidate(candidate_id, data)

@app.route('/candidates', methods=['GET'])
def get_all_candidates():
    return manager.get_all_candidates()

@app.route('/candidate/<int:candidate_id>', methods=['GET'])
def get_specific_candidate(candidate_id):
    return manager.specific_candidate(candidate_id)

@app.route('/candidate/<int:candidate_id>', methods=['DELETE'])
def delete_candidate(candidate_id):
    return manager.delete_candidate(candidate_id)

if __name__ == '__main__':
    app.run(debug=True)