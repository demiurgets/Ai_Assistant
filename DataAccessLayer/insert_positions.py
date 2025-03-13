import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine
from datetime import datetime

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
        'description': 'object',
        'date_created': 'object',
        'date_updated': 'object',
        'key_responsibilities': 'object',
        'qualifications': 'object',
        'benefits': 'object',
        'salary_range': 'object',
        'salary_currency': 'object',
        'salary_period': 'object',
        'job_type': 'object',
        'location_type': 'object',
        'date_created': 'datetime64',
        'date_updated': 'datetime64'
    }
    
    df = pd.read_excel(os.path.join('excel_file_context', excel_files[0]), sheet_name="Positions", dtype=dtype_dict)    
    
    # Helper function to convert concatenated strings to PostgreSQL array format
    def to_pg_array(series):
        return '{' + ','.join(f'"{str(val).strip()}"' for val in series if pd.notnull(val) and str(val).strip()) + '}'
    
    ### Merge all individual key_responsibilities, qualifications and benefits columns
    ### from the excel file to a pg-friendly array format to insert the array to the db
    
    key_columns = [col for col in df.columns if col.startswith('key')]
    df['key_responsibilities'] = df[key_columns].apply(lambda row: to_pg_array(row), axis=1)
    df.drop(columns=key_columns, inplace=True)
    
    qualification_columns = [col for col in df.columns if col.startswith('qualification')]
    df['qualifications'] = df[qualification_columns].apply(lambda row: to_pg_array(row), axis=1)
    df.drop(columns=qualification_columns, inplace=True)
    
    benefit_columns = [col for col in df.columns if col.startswith('benefit')]
    df['benefits'] = df[benefit_columns].apply(lambda row: to_pg_array(row), axis=1)
    df.drop(columns=benefit_columns, inplace=True)
    
    new_column_names = ['id','name', 'job_type', 'location_type', 'description', 'working_hours', 'salary_range', 'salary_currency', 'salary_period', 'key_responsibilities', 'qualifications', 'benefits']
    df.columns = new_column_names
    
    # Add the 'is_active' column with a default value of True
    df['is_active'] = True
    
    # Add the default timestamp columns
    df['date_created'] = datetime.now()
    df['date_updated'] = datetime.now()
    
    print(df.head(10))
else:
    print("No Excel files found in the directory.")

col_names = list(df.columns)
print(col_names)
print(df.dtypes)

# Insert data into positions table in pg
table_name = 'positions'
df.to_sql(table_name, engine, if_exists='append', index=False)

print("Positions inserted successfully!")
