import json
import psycopg2
from psycopg2 import sql
import streamlit as st

dbname = st.secrets["database"]["dbname"]
user = st.secrets["database"]["user"]
password = st.secrets["database"]["password"]
host = st.secrets["database"]["host"]
port = st.secrets["database"]["port"]



def load_schema(filename):
    with open(filename, 'r') as file:
        return json.load(file)

def generate_create_table_query(table):
    table_name = table['name']
    columns = table['columns']
    
    columns_sql = []
    for column in columns:
        column_def = f"{column['name']} {column['type']}"
        
        if column.get('not_null', False):
            column_def += " NOT NULL"
        
        if column.get('primary_key', False):
            column_def += " PRIMARY KEY"
        
        if column.get('unique', False):
            column_def += " UNIQUE"
        
        if 'default' in column:
            column_def += f" DEFAULT {column['default']}"
        
        if 'foreign_key' in column:
            fk = column['foreign_key']
            column_def += f" REFERENCES {fk['references']}"
        
        columns_sql.append(column_def)
    
    create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_sql)});"
    return create_table_sql

    
def execute_query(connection, query):
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        connection.commit()
        print(f"Executed: {query}")
    except Exception as e:
        connection.rollback()
        print(f"Error executing query: {query}")
        print(e)
    finally:
        cursor.close()

def findDifferences(newSchema, currentSchema):


    return {
        {
            "tables": {
                "added": ["table1", "table2"],
                "removed": ["table3"],
                "modified": {
                    "table1": {
                        "added_columns": ["new_column"],
                        "removed_columns": ["old_column"],
                        "modified_columns": {
                            "column_name": {"type": "new_type", "not_null": True}
                        }
                    }
                }
            }
        }

    }
def main():
    newSchema_file = 'newSchema.json'
    currentSchema_file = 'currentSchema.json'
    
    newSchema = load_schema(newSchema_file)
    currentSchema = load_schema(currentSchema_file)
    
    db_config = {
        'dbname': dbname,
        'user': postgres,
        'password': password,
        'host': host, 
        'port': port  
    }

    conn = psycopg2.connect(**db_config)
    queriesToExecute = ["ADD TABLE XYZ COLS ", "UPDATE TABLE POSITIONS WHERE ID = 2", "DELETE COLUMN IN users favoritecolor"]
    try:
        for table in newSchema['tables']:
            create_query = generate_create_table_query(table)
            execute_query(conn, create_query)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
