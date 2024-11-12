from flask import Flask, request, jsonify
from DataAccessLayer.models.candidateManager import CandidateManager
from message_reciever import recieve_message
import os
from dotenv import load_dotenv
import requests
from candidateManager import CandidateManager
from DataAccessLayer.services import *
from sqlalchemy.exc import SQLAlchemyError


app = Flask(__name__)

GRAPH_API_TOKEN  = os.getenv('WHATSAPP_GRAPH_API_TOKEN')
WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY")


# Endpoint for webhook verification
@app.route('/whatsapp_webhook', methods=['GET'])
def webhook_verification():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        print("Webhook verified successfully!")
        return challenge, 200
    else:
        return "Forbidden", 403



# handles incoming messages from WhatsApp
@app.route('/whatsapp_webhook', methods=['POST'])
def whatsapp_process_data():
    # Extract the message and number from incoming data
    data = request.json
    print(f"Received data: {data}")

    try:
        message = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
        sender_number = data['entry'][0]['changes'][0]['value']['messages'][0]['from']
        business_phone_number_id = data['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']

        print(f"Received message: {message} from number: {sender_number}")
    except KeyError as e:
        print(f"Error extracting data: {e}")
        return jsonify({"error": "Error processing incoming message"}), 500

    # Process the message using your application's logic
    response_message = recieve_message(message, sender_number)

    # Send the processed message back to WhatsApp using the Graph API
    url = f"https://graph.facebook.com/v18.0/{business_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {GRAPH_API_TOKEN}",
    }

    # Construct payload for response
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_number,
        "text": {"body": response_message},
        
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(response.status_code, response.text)  # Log status code and response body for more details
        response.raise_for_status()  # Check if request was successful
        print("Message sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to WhatsApp API: {e}")
        return jsonify({"error": "Failed to send message to WhatsApp"}), 500

    # Mark the message as read
    read_url = f"https://graph.facebook.com/v18.0/{business_phone_number_id}/messages"
    read_payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": data['entry'][0]['changes'][0]['value']['messages'][0]['id']
    }

    try:
        requests.post(read_url, headers=headers, json=read_payload)
        print("Message marked as read.")
    except requests.exceptions.RequestException as e:
        print(f"Error marking message as read: {e}")
        return jsonify({"error": "Failed to mark message as read"}), 500

    return jsonify({"processed_message": response_message}), 200


#Endpoint for facebook messenger
@app.route('/messenger_process', methods=['POST'])
def process_data_messenger():
    # Get data from the POST request
    data = request.json
    print(f"Received data: {data}")
    
    # Process the data (here, we're just echoing it)
    processed_data = f"Processed: {data['message']}"
    response = recieve_message(data['message'], "", data['email'])

    # Return a response
    return jsonify({"processed_message": response}), 200

# Front-end communication endpoints
manager = CandidateManager()

@app.route('/candidate/<int:candidate_id>', methods=['PUT'])
def update_candidate(candidate_id):
    data = request.json
    return manager.update_candidate(candidate_id, data)

@app.route('/candidates', methods=['GET'])
def get_all_candidates():
    return manager.get_all_candidates()

@app.route('/candidate/<int:candidate_id>', methods=['GET'])
def get_specific_candidate(candidate_id):
    return manager.specific_candidate(candidate_id)

@app.route('/candidate/<int:candidate_id>', methods=['DELETE'])
def delete_candidate(candidate_id):
    return manager.delete_candidate(candidate_id)

if __name__ == '__main__':
    app.run(debug=True)
# End of new endpoints


@app.route('/users', methods=['GET'])
def users():
    try:
        users = get_all_users()
        return jsonify({"data": users}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching users: {e}"}), 500

# 2. Get a user by ID
@app.route('/users/<int:user_id>', methods=['GET'])
def user_by_id(user_id):
    try:
        user = get_user_by_id(user_id)
        if user:
            return jsonify({"user": user}), 200
        return jsonify({"error": "User not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching user by ID: {e}"}), 500


# 4. Create a new user
@app.route('/users', methods=['POST'])
def create_new_user():
    try:
        user_data = request.json
        user = create_user(user_data)
        if user:
            return jsonify({"message": "User created successfully", "user": user}), 201
        return jsonify({"error": "Failed to create user"}), 500
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error creating user: {e}"}), 500

# 5. Update user by ID
@app.route('/users/<int:user_id>', methods=['PUT'])
def update_existing_user(user_id):
    try:
        update_data = request.json
        updated_user = update_user(user_id, update_data)
        if updated_user:
            return jsonify({"message": "User updated successfully", "user": updated_user}), 200
        return jsonify({"error": "Failed to update user or user not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating user: {e}"}), 500

# 6. Delete user by ID
@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_existing_user(user_id):
    try:
        success = delete_user(user_id)
        if success:
            return jsonify({"message": "User deleted successfully"}), 200
        return jsonify({"error": "Failed to delete user or user not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error deleting user: {e}"}), 500


@app.route('/create_location', methods=['POST'])
def location():
    # Get data from the POST request
    data = request.json
    print(f"Received data: {data}")
    
    # Process the data (here, we're just echoing it)
    processed_data = f"Processed: {data['message']}"

    # Return a response
    return jsonify({"processed_message": response}), 200

@app.route('/create_position', methods=['POST'])
def position():
    # Get data from the POST request
    data = request.json
    print(f"Received data: {data}")
    
    # Process the data (here, we're just echoing it)
    processed_data = f"Processed: {data['message']}"

    # Return a response
    return jsonify({"processed_message": response}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
