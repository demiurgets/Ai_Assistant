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
        self.client = OpenAI(api_key=self.api_key)

    def create_thread(self):
        try:
            thread = self.client.beta.threads.create()
            return thread.id
        except Exception as e:
            print(f"Error creating thread: {e}")
            return None

    def wait_for_run_completion(self, thread_id, run_id):
        """Wait for a run to complete."""
        while True:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            if run.status in ['completed', 'failed', 'cancelled']:
                return run.status
            time.sleep(1)  # Wait for 1 second before checking again

    def send_to_ai(self, query, thread_id, asst_id):
        try:
            # Check if there is an active run in the thread
            runs = self.client.beta.threads.runs.list(thread_id=thread_id)
            active_runs = [run for run in runs.data if run.status not in ['completed', 'failed', 'cancelled']]

            # Wait for all active runs to complete
            for run in active_runs:
                print(f"Waiting for run {run.id} to complete...")
                self.wait_for_run_completion(thread_id, run.id)

            # Add the user's message to the thread
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=query
            )
            print("AI run started...")

            # Create and poll the run
            run = self.client.beta.threads.runs.create_and_poll(
                thread_id=thread_id,
                assistant_id=asst_id,
            )

            # Check if the run completed successfully
            if run.status == 'completed':
                print("AI Run completed")
                response_page = self.client.beta.threads.messages.list(thread_id=thread_id)
                response = response_page.data[0].content[0].text.value
                return response
            else:
                print(f"Run status: {run.status}")
                return "Error with AI API"
        except Exception as e:
            print(f"Error sending message to AI: {e}")
            return self.send_to_ai(query, thread_id, asst_id)