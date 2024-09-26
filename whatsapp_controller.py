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
import sqlite3

# Initialize Flask app
app = Flask(__name__)

# Load the .env file
load_dotenv()


api_key = st.secrets["api_keys"]["API_KEY"]
reader_id = st.secrets["api_keys"]["ASST_ID_READER"]
interviewer_id = st.secrets["api_keys"]["ASST_INTERVIEWER"]
admin_assistant_id = st.secrets["api_keys"]["ASST_ADMIN"]

# Load config and data
document_embeddings = np.load('Stored_context/applicant_embeddings.npy')
with open('Stored_context/document_chunks.json', 'r') as f:
    document_metadata = json.load(f)

# Set up FAISS index
dimension = document_embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(document_embeddings)

# Load model and tokenizer
model_name = "sentence-transformers/all-MiniLM-L6-v2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

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
    key = api_key
    asstId = interviewer_id
    client = OpenAI(api_key=key)
    query = "Using all the information you just received, generate a JSON with the following fields: name, age, location, position, experience, availability, lead source, contact."
    message = client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=query
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id, assistant_id=asstId,
    )
    response = "Error with AI API"
    if run.status == 'completed':
        response_page = client.beta.threads.messages.list(thread_id=thread_id)
        response = response_page.data[0].content[0].text.value
    else:
        response = "Error processing request with AI Assistant"
    return response

def detect_trigger_string(text, thread_id, phoneNumber):
    """Detect 'have a great day' string and trigger AI assistant."""
    print(text)
    trigger_phrase = "have a great day"
    if trigger_phrase in text.lower():
        print("trigger string TRIGGERED")
        json_response = assistant_generate_json(thread_id)
        json_data = json.loads(json_response)
        print(json_data)
        #save to db here
        save_to_database(json_data, phoneNumber)
        return True
    return False

def save_to_database(json_data, phoneNumber):

    conn = sqlite3.connect('Stored_context/applicants.db')
    cursor = conn.cursor()

    # Check if an applicant with the given phone number exists
    cursor.execute('SELECT * FROM applicants WHERE contact = ?', (phoneNumber,))
    existing_applicant = cursor.fetchone()

    if existing_applicant:
        # Update the existing record with the new JSON data
        cursor.execute('''
            UPDATE applicants
            SET name = ?,
                age = ?,
                location = ?,
                position = ?,
                experience = ?,
                availability = ?,
                lead_source = ?
            WHERE contact = ?
        ''', (
            json_data['name'],
            json_data['age'],
            json_data['location'],
            json_data['position'],
            json_data['experience'],
            json_data['availability'],
            json_data['lead_source'],
            phoneNumber
        ))
    else:
        # Insert the JSON data into the applicants table
        cursor.execute('''
            INSERT INTO applicants (name, age, location, position, experience, lead_source, contact)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            json_data['name'],
            json_data['age'],
            json_data['location'],
            json_data['position'],
            json_data['experience'],
            json_data['lead_source'],
            phoneNumber
        ))

    conn.commit()
    conn.close()

def recieve_query_from_whatsapp(query, phoneNumber):
    import sqlite3
    phoneNumber = '9512238384'
    # Connect to the database (or create it if it doesn't exist)
    conn = sqlite3.connect('Stored_context/applicants.db')
    cursor = conn.cursor()

    # Create a table for applicants
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applicants (
            id INTEGER,
            name TEXT,
            age INTEGER,
            location TEXT,
            position TEXT,
            experience TEXT,
            lead_source TEXT,
            contact TEXT,
            thread TEXT
        )
    ''')

    # Check if an applicant with the given phone number exists
    cursor.execute('SELECT * FROM applicants WHERE contact = ?', (phoneNumber,))
    existing_applicant = cursor.fetchone()


    key = api_key
    asstId = interviewer_id
    client = OpenAI(api_key=key)
    response = ""

    if existing_applicant:
        print("Applicant already exists in the database.")
        # Access the applicant's details using existing_applicant variable
        thread_id = existing_applicant[8]  # Assuming thread is at index 8 in the table
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content= query
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

        conn.commit()
        conn.close()
        detect_trigger_string(response, thread_id, phoneNumber)

    else:
        print("new applicant")
        thread = client.beta.threads.create() 
        cursor.execute('INSERT INTO applicants (contact, thread) VALUES (?, ?)', (phoneNumber, thread.id))
        conn.commit()

        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content= query
        )
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=asstId,
        )
        response = "Error with AI API"
        if run.status == 'completed':
            response_page = client.beta.threads.messages.list(thread_id=thread.id)
            response = response_page.data[0].content[0].text.value
        else:
            response = "Error processing request with OpenAI"
        conn.commit()
        conn.close()
    # Commit the changes and close the connection
    
    return response

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    message_body = data['Body']
    response_length = 150
    thread_id = data['thread_id'] if 'thread_id' in data else None

    if message_body.lower().startswith("tell me"):
        assistant_response_text = embeddings_search(message_body, response_length)
    else:
        if thread_id is None:
            client = OpenAI(api_key=api_key)
            thread = client.beta.threads.create()
            thread_id = thread.id
        assistant_response_text = assistant_response(thread_id, message_body, response_length)

    triggered, trigger_response = detect_trigger_string(assistant_response_text, thread_id)

    return jsonify({
        "reply": assistant_response_text,
        "triggered": triggered,
        "trigger_response": trigger_response
    })

json_data = {
        "name": "Tony Soprano",
        "age": 23,
        "location": "New York",
        "position": "Legal Assistant",
        "experience": "Passed the bar exam",
        "lead_source": "LinkedIn ad",
        "availability": "This weekend",
        "contact": "123 449 2421"
    }
save_to_database(json_data, '19153528343')