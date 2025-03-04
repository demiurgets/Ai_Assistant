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
    # Specify the data types for each column
    dtype_dict = {
        'name': 'object',
        'address': 'object',
        'city': 'object',
        'zip': 'object',
        'phone': 'object',
    }
    
    df = pd.read_excel(os.path.join('excel_file_context', excel_files[0]), sheet_name="Locations", dtype=dtype_dict)
    print(df.head(10))
    
    new_column_names = ['id', 'name', 'address', 'city', 'state', 'zip', 'phone']
    df.columns = new_column_names
    print(df.head(10))
    
    # Add the 'is_active' column with a default value of True
    df['is_active'] = True
else:
    print("No Excel files found in the directory.")

col_names = list(df.columns)
print(col_names)
print(df.dtypes)

# Insert data into locations table in pg
table_name = 'locations'
df.to_sql(table_name, engine, if_exists='append', index=False)

print("Locations inserted successfully!")
