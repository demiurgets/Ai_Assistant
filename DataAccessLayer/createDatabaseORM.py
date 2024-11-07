import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from models import Base  # Import centralized Base from models/__init__.py

# Load environment variables from .env file
load_dotenv()

# Load database configuration from environment variables
dbname = os.getenv('dbname')
user = os.getenv('user')
password = os.getenv('password')
host = os.getenv('host')
port = os.getenv('port')

# Construct the database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"

def initialize_database(engine):
    """Create all tables defined in models."""
    try:
        print("Metadata:", Base.metadata.tables)  # Print all tables in metadata
        Base.metadata.create_all(engine)  # Create tables based on models
        print("Tables created successfully.")
    except SQLAlchemyError as e:
        print("Error creating tables:", e)

def main():
    # Create a database engine
    engine = create_engine(database_url)
    print(f"Engine created: {database_url}")  # Debug print to confirm connection

    # Initialize tables based on models
    initialize_database(engine)

if __name__ == "__main__":
    main()
