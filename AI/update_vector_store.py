from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from DataAccessLayer.models.locations import Locations
from DataAccessLayer.models.positions import Positions
from DataAccessLayer.models.locations_positions import LocationsPositions
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from openai import OpenAI

client = OpenAI()

# Define the directory for storing context files
context_dir = "context_files"
os.makedirs(context_dir, exist_ok=True)

load_dotenv(override=True)

# Database configuration
dbname = os.getenv('dbname')
user = os.getenv('user')
password = os.getenv('password')
host = os.getenv('host')
port = os.getenv('pg_port')

api_key = os.getenv('OPENAI_KEY')
vector_store_id = os.getenv("VECTOR_STORE_ID")


# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)


def generate_all_txt_files():

    try:
        # Retrieve locations with available positions
        locations = (
            db_session.query(Locations)
            .join(Locations.positions) 
            .join(LocationsPositions, (LocationsPositions.location_id == Locations.id) & (LocationsPositions.position_id == Positions.id))  
            .filter(
                Locations.is_active == True,
                Positions.is_active == True,
                LocationsPositions.filled_openings < LocationsPositions.max_openings
            )
            .all()
        )

        if not locations:
            print("No active locations with available positions found.")
            return "No active locations with available positions found."

        # Group locations by state and city
        state_groups = {}
        city_groups = {}
        location_position_groups = {}

        for location in locations:
            for position in location.positions:
                if location.is_active and position.is_active:
                    # Group by state and city
                    state_groups.setdefault(location.state, []).append(location)
                    city_groups.setdefault(location.city, []).append(location)

                    # Group positions by location
                    location_position_groups.setdefault(location.id, {"location_name": location.name, "city": location.city, "state": location.state, "address": location.address, "positions": []})
                    location_position_groups[location.id]["positions"].append({"id": position.id, "name": position.name})

        # Write locations grouped by city
        with open(os.path.join(context_dir,dbname+"_all_available_locations_by_city.txt"), "w") as file:
            for city, locs in city_groups.items():
                file.write(f"Available locations in {city} city:\n\n")
                for loc in locs:
                    file.write(f"Location id: {loc.id},\n")
                    file.write(f"name: {loc.name},\n")
                    file.write(f"Address: {loc.address}\n")
                    file.write(f"city: {loc.city},\n")
                    file.write(f"state: {loc.state},\n")
                    file.write(f"zip: {loc.zip}\n")
                    file.write("\n")
                file.write("\n")
        print("File 'all_available_locations_by_city.txt' generated successfully.")

        # Write positions available for each location
        with open(os.path.join(context_dir, dbname+"_positions_available_for_locations.txt"), "w") as file:
            for loc_id, data in location_position_groups.items():
                file.write(f"Positions available for:\nLocation name: {data['location_name']}, Location ID: {loc_id}\n(City: {data['city']}, State: {data['state']}, Address: {data['address']}):\n\n")
                for position in data["positions"]:
                    file.write(f"Position id: {position['id']},\n")
                    file.write(f"name: {position['name']}.\n")
                    file.write("\n")
                file.write("\n")
        print("File 'positions_available_for_locations.txt' generated successfully.")

        # Write detailed position information
        with open(os.path.join(context_dir, dbname+"_all_available_positions_details.txt"), "w", encoding="utf-8") as file:
            positions = db_session.query(Positions).join(LocationsPositions).filter(
                Positions.is_active == True,
                LocationsPositions.filled_openings < LocationsPositions.max_openings
            ).all()
            
            for position in positions:
                file.write(f"Position ID: {position.id}\n")
                file.write(f"Name: {position.name}\n")
                
                if position.description:  # Check if description is not None or empty
                    file.write(f"Description: {position.description}\n")
                
                key_responsibilities = position.key_responsibilities
                if key_responsibilities:
                    if isinstance(key_responsibilities, list):
                        key_responsibilities = "; ".join(key_responsibilities)
                    file.write(f"Key Responsibilities: {key_responsibilities}\n")

                qualifications = position.qualifications
                if qualifications:
                    if isinstance(qualifications, list):
                        qualifications = "; ".join(qualifications)
                    file.write(f"Qualifications: {qualifications}\n")

                benefits = position.benefits
                if benefits:
                    if isinstance(benefits, list):
                        benefits = "; ".join(benefits)
                    file.write(f"Benefits: {benefits}\n")
                
                if position.salary_range:  # Check if salary_range is not None or empty
                    salary_info = f"{position.salary_range}"
                    if position.salary_currency:
                        salary_info += f" {position.salary_currency}"
                    if position.salary_period:
                        salary_info += f" per {position.salary_period}"
                    file.write(f"Salary Range: {salary_info}\n")
                
                if position.job_type:  # Check if job_type is not None or empty
                    file.write(f"Job Type: {position.job_type}\n")
                
                if position.location_type:  # Check if location_type is not None or empty
                    file.write(f"Location Type: {position.location_type}\n")
                
                file.write("\n")
        print("File 'all_available_positions_details.txt' generated successfully.")

        return "All files generated successfully."

    except SQLAlchemyError as e:
        db_session.rollback()  # Rollback in case of error
        print(f"Error fetching data from the database: {e}")
        return f"Error fetching data from the database: {e}"

    finally:
        db_session.close()  # Ensure the session is closed
        print("Database session closed.")


def load_to_vector_store():
    # Retrieve the vector store
    vector_store = client.beta.vector_stores.retrieve(
        vector_store_id=os.getenv("VECTOR_STORE_ID")
    )

    # Retrieve the list of files in the vector store
    files_in_vs = client.beta.vector_stores.files.list(vector_store_id=vector_store.id)

    # Delete all existing files in the vector store
    for file in files_in_vs.data:
        client.beta.vector_stores.files.delete(
            vector_store_id=vector_store.id, file_id=file.id
        )
        client.files.delete(file.id)

    # Get all .txt files in the current directory
    file_paths = [os.path.join(context_dir, f) for f in os.listdir(context_dir) if f.endswith(".txt")]

    if not file_paths:
        print("No .txt files found in the context_files/ directory.")
        return

    # Open the files in binary mode for upload
    file_streams = [open(path, "rb") for path in file_paths]

    # Use the upload and poll SDK helper to upload the files, add them to the vector store,
    # and poll the status of the file batch for completion.
    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams,
        chunking_strategy={"type": "static", "static": {"max_chunk_size_tokens": 1200, "chunk_overlap_tokens": 600}}
    )

    # Print the status and the file counts of the batch
    print(f"Batch Status: {file_batch.status}")
    print(f"File Counts: {file_batch.file_counts}")

    # Close all file streams
    for stream in file_streams:
        stream.close()
        

#generate_all_txt_files()
#load_to_vector_store()