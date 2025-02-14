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

from DataAccessLayer.services.candidateServices import (
    find_or_create_candidate_json,
    update_conversation,
    save_to_database,
    get_corresponding_assistant,
    upgrade_candidate,
    load_candidates_json
)

import openai
from langchain_openai import ChatOpenAI
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.prompts import PromptTemplate

from AI.openai_utils import OpenAIUtility


# Initialize Flask app
app = Flask(__name__)

# Load the .env file
load_dotenv()

dbname = os.getenv("dbname")
user = os.getenv("user")
password = os.getenv("password")
host = os.getenv("host")
port = os.getenv("pg_port")

api_key = os.getenv("OPENAI_KEY")
reader_id = os.getenv("ASST_ID_READER")
interviewer_id = os.getenv("ASST_INTERVIEWER")
admin_assistant_id = os.getenv("ASST_ADMIN")

database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)

openAiUtils = OpenAIUtility()


# Test function
# def test_extract_info_with_agent():
#     conversation = """
#         User: Hi, my name is John Doe.
#         Assistant: Nice to meet you, John! What's your phone number?
#         User: It's 123-456-7890.
#         Assistant: Got it. What's your email address?
#         User: My email is john.doe@example.com.
#         Assistant: Thanks! How old are you?
#         User: I'm 30 years old.
#         Assistant: Great! Where do you live?
#         User: I live in New York City, New York, and my zip code is 10001.
#         Assistant: What's your work experience?
#         User: I have 5 years of experience in software development.
#         Assistant: When are you available to start?
#         User: I'm available starting next month.
#     """

#     candidate_info = extract_info_with_agent(conversation)
#     print("EXTRACTED CANDIDATE INFO")
#     print(candidate_info)


# if __name__ == "__main__":
#     test_extract_info_with_agent()


def extract_conversation_info(latest_interaction: str, existing_info: dict) -> dict:
    """
    Extracts information from the latest message exchange and merges with existing data.
    Uses a more focused prompt for partial extraction.
    """
    # Define the response schema
    response_schemas = [
        ResponseSchema(name="first_name", description="The first name of the candidate."),
        ResponseSchema(name="last_name", description="The last name of the candidate."),
        ResponseSchema(name="age", description="The age of the candidate. It has to be a number ONLY"),
        ResponseSchema(name="email", description="The email address provided by the candidate."),
        ResponseSchema(name="experience", description="The work experience of the candidate."),
        ResponseSchema(name="lead_source", description="How the candidate found about the job posting or hiring opportunity. Only stick to the following categories: 1.- Linkedin 2.- Facebook 3.- Instagram, 4.- Indeed, 5.- Google, 6- Referral, 7.- Website, 8.- Other"),
        ResponseSchema(name="lead_source_id", description="The id of the lead_source. Only stick to the following categories: 1.- Linkedin 2.- Facebook 3.- Instagram, 4.- Indeed, 5.- Google, 6- Referral, 7.- Website, 8.- Other"),
        ResponseSchema(name="availability", description="The availability of the candidate, day of the week and what time"),
        ResponseSchema(name="city", description="The city of the agreed location between the candidate and the assistant, where the candidate is applying.",),
        ResponseSchema(name="state", description="The state of the agreed location between the candidate and the assistant, where the candidate is applying.",),
        ResponseSchema(name="phone", description="The phone number provided by the candidate."),
        ResponseSchema(name="location_id", description="The id of the location in which the candidate is interested in applying",),
        ResponseSchema(name="position_id", description="The id of the position the candidate is interested in applying for.",),
        ResponseSchema(name="assistant_confirmation", description="The assistant's final confirmation that the job application and the candidate's information has been submitted. If the assistant confirms the application has been submitted, set this to true. If the assistant has not mentioned any of this explicitly, set this to false. If the assistant does not provide a job application submission final confirmation, set this to false.",)
    ]
    
    output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
    format_instructions = output_parser.get_format_instructions()

    prompt_template = """Analyze this conversation snippet and extract ANY candidate details you can find. 
    Only return values that are explicitly mentioned. If a field isn't mentioned, leave it blank.
    
    {format_instructions}
    
    Existing known information (don't repeat these unless new information is provided):
    {existing_info}
    
    Ovewrite if new information is provided.
    
    Latest conversation snippet:
    {latest_interaction}"""

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["latest_interaction", "existing_info"],
        partial_variables={"format_instructions": format_instructions},
    )

    llm = ChatOpenAI(model_name="gpt-4o", temperature=0)
    chain = prompt | llm | output_parser

    try:
        new_info = chain.invoke(
            {
                "latest_interaction": latest_interaction,
                "existing_info": str(existing_info),
            }
        )
        # Merge new info with existing, preserving existing data where new info is missing
        return {
            **existing_info,
            **{k: v for k, v in new_info.items() if v not in [None, ""]},
        }
    except Exception as e:
        print(f"Partial extraction error: {e}")
        return existing_info


def format_latest_interaction(candidate_identifier):
    """
    Formats the latest interaction showing:
    - Last 2 assistant responses
    - Last user response
    in chronological order (older messages first).
    """
    path = f"Stored_context/applicants_in_progress/{candidate_identifier}.json"
    try:
        with open(path, "r") as f:
            data = json.load(f)
            
            if isinstance(data, list) and len(data) > 0:
                conversation = data[0].get("conversation", [])
                
                last_user_message = None
                assistant_messages = []
                
                # Collect messages in reverse order
                for message in reversed(conversation):
                    # Get the last user message
                    if message["role"] == "external_user" and last_user_message is None:
                        last_user_message = f"User: {message['message']}"
                    
                    # Get up to 2 assistant messages
                    if message["role"] == "assistant":
                        assistant_messages.append(f"Assistant: {message['message']}")
                    
                    # Stop when we have all required messages
                    if last_user_message is not None and len(assistant_messages) >= 2:
                        break
                
                # Combine messages maintaining chronological order
                interaction_parts = []
                
                # Add the first assistant message if it exists
                if len(assistant_messages) > 1:
                    interaction_parts.append(assistant_messages[-1])
                
                # Add the user message if it exists
                if last_user_message is not None:
                    interaction_parts.append(last_user_message)
                
                # Add the second assistant message if it exists
                if len(assistant_messages) > 0:
                    interaction_parts.append(assistant_messages[0])
                
                return "\n".join(interaction_parts)
                
        return "No conversation found"
        
    except Exception as e:
        print(f"Error formatting interaction: {e}")
        return "Error loading conversation"


    

