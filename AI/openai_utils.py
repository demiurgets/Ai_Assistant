import os
import time
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class OpenAIUtility:
    def __init__(self):
        # OpenAI API configuration
        self.api_key = os.getenv('OPENAI_KEY')
        self.reader_id = os.getenv('ASST_ID_READER')
        self.interviewer_id = os.getenv('ASST_INTERVIEWER')
        self.client = OpenAI(
            api_key=self.api_key,
            max_retries=5  # Configure built-in retries
        )

    def create_thread(self):
        """Create a new conversation thread"""
        try:
            thread = self.client.beta.threads.create()
            return thread.id
        except Exception as e:
            print(f"Error creating thread: {str(e)}")
            return None

    def send_to_ai(self, query, thread_id, asstId):
        """Send message to assistant and get response"""
        print("Starting AI message processing")
        
        try:
            # Create message in thread
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=query
            )
            print("User message added to thread")

            # Create and poll run with timeout
            run = self.client.beta.threads.runs.create_and_poll(
                thread_id=thread_id,
                assistant_id=asstId,
                timeout=60  # Timeout
            )

            if run.status == 'completed':
                print("AI Run completed successfully")
                messages = self.client.beta.threads.messages.list(
                    thread_id=thread_id
                )
                return messages.data[0].content[0].text.value
            else:
                print(f"Run ended with status: {run.status}")
                return f"Sorry, I couldn't process your request. (Status: {run.status})"

        except Exception as e:
            print(f"Error in send_to_ai: {str(e)}")
            return ""