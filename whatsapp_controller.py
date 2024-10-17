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

# Initialize Flask app
app = Flask(__name__)

# Load the .env file
load_dotenv()

api_key = st.secrets["api_keys"]["API_KEY"]
reader_id = st.secrets["api_keys"]["ASST_ID_READER"]
interviewer_id = st.secrets["api_keys"]["ASST_INTERVIEWER"]
admin_assistant_id = st.secrets["api_keys"]["ASST_ADMIN"]

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
            dbname='qonda', 
            user='postgres', 
            password='Not24get!', 
            host='localhost', 
            port=5432
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
        "using all the information you just received, generate ONLY a JSON object with the following fields: first_name, last_name, email, phone, age, city, state, zip, experience, lead_source, availability"
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
        move_single_conversation(phoneNumber)

        return True
    return False

def move_single_conversation(phone_number):
    # Load the JSON data
    data = load_candidates_data()
    
    for candidate in data:
        if candidate["phone_number"] == phone_number:
            move_conversation_to_database(candidate)
            candidate["conversation"] = []
            break
    save_candidates_data(data)

def move_conversation_to_database(candidate):
    print("Saving conversation to the database...")
    conn = get_postgres_connection()
    if not conn:
        return

    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE candidates
            SET conversation = %s
            WHERE phone = %s
        ''', (
            json.dumps(candidate["conversation"]),  
            candidate["phone_number"]
        ))
        conn.commit()
        print("Conversation saved successfully.")
    except Exception as e:
        print(f"Error saving conversation: {e}")
    
    cursor.close()
    conn.close()



def save_to_database(json_data, phoneNumber, thread):
    print("Saving candidate to the database...")
    conn = get_postgres_connection()
    if not conn:
        return

    cursor = conn.cursor()

    for key, value in json_data.items():
        if value == "":
            json_data[key] = None

    try:
        cursor.execute('''
            INSERT INTO candidates (first_name, last_name, email, phone, assistant_thread_id, age, location, experience, lead_source, availability, status, assistant_thread_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            
        ''', (
            json_data['first_name'],
            json_data['last_name'],
            json_data['email'],
            phoneNumber,
            thread_id,
            json_data['age'],
            json_data['location'],
            json_data['experience'],
            json_data['lead_source'],
            json_data['availability'],
            json_data.get('status', 'pending'),  # Default to 'pending' if status is not provided
            json_data.get('assistant_thread_id', None)
        ))

        conn.commit()
        print("Candidate saved successfully.")
    except Exception as e:
        print(f"Error saving candidate: {e}")
    
    cursor.close()
    conn.close()


def load_candidates_data():
    # Load JSON data from file or create an empty list if the file doesn't exist
    json_file_path = "Stored_context/screening_applicants.json"

    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as f:
            data = json.load(f)
            # Ensure that the data is a list
            if isinstance(data, list):
                return data
            else:
                return []  # If the JSON is not a list, return an empty list
    return []
def save_candidates_data(data):
    json_file_path = "Stored_context/screening_applicants.json"

    # Save JSON data to file
    with open(json_file_path, 'w') as f:
        json.dump(data, f, indent=4)

def add_new_candidate(phone_number, thread_id):
    # Add a new candidate with phone number, thread ID, and timestamp
    data = load_candidates_data()
    
    new_entry = {
        "phone_number": phone_number,
        "thread_id": thread_id,
        "first_contact_timestamp": datetime.now().isoformat(),
        "conversation": []  # Initialize an empty list for the conversation
    }
    
    data.append(new_entry)
    save_candidates_data(data)

def update_conversation(phone_number, user_message, assistant_response):
    data = load_candidates_data()
    for candidate in data:
        if candidate["phone_number"] == phone_number:
            # Get the current message count and increment for each new message
            message_id = len(candidate["conversation"]) + 1
            
            candidate["conversation"].append({
                "message_id": message_id,  # Add the new message ID
                "timestamp": datetime.now().isoformat(),
                "user_message": user_message,
                "assistant_response": assistant_response
            })
            break
    save_candidates_data(data)


def find_candidate_by_phone(phone_number):
    data = load_candidates_data()
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



@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    message_body = data['Body']
    response_length = 150
    thread_id = data.get('thread_id')

    if message_body.lower().startswith("tell me"):
        assistant_response_text = embeddings_search(message_body, response_length)
    else:
        if thread_id is None:
            client = OpenAI(api_key=api_key)
            thread = client.beta.threads.create()
            thread_id = thread.id
        assistant_response_text = assistant_response(thread_id, message_body, response_length)

    triggered, trigger_response = detect_trigger_string(assistant_response)

#detect_trigger_string("have a great day please", "thread_oOz3DgD3hC0tsRssL9am1u5O", "915 332-3235")
recieve_message("localization please", "935 338-3235")

#save_to_database(json_data, "915 352-323")

