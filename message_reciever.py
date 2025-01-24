from flask import Flask, request, jsonify
import re
import numpy as np
import json
import faiss
from transformers import AutoTokenizer, AutoModel
from openai import OpenAI
import os
from dotenv import load_dotenv
import subprocess
import streamlit as st
import psycopg2
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine
from DataAccessLayer.models.candidates import Candidates
from DataAccessLayer.models.assistants import Assistants

from DataAccessLayer.services.candidateServices import (find_or_create_candidate_json, update_conversation, save_to_database, get_corresponding_assistant, upgrade_candidate)
from DataAccessLayer.services.assistantServices import (assistant_get_positions, assistant_get_locations)

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

api_key = os.getenv('OPENAI_KEY')
reader_id = os.getenv('ASST_ID_READER')
interviewer_id = os.getenv('ASST_INTERVIEWER')
admin_assistant_id = os.getenv('ASST_ADMIN')

database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)

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


#def get_embedding(text):
#    print("empty func")
#def search(query, result_length=5):
#    query_embedding = get_embedding(query).reshape(1, -1)
#    D, I = index.search(query_embedding, k=result_length)
#    
#    if all(i < len(document_metadata) for i in I[0]):
#        results = [document_metadata[i] for i in I[0]]
#    else:
#        results = []
#    
#    return results


#def embeddings_search(query, response_length):
#    client = OpenAI(api_key=api_key)
#    thread = client.beta.threads.create()
#    context_results = search(query)
#    context_str = "\n\n".join([f"Title: {result['title']}\nChunk ID: {result['chunk_id']}\nContent: {result['content']}" for result in context_results])
#    message = client.beta.threads.messages.create(thread_id=thread.id, role="user", content=f"Analyze: {context_str} to answer: {query} in {response_length}")
#    run = client.beta.threads.runs.create_and_poll(thread_id=thread.id, assistant_id=reader_id)
#    if run.status == 'completed':
#        response_page = client.beta.threads.messages.list(thread_id=thread.id)
#        return response_page.data[0].content[0].text.value
#    return "Error processing request with AI Assistant"



def assistant_generate_json(thread_id, assistant_id):
    client = OpenAI(api_key=api_key)
    query = (
        "using all the information you just received, generate ONLY a JSON object with the following fields: language, first_name, last_name, phone, email, location_id, position_id, age, city, state, zip, experience, lead_source, availability, lead_source_id. Please write the ID integer for the position, location, and lead_source_id. To get lead source ID follow this mapping: 1: linkedin, 2 - facebook, 3-  instagram, 4- indeed, 5- google, 6- referral, 7- website, 8- other"
    )
    # Send the user query
    message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=query)
    # Poll until the run is completed
    run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=assistant_id)
    
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


def detect_trigger_string(text, thread_id, candidate_identifier, asstId):
    ending_trigger = "ending_phrase_trigger"
    location_trigger = "location_phrase_trigger"
    position_trigger = "position_phrase_trigger"
    phone_trigger = "phone_phrase_trigger"

    if location_trigger in text.lower():
        print("Location string triggered")
        positions = assistant_get_positions(thread_id, text, asstId)
        return positions
    
    if phone_trigger in text.lower():
        if len(candidate_identifier) < 16:
            ask_for_phone = False
        else:
            ask_for_phone = True
        return ask_for_phone

    if position_trigger in text.lower():
        print("Position string triggered")
        locations = assistant_get_locations(thread_id, text, asstId)
        return locations

    if ending_trigger in text.lower():
        print("ending string TRIGGERED")
        print(text)
        candidate_json_data = assistant_generate_json(thread_id, asstId)  
        if len(candidate_identifier) < 16:
            candidate_json_data["phone"] = candidate_identifier
            
        candidate_json_data["candidate_identifier"] = candidate_identifier
        candidate_json_data["thread_id"] = thread_id

        save_to_database(candidate_json_data)
#upgrading the candidate will update the JSON with the status and a new thread ID for detailed screening
        upgrade_candidate(candidate_identifier, candidate_json_data)
        text_without_trigger = text.lower().replace(ending_trigger, "").strip()
        return text_without_trigger
    return text



#I should probably update this so it only queries for the candidate/phone number once instead of multiple times per message

def recieve_message(query, candidate_identifier):
    candidate_json = find_or_create_candidate_json(candidate_identifier)
    assistant_id = get_corresponding_assistant(candidate_identifier)

    print(assistant_id)
    response = ""
    response = openAiUtils.send_to_ai(query, candidate_json["thread_id"], assistant_id)

    #if positions are queried they will be returned here for the user to see
    triggerResponse = detect_trigger_string(response, candidate_json["thread_id"], candidate_identifier, assistant_id)
    
    # Update the conversation with the combined response
    update_conversation(candidate_identifier, query, triggerResponse)
    
    # Return the combined response
    return triggerResponse
    


#ALL THESE METHOD CALLS ARE FOR LOCAL TESTING 

#detect_trigger_string("have a great day please", "thread_6jMNCZI3AuJqZbciEuau9VKL", "19153528343")
#recieve_message("hi there", "967 658-4442")
#json_data = {'first_name': 'Michael', 'last_name': 'Soprano', 'email': 'mikey123@gmail.com', 'phone': '', 'age': 33, 'city': 'Houston', 'state': 'Texas', 'zip': '', 'experience': '3 years', 'lead_source': 'Facebook ad', 'availability': 'Next weekend', 'location': None, 'status': None, 'assistant_thread_id': None}
#save_to_database(json_data, "915 658-4442", "thread_oJuzEbVFPfrm9chyUI0rIcME")

