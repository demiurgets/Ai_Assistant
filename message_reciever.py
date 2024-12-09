from flask import Flask, request, jsonify
import re
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
from DataAccessLayer.services.positionServices import get_positions_by_location
from DataAccessLayer.services.candidateServices import (find_or_create_candidate_json, update_conversation, save_to_database, get_corresponding_assistant, upgrade_candidate)

from AI.openai_utils import OpenAIUtility



# Initialize Flask app
app = Flask(__name__)

# Load the .env file
load_dotenv()

dbname = os.getenv('dbname')
user = os.getenv('user')
password = os.getenv('password')
host = os.getenv('host')
port = os.getenv('pg_port')

api_key = os.getenv('API_KEY')
reader_id = os.getenv('ASST_ID_READER')
interviewer_id = os.getenv('ASST_INTERVIEWER')
admin_assistant_id = os.getenv('ASST_ADMIN')

database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"

engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
db_session = Session()

openAiUtils = OpenAIUtility()

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
        "using all the information you just received, generate ONLY a JSON object with the following fields: first_name, last_name, email, location_id, position_id, age, city, state, zip, experience, lead_source, availability. Please write the ID integer for the position."
    )
    # Send the user query
    message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=query)
    # Poll until the run is completed
    run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=interviewer_id)
    
    # Default response in case of failure
    response = "Error with AI API"
    json_data = None
    
    if run.status == 'completed':
        # Retrieve the response page after run completion
        response_page = client.beta.threads.messages.list(thread_id=thread_id)
        response = response_page.data[0].content[0].text.value
        print(response)

        try:
            # Regex to find any JSON object: it looks for a string starting with `{` and ending with `}`, 
            # containing a valid JSON-like structure (not a foolproof guarantee but a common approach)
            json_pattern = r'\{.*?\}'  # Match any content inside curly braces
            match = re.search(json_pattern, response, re.DOTALL)
            
            if match:
                # Extract the matched JSON string
                clean_response = match.group(0).strip()
                print(f"Extracted JSON string: {repr(clean_response)}")  # Debugging: Show the cleaned JSON string
                
                # Attempt to load the cleaned JSON string
                json_data = json.loads(clean_response)
                print(f"Parsed JSON: {json_data}")  # Debugging: Show parsed JSON
                
                # Ensure all required fields are present in the parsed JSON data
                required_fields = ["first_name", "last_name", "email", "phone", "age", "position_id", 
                                   "experience", "lead_source", "availability", "status", "assistant_thread_id"]
                
                for field in required_fields:
                    if field not in json_data:
                        json_data[field] = None  # Set to None if not present
                
            else:
                print("No JSON found in the response.")
        
        except json.JSONDecodeError as e:
            print(f"JSON decoding error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    return json_data

def assistant_get_positions(thread_id, text):
    numbers = re.findall(r'\d+', text)
    location_id = int(numbers[0]) if numbers else None
      # If a valid location_id is found, retrieve positions for that location
    response = ""
    if location_id is not None:
        positions = get_positions_by_location(location_id)
        positions_json = json.dumps(
            positions,
            default=lambda obj: obj.isoformat() if isinstance(obj, datetime) else str(obj)  # Handle datetime serialization
        )
        print("Queried positions!")
        query = (
            "Here are all the positions for the location, please present each with a short summary to the user and remember the position ID of their choice: " + positions_json
        )
        
        response = openAiUtils.send_to_ai(query, thread_id, interviewer_id)
        return response
    else:
        return response

    
def detect_trigger_string(text, thread_id, phoneNumber):
    ending_trigger = "ending_phrase_trigger"
    location_trigger = "location_phrase_trigger"
    if location_trigger in text.lower():
        print("Location string triggered")
        positions = assistant_get_positions(thread_id, text)
        
        return positions

    if ending_trigger in text.lower():
        print("ending string TRIGGERED")
        print(text)
        candidate_json_data = assistant_generate_json(thread_id)  
        candidate_json_data["phone"] = phoneNumber
        candidate_json_data["thread_id"] = thread_id

        save_to_database(candidate_json_data)

#upgrading the candidate will update the JSON with the status and a new thread ID for detailed screening
        upgrade_candidate(phoneNumber)
        text_without_trigger = text.lower().replace(ending_trigger, "").strip()
        return text_without_trigger
    return text



#I should probably update this so it only queries for the candidate/phone number once instead of multiple times per message

def recieve_message(query, phoneNumber):
    candidate_json = find_or_create_candidate_json(phoneNumber)
    assistant_id = get_corresponding_assistant(phoneNumber)

    print(assistant_id)
    response = ""
    response = openAiUtils.send_to_ai(query, candidate_json["thread_id"], assistant_id)

    #if positions are queried they will be returned here for the user to see
    triggerResponse = detect_trigger_string(response, candidate_json["thread_id"], phoneNumber)
    
    combined_response = f"{response}\n{triggerResponse}" if triggerResponse else response

    # Update the conversation with the combined response
    update_conversation(phoneNumber, query, triggerResponse)
    
    # Return the combined response
    return triggerResponse
    


#ALL THESE METHOD CALLS ARE FOR LOCAL TESTING 

#detect_trigger_string("have a great day please", "thread_6jMNCZI3AuJqZbciEuau9VKL", "19153528343")
#recieve_message("hi there", "967 658-4442")
#json_data = {'first_name': 'Michael', 'last_name': 'Soprano', 'email': 'mikey123@gmail.com', 'phone': '', 'age': 33, 'city': 'Houston', 'state': 'Texas', 'zip': '', 'experience': '3 years', 'lead_source': 'Facebook ad', 'availability': 'Next weekend', 'location': None, 'status': None, 'assistant_thread_id': None}
#save_to_database(json_data, "915 658-4442", "thread_oJuzEbVFPfrm9chyUI0rIcME")

