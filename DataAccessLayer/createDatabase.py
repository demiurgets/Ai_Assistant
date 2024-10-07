import json
import psycopg2
from psycopg2 import sql

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

def main():
    schema_file = 'schema.json'
    json_schema = load_schema(schema_file)
    
    db_config = {
        'dbname': 'qonda',
        'user': 'postgres',
        'password': 'Not24get!',
        'host': 'localhost', 
        'port': 5432  
    }

    conn = psycopg2.connect(**db_config)
    
    try:
        for table in json_schema['tables']:
            create_query = generate_create_table_query(table)
            execute_query(conn, create_query)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
