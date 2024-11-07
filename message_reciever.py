from flask import Flask, request, jsonify
import numpy as np
import json
import faiss
import torch
from transformers import AutoTokenizer, AutoModel
from openai import OpenAI
import os
from dotenv import load_dotenv
import subprocess
import streamlit as st
import psycopg2
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from DataAccessLayer.models.candidates import Candidates


# Initialize Flask app
app = Flask(__name__)

# Load the .env file
load_dotenv()

dbname = os.getenv('dbname')
user = os.getenv('user')
password = os.getenv('password')
host = os.getenv('host')
port = os.getenv('port')

api_key = os.getenv('API_KEY')
reader_id = os.getenv('ASST_ID_READER')
interviewer_id = os.getenv('ASST_INTERVIEWER')
admin_assistant_id = os.getenv('ASST_ADMIN')

database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"

engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
db_session = Session()

# Load config and data
#document_embeddings = np.load('Stored_context/applicant_embeddings.npy')
#with open('Stored_context/document_chunks.json', 'r') as f:
#    document_metadata = json.load(f)

# Set up FAISS index
#dimension = document_embeddings.shape[1]
#index = faiss.IndexFlatL2(dimension)
#index.add(document_embeddings)

# Load model and tokenizer
#model_name = "sentence-transformers/all-MiniLM-L6-v2"
#tokenizer = AutoTokenizer.from_pretrained(model_name)
#model = AutoModel.from_pretrained(model_name)

def get_postgres_connection():
    try:
        conn = psycopg2.connect(
            dbname=dbname, 
            user=user, 
            password=password, 
            host=host, 
            port=port
        )
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None

def get_embedding(text):
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

def search(query, result_length=5):
    query_embedding = get_embedding(query).reshape(1, -1)
    D, I = index.search(query_embedding, k=result_length)
    
    if all(i < len(document_metadata) for i in I[0]):
        results = [document_metadata[i] for i in I[0]]
    else:
        results = []
    
    return results

def assistant_response(thread_id, query, response_length):
    client = OpenAI(api_key=api_key)
    message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=query)
    run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=interviewer_id)
    if run.status == 'completed':
        response_page = client.beta.threads.messages.list(thread_id=thread_id)
        return response_page.data[0].content[0].text.value
    return "Error processing request with AI Assistant"

def embeddings_search(query, response_length):
    client = OpenAI(api_key=api_key)
    thread = client.beta.threads.create()
    context_results = search(query)
    context_str = "\n\n".join([f"Title: {result['title']}\nChunk ID: {result['chunk_id']}\nContent: {result['content']}" for result in context_results])
    message = client.beta.threads.messages.create(thread_id=thread.id, role="user", content=f"Analyze: {context_str} to answer: {query} in {response_length}")
    run = client.beta.threads.runs.create_and_poll(thread_id=thread.id, assistant_id=reader_id)
    if run.status == 'completed':
        response_page = client.beta.threads.messages.list(thread_id=thread.id)
        return response_page.data[0].content[0].text.value
    return "Error processing request with AI Assistant"

def assistant_generate_json(thread_id):
    client = OpenAI(api_key=api_key)
    query = (
        "using all the information you just received, generate ONLY a JSON object with the following fields: first_name, last_name, email, phone, age, city, state, zip, experience, lead_source, availability (in date range)"
    )
    
    message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=query)
    run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=interviewer_id)
    
    response = "Error with AI API"
    if run.status == 'completed':
        response_page = client.beta.threads.messages.list(thread_id=thread_id)
        response = response_page.data[0].content[0].text.value
        print(response)
        json_data = json.loads(response)
        
        # Ensure all required fields are present in the JSON data
        required_fields = ["first_name", "last_name", "email", "phone", "age", "location", 
                           "experience", "lead_source", "availability", "status", "assistant_thread_id"]
        
        for field in required_fields:
            if field not in json_data:
                json_data[field] = None  # Set to None if not present

    
    return json_data

def detect_trigger_string(text, thread_id, phoneNumber):
    trigger_phrase = "have a great day"
    if trigger_phrase in text.lower():
        print("trigger string TRIGGERED")
        json_data = assistant_generate_json(thread_id)  
        print(json_data)
        save_to_database(json_data, phoneNumber, thread_id)

        return True
    return False

