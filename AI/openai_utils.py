import os
import json
import numpy as np
import torch
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from transformers import AutoTokenizer, AutoModel
import psycopg2
from DataAccessLayer.models.candidates import Candidates

# Load environment variables
load_dotenv()

class OpenAIUtility:
    def __init__(self):
        # Database configuration
        self.dbname = os.getenv('dbname')
        self.user = os.getenv('user')
        self.password = os.getenv('password')
        self.host = os.getenv('host')
        self.port = os.getenv('port')

        # OpenAI API configuration
        self.api_key = os.getenv('API_KEY')
        self.reader_id = os.getenv('ASST_ID_READER')
        self.interviewer_id = os.getenv('ASST_INTERVIEWER')

        # Database engine
        database_url = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)

        # Load transformer model
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)

    def get_postgres_connection(self):
        try:
            conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            return conn
        except Exception as e:
            print(f"Error connecting to PostgreSQL: {e}")
            return None

    def get_embedding(self, text):
        inputs = self.tokenizer(text, return_tensors='pt', padding=True, truncation=True)
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

    def create_thread(self):
        client = OpenAI(api_key=self.api_key)
        thread = client.beta.threads.create()
        return thread.id

    def assistant_response(self, thread_id, query):
        client = OpenAI(api_key=self.api_key)
        message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=query)
        run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=self.interviewer_id)
        if run.status == 'completed':
            response_page = client.beta.threads.messages.list(thread_id=thread_id)
            return response_page.data[0].content[0].text.value
        return "Error processing request with AI Assistant"

    def generate_json_from_thread(self, thread_id):
        client = OpenAI(api_key=self.api_key)
        query = (
            "Using all the information you just received, generate ONLY a JSON object with the following fields: "
            "first_name, last_name, email, phone, position, age, city, state, zip, experience, lead_source, availability "
            "(in date range). Please write the ID integer for the position."
        )
        message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=query)
        run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=self.interviewer_id)

        if run.status == 'completed':
            response_page = client.beta.threads.messages.list(thread_id=thread_id)
            response = response_page.data[0].content[0].text.value
            return json.loads(response)
        return {}

    def save_to_database(self, json_data, phone_number, thread_id):
        session = self.Session()
        try:
            candidate = session.query(Candidates).filter_by(phone=phone_number).first()
            if candidate:
                print("Candidate already exists.")
                return

            new_candidate = Candidates(phone=phone_number, thread_id=thread_id)
            for key, value in json_data.items():
                if hasattr(new_candidate, key):
                    setattr(new_candidate, key, value if value != "" else None)

            session.add(new_candidate)
            session.commit()
            print("Candidate saved successfully.")
        except SQLAlchemyError as e:
            print(f"Error saving candidate: {e}")
            session.rollback()
        finally:
            session.close()

    def handle_trigger(self, text, thread_id, phone_number):
        trigger_phrase = "have a great day"
        if trigger_phrase in text.lower():
            print("Trigger string detected.")
            json_data = self.generate_json_from_thread(thread_id)
            self.save_to_database(json_data, phone_number, thread_id)
            return True
        return False

    def manage_conversation(self, phone_number, query):
        # Check if candidate exists
        session = self.Session()
        candidate = session.query(Candidates).filter_by(phone=phone_number).first()
        session.close()

        thread_id = candidate.thread_id if candidate else self.create_thread()

        # Send query to OpenAI
        response = self.assistant_response(thread_id, query)

        # Detect and handle trigger
        self.handle_trigger(response, thread_id, phone_number)

        return response
