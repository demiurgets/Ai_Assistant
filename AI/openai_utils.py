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
        # OpenAI API configuration
        self.api_key = os.getenv('API_KEY')
        self.reader_id = os.getenv('ASST_ID_READER')
        self.interviewer_id = os.getenv('ASST_INTERVIEWER')

        # Load transformer model
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)

    def create_thread(self):
        client = OpenAI(api_key=self.api_key)
        thread = client.beta.threads.create()
        thread_id = thread.id
        return thread_id
    
    
    def send_to_ai(self, query, thread_id, asstId):
        print("messaging from class")
        client = OpenAI(api_key=self.api_key)

        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=query
        )
        print("Ai run started...")

        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=asstId,
        )
        response = "Error with AI API"
        if run.status == 'completed':
            print("AI Run completed")
            response_page = client.beta.threads.messages.list(thread_id=thread_id)
            response = response_page.data[0].content[0].text.value
            
        else:
            response = "Error processing request with OpenAI. Please Try again."
        return response

