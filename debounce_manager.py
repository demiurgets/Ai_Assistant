import threading
import time
from message_reciever import recieve_message  # adjust import as needed
import os
from dotenv import load_dotenv
# Global constant for debounce delay
MESSAGE_DELAY = 10
HILOS_API_KEY = os.getenv('HILOS_API_TOKEN')


# Global stores shared with the UI and hilos integration.
# These are still maintained as globals for now.
inbox_contact_mapping = {}  # Maps sender_number → inbox_contact_id for Hilos responses
ui_message_store = {}

class DebounceManager:
    
    def __init__(self, delay=MESSAGE_DELAY):
        self.delay = delay
        self.lock = threading.Lock()
        self.timers = {}          # Maps sender_number -> Timer
        self.message_buffer = {}  # Maps sender_number -> list of messages

    def enqueue_message(self, sender_number, message, inbox_contact_id=None):
        """
        Enqueue a new message for the sender. If a timer already exists, cancel it and restart.
        """
        with self.lock:
            self.message_buffer.setdefault(sender_number, []).append(message)
            if inbox_contact_id:
                inbox_contact_mapping[sender_number] = inbox_contact_id

            # Cancel any existing timer
            if sender_number in self.timers:
                self.timers[sender_number].cancel()

            # Start a new timer to process messages after the delay.
            timer = threading.Timer(self.delay, self.process_messages, args=(sender_number,))
            self.timers[sender_number] = timer
            timer.start()

    def process_messages(self, sender_number):
        """
        Called when the debounce timer fires. Aggregate messages for the sender and process them.
        """
        with self.lock:
            if sender_number not in self.message_buffer:
                return
            combined_message = " ".join(self.message_buffer.pop(sender_number))
            self.timers.pop(sender_number, None)

        print(f"[INFO] Processing aggregated messages for {sender_number}: {combined_message}")
        response_message = recieve_message(combined_message, sender_number)
        print(f"[INFO] Generated AI response for {sender_number}: {response_message}")

        # Deliver the response. For Hilos, use the inbox mapping; for UI, store the response.
        if sender_number in inbox_contact_mapping:
            inbox_contact_id = inbox_contact_mapping.pop(sender_number, None)
            if inbox_contact_id:
                # Call your existing send_hilos_message() function where appropriate.
                send_hilos_message(inbox_contact_id, response_message)
        else:
            ui_message_store[sender_number] = response_message
            
    def send_hilos_message(inbox_contact_id, message):
        HILOS_API_URL = "https://api.hilos.io/api/inbox/contact"
        url = f"{HILOS_API_URL}/{inbox_contact_id}/message"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {HILOS_API_KEY}"
        }

        payload = {
            'body': message,
            'msg_type': 'text',
            'is_deleted': False
        }

        print(f"[INFO] Sending message to {inbox_contact_id}: {message}")

        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                print(f"[SUCCESS] Message successfully sent to {inbox_contact_id}")
            else:
                print(f"[ERROR] Failed to send message. Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            print(f"[ERROR] Error sending message: {e}")


# Note: The send_hilos_message function should be imported or defined elsewhere,
# so that this module remains focused on debouncing.