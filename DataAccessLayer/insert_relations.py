import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine

load_dotenv(override=True)

# Database configuration
dbname = os.getenv('dbname')
user = os.getenv('user')
password = os.getenv('password')
host = os.getenv('host')
port = os.getenv('pg_port')

# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)

# List all files in the directory
files = os.listdir('excel_file_context')

# Filter for Excel files and read the first one
excel_files = [file for file in files if file.endswith('.xlsx')]

if excel_files:
    # Load the Relations sheet from the first Excel file
    df = pd.read_excel(os.path.join('excel_file_context', excel_files[0]), sheet_name="Relations")
    
    # Load Locations and Positions sheets to get IDs
    locations_df = pd.read_excel(os.path.join('excel_file_context', excel_files[0]), sheet_name="Locations")
    positions_df = pd.read_excel(os.path.join('excel_file_context', excel_files[0]), sheet_name="Positions")
    
    # Normalize text (convert to uppercase and remove accents)
    def normalize_text(text):
        import unicodedata
        return ''.join(
            c for c in unicodedata.normalize('NFKD', str(text).upper()) if not unicodedata.combining(c)
        )
    
    # Apply normalization
    locations_df["normalized_name"] = locations_df["Location name"].apply(normalize_text)
    positions_df["normalized_name"] = positions_df["Position name"].apply(normalize_text)
    df["normalized_location"] = df["Locations"].apply(normalize_text)
    df["normalized_position"] = df["Positions"].apply(normalize_text)
    
    # Merge IDs
    df = df.merge(locations_df[["id", "normalized_name"]], left_on="normalized_location", right_on="normalized_name", how="left")
    df.rename(columns={"id": "location_id"}, inplace=True)
    
    df = df.merge(positions_df[["id", "normalized_name"]], left_on="normalized_position", right_on="normalized_name", how="left")
    df.rename(columns={"id": "position_id"}, inplace=True)
    
    # Keep only relevant columns and drop rows with missing values
    df = df[["location_id", "position_id"]].dropna().astype(int)
    
    # Remove duplicate location-position pairs
    df = df.drop_duplicates()
    
    # Add default values for max_openings and filled_openings
    df["max_openings"] = 1
    df["filled_openings"] = 0
    
    # Insert data into PostgreSQL
    table_name = 'locations_positions'
    df.to_sql(table_name, engine, if_exists='append', index=False)
    
    print("Locations-Positions relationships inserted successfully!")
else:
    print("No Excel files found in the directory.")
