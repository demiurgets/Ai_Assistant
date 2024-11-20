import json
import os
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

type_map = {
    "SERIAL": Integer,
    "INT": Integer,
    "FLOAT": Float,
    "BOOLEAN": Boolean,
    "TEXT": Text,
    "DATE": Date,
    "TIMESTAMP": DateTime,
}

def parse_column_type(col_type):
    """Parse the column type from JSON schema, returning the class or parameterized class."""
    if col_type.startswith("VARCHAR"):
        length = int(col_type[col_type.find("(") + 1 : col_type.find(")")])
        return String, (length,)
    return type_map.get(col_type, String), ()  

def load_schema(schema_path):
    """Load JSON schema from a file."""
    with open(schema_path) as f:
        return json.load(f)

def create_model_class_code(table_name, columns):
    """Generate the Python code for a SQLAlchemy model class."""
    class_code = f"class {table_name.capitalize()}(Base):\n"
    class_code += f"    __tablename__ = '{table_name}'\n\n"

    # Add import for func at the top of the file (only once)

    for col in columns:
        col_type, col_args = parse_column_type(col["type"])
        col_def = f"    {col['name']} = Column({col_type.__name__}"

        if col_args:
            col_def += f"({', '.join(map(str, col_args))})"
        
        # If there's a ForeignKey, place it first
        foreign_key = col.get("foreign_key")
        if foreign_key:
            ref_table, ref_column = foreign_key["references"].split("(")
            ref_column = ref_column[:-1]
            col_def += f", ForeignKey('{ref_table.strip()}.{ref_column.strip()}')"
        
        # After foreign_key, add other keyword arguments like nullable, unique, etc.
        if col.get("primary_key"):
            col_def += ", primary_key=True"
        if col.get("unique"):
            col_def += ", unique=True"
        if col.get("not_null"):
            col_def += ", nullable=False"
        else:
            col_def += ", nullable=True"
        if col.get("default"):
            # Handle default for CURRENT_TIMESTAMP and CURRENT_DATE
            if col['default'] == "CURRENT_TIMESTAMP":
                col_def += f", default=func.current_timestamp()"
            elif col['default'] == "CURRENT_DATE":
                col_def += f", default=func.current_date()"
            else:
                col_def += f", default={col['default']}"

        col_def += ")"
        class_code += col_def + "\n"

    class_code += "\n"
    return class_code

def generate_model_files(schema, output_dir="models"):
    """Generate Python files for each table in the schema."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for table in schema["tables"]:
        table_name = table["name"]
        columns = table["columns"]

        model_code = (
            "from sqlalchemy import Column, Integer, String, Float, Text, Boolean, Date, DateTime, ForeignKey\n"
            "from sqlalchemy.ext.declarative import declarative_base\n\n"
            "from models import Base\n\n"
            "from sqlalchemy import func\n\n"
        )
        model_code += create_model_class_code(table_name, columns)

        file_path = os.path.join(output_dir, f"{table_name}.py")
        with open(file_path, "w") as f:
            f.write(model_code)

        print(f"Model file created for table '{table_name}': {file_path}")  # Debug print

def main():
    schema = load_schema("newSchema.json")  # Load schema from JSON file
    print(f"Loaded schema: {json.dumps(schema, indent=4)}")  # Debug print for loaded schema
    generate_model_files(schema)  # Generate model files

if __name__ == "__main__":
    main()