# Modified receive_message with real-time extraction
def recieve_message(query, candidate_identifier):
    candidate_json = find_or_create_candidate_json(candidate_identifier)
    assistant_id = get_corresponding_assistant(candidate_identifier)
    if assistant_id is None:
        return "Please restart conversation, the assistant has left"
    
    update_conversation(candidate_identifier, user_message=query)
    
    # First candidate screening phase
    if candidate_json['assistant_stage'] == 0:

        # Get AI response
        response = openAiUtils.send_to_ai(query, candidate_json["thread_id"], assistant_id)

        update_conversation(candidate_identifier, assistant_response=response)

        latest_interaction =  format_latest_interaction(candidate_identifier)
        print("LATEST INTERACTION\n\n", latest_interaction)

        # Load existing extracted info
        existing_info = load_extracted_info(candidate_identifier)  # Should return empty dict if none exists

        # Perform info extraction
        updated_info = extract_conversation_info(latest_interaction, existing_info)

        # Save updated info
        save_extracted_data(candidate_identifier, updated_info)

        # Check if all fields are fulfilled
        check_and_process_candidate(candidate_identifier) # Save & upgrade candidate
        
        return response
    
    # Get AI response
    response = openAiUtils.send_to_ai(query, candidate_json["thread_id"], assistant_id)

    update_conversation(candidate_identifier, assistant_response=response)

    return response


# Helper functions
def load_extracted_info(candidate_identifier):
    path = f"Stored_context/applicants_in_progress/{candidate_identifier}.json"
    try:
        with open(path, "r") as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("extracted_info", {})
        return {}
    except Exception as e:
        print(f"Error loading extracted info: {e}")
        return {}


def save_extracted_data(candidate_identifier, data):
    path = f"Stored_context/applicants_in_progress/{candidate_identifier}.json"
    try:
        # Load existing data
        with open(path, "r") as f:
            file_data = json.load(f)

        # Update extracted info
        if isinstance(file_data, list) and len(file_data) > 0:
            file_data[0]["extracted_info"] = data

            # Write back to file
            with open(path, "w") as f:
                json.dump(file_data, f, indent=2)
    except Exception as e:
        print(f"Error saving extracted data: {e}")


def retrieve_last_responses(candidate_identifier):
    path = f"Stored_context/applicants_in_progress/{candidate_identifier}.json"
    try:
        with open(path, "r") as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                conversation = data[0].get("conversation", [])
                
                last_assistant = None
                last_user = None
                
                # Search in reverse order
                for message in reversed(conversation):
                    if message["role"] == "assistant" and last_assistant is None:
                        last_assistant = message["message"]
                    elif message["role"] == "external_user" and last_user is None:
                        last_user = message["message"]
                    
                    if last_assistant is not None and last_user is not None:
                        break
                
                return last_assistant, last_user
                
        return None, None
        
    except Exception as e:
        print(f"Error retrieving last responses: {e}")
        return None, None


def check_and_process_candidate(candidate_identifier):
    """
    Checks if all fields in extracted_info are fulfilled and processes the candidate if they are.
    """
    # Load the candidate data
    path = f"Stored_context/applicants_in_progress/{candidate_identifier}.json"
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            
        if not isinstance(data, list) or len(data) == 0:
            print("Invalid data format")
            return False
            
        
        candidate_data = data[0]
        extracted_info = candidate_data.get('extracted_info', {})
        thread_id = candidate_data.get('thread_id')
        
        print("ASSISTANT'S CONFIRMATION VALUE:\n", extracted_info['assistant_confirmation'])
        
        
        # Define required fields
        required_fields = {
            "first_name", "experience",
            "lead_source", "lead_source_id", "availability", "city", "phone",
            "location_id", "position_id"
        }
        

        # Check if all required fields are present and non-empty
        if not all(extracted_info.get(field) not in [None, ""] for field in required_fields):
            missing_or_empty_fields = [
                field for field in required_fields 
                if extracted_info.get(field) in [None, ""]
            ]
            print("The following required fields are missing or empty:", missing_or_empty_fields)
            return False
        else:
            print("All required fields are fulfilled.")
        
        if extracted_info['assistant_confirmation'] == "false":
            print("All required fields fulfilled. Waiting for candidates's final confirmation")
            return False
            
            
            
        # Ensure 'age' field is numeric
        if 'age' in extracted_info:
            try:
                # Try to convert 'age' to an integer
                extracted_info['age'] = int(extracted_info['age'])
            except (ValueError, TypeError):
                print("Invalid 'age' value. 'age' must be a numeric value.")
                return False
               
        # Prepare the final JSON data
        candidate_json_data = {
            **extracted_info,
            "candidate_identifier": candidate_identifier,
            "thread_id": thread_id
        }
        
        # Call the processing functions
        save_to_database(candidate_json_data)
        upgrade_candidate(candidate_identifier, candidate_json_data)
        
        print("Candidate saved successfully")
        return True
        
    except Exception as e:
        print(f"Error processing candidate: {e}")
        return False
