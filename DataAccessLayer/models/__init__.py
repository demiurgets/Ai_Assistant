import os
import importlib
from sqlalchemy.orm import declarative_base

Base = declarative_base()  # Make sure Base is available to all models

model_files = [f for f in os.listdir(os.path.dirname(__file__)) if f.endswith('.py') and f != '__init__.py']
for model_file in model_files:
    print(f"Importing {model_file[:-3]}")  # Print the model being imported
    importlib.import_module(f".{model_file[:-3]}", package="DataAccessLayer.models")