def save_to_database(json_data, phone_number, thread):
    print("Saving candidate to the database...")

    candidate = db_session.query(Candidates).filter_by(phone=phone_number).first()

    if candidate:
        print("Candidate already exists.")
        return

    new_candidate = Candidates()
    setattr(new_candidate, 'phone', phone_number)
    setattr(new_candidate, 'thread_id', thread)

    for key, value in json_data.items():
        if hasattr(new_candidate, key):
            setattr(new_candidate, key, value if value != "" else None)
        else:
            print(f"Warning: '{key}' not a valid attribute of Candidate. Skipping.")

    if not hasattr(new_candidate, 'status_id'):
        setattr(new_candidate, 'status_id', json_data.get('status', 0))

    try:
        db_session.add(new_candidate)
        db_session.commit()
        print("Candidate saved successfully.")
    except SQLAlchemyError as e:
        print(f"Error saving candidate: {e}")
        db_session.rollback()



def load_candidates_data(phone_number):
    # Load JSON data from file or create an empty list if the file doesn't exist
    json_file_path = "Stored_context/applicants_in_progress/" + phone_number + ".json"

    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as f:
            data = json.load(f)
            # Ensure that the data is a list
            if isinstance(data, list):
                return data
            else:
                return []  # If the JSON is not a list, return an empty list
    return []

def save_candidates_data(data, phone_number):
    json_file_path = "Stored_context/applicants_in_progress/" + phone_number + ".json"

    # Save JSON data to file
    with open(json_file_path, 'w') as f:
        json.dump(data, f, indent=4)

def add_new_candidate(phone_number, thread_id):
    data = load_candidates_data(phone_number)
    
    new_entry = {
        "phone_number": phone_number,
        "thread_id": thread_id,
        "first_contact_timestamp": datetime.now().isoformat(),
        "conversation": []  
    }
    
    data.append(new_entry)
    save_candidates_data(data, phone_number)

def update_conversation(phone_number, user_message, assistant_response):
    data = load_candidates_data(phone_number)
    for candidate in data:
        if candidate["phone_number"] == phone_number:
            # Get the current message count and increment for each new message
            message_id = len(candidate["conversation"]) + 1
            
            candidate["conversation"].append({
                "message_id": message_id,  # Add the new message ID
                "timestamp": datetime.now().isoformat(),
                "message": user_message,
                "role": "external_user"
            })
            candidate["conversation"].append({
                "message_id": message_id + 1,  # Add the new message ID
                "timestamp": datetime.now().isoformat(),
                "message": assistant_response,
                "role": "assistant"
            })
            break
    save_candidates_data(data, phone_number)


def find_candidate_by_phone(phone_number):
    data = load_candidates_data(phone_number)
    for candidate in data:
        if candidate["phone_number"] == phone_number:
            return candidate
    return None

def recieve_message(query, phoneNumber):
    key = api_key
    asstId = interviewer_id
    client = OpenAI(api_key=key)

    candidate = find_candidate_by_phone(phoneNumber)
    if candidate:
        thread_id = candidate['thread_id']
        print("Candidate already exists in the database.")


    else:
        # Create a new thread and add a new candidate to the JSON file
        client = OpenAI(api_key=api_key)
        thread = client.beta.threads.create()
        thread_id = thread.id
        add_new_candidate(phoneNumber, thread_id)
        
    response = ""

    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=query
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=asstId,
    )
    response = "Error with AI API"
    if run.status == 'completed':
        response_page = client.beta.threads.messages.list(thread_id=thread_id)
        response = response_page.data[0].content[0].text.value
        
    else:
        response = "Error processing request with OpenAI"

    update_conversation(phoneNumber, query, response)
    detect_trigger_string(response, thread_id, phoneNumber)
    
    print(response)
    return response


#ALL THESE METHOD CALLS ARE FOR LOCAL TESTING 

detect_trigger_string("have a great day please", "thread_oJuzEbVFPfrm9chyUI0rIcME", "915 658-4442")
#recieve_message("hi there", "967 658-4442")
#json_data = {'first_name': 'Michael', 'last_name': 'Soprano', 'email': 'mikey123@gmail.com', 'phone': '', 'age': 33, 'city': 'Houston', 'state': 'Texas', 'zip': '', 'experience': '3 years', 'lead_source': 'Facebook ad', 'availability': 'Next weekend', 'location': None, 'status': None, 'assistant_thread_id': None}
#save_to_database(json_data, "915 658-4442", "thread_oJuzEbVFPfrm9chyUI0rIcME")

