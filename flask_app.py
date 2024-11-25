from flask import Flask, render_template, request, jsonify

from message_reciever import recieve_message, find_or_create_candidate
import os
from dotenv import load_dotenv
import requests
from sqlalchemy.exc import SQLAlchemyError
import json
from DataAccessLayer.createModels import createModelsMain
from DataAccessLayer.createDatabaseORM import createDbMain


from DataAccessLayer.services.candidateServices import (
    get_all_candidates,
    get_candidate_by_id,
    create_candidate,
    update_candidate,
    delete_candidate,
    update_candidate_status
)
from DataAccessLayer.services.userServices import (
    get_all_users,
    get_user_by_id,
    create_user,
    update_user,
    delete_user,
    update_user_status
)
from DataAccessLayer.services.locationsServices import (
    get_all_locations,
    get_location_by_id,
    create_location,
    update_location,
    delete_location
)

from DataAccessLayer.services.positionServices import (
    get_all_positions,
    get_position_by_id,
    create_position,
    update_position,
    delete_position
)



app = Flask(__name__)

GRAPH_API_TOKEN  = os.getenv('WHATSAPP_GRAPH_API_TOKEN')
WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY")

MESSENGER_WEBHOOK_VERIFY_TOKEN = os.getenv('MESSENGER_WEBHOOK_VERIFY_TOKEN')
MESSENGER_PAGE_ACCESS_TOKEN = os.getenv('MESSENGER_PAGE_ACCESS_TOKEN')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/find_candidate_by_phone/<phone_number>', methods=['GET'])
def find_candidate_by_phone_endpoint(phone_number):
    # Call the function to find the candidate by phone number
    candidate_data = find_or_create_candidate(phone_number)
    print(candidate_data)
    return jsonify(candidate_data)

@app.route('/ui_send_message', methods=['POST'])
def send_message():
    data = request.json
    message = data.get('message')
    phone_number = data.get('phone_number')

    if message and phone_number:
        response = recieve_message(message, phone_number)
        return jsonify({'response': response})
    else:
        return jsonify({'error': 'Invalid message or phone number'}), 400


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
    # Extract the incoming data
    data = request.json

    try:
        # Check if this is a message or status update
        if 'messages' in data['entry'][0]['changes'][0]['value']:
            print(f"Received data: {data}")

            # Extract sender info
            sender_number = data['entry'][0]['changes'][0]['value']['messages'][0]['from']
            
            # Check if the phone number starts with +52 (Mexico's country code)
            if sender_number.startswith("52"):
                print("Received from Mexico")
                return "", 200  # Do nothing and return


            # Process message if 'messages' key exists
            message = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            sender_number = data['entry'][0]['changes'][0]['value']['messages'][0]['from']
            business_phone_number_id = data['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']

            print(f"Received message: {message} from number: {sender_number}")
            
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

        elif 'statuses' in data['entry'][0]['changes'][0]['value']:
            # Handle status update if 'statuses' key exists
            print("Received status update:", data['entry'][0]['changes'][0]['value']['statuses'][0]['status'])
            # You may choose to log status updates or perform other actions here
            return jsonify({"status": "Status update received"}), 200

        else:
            print("Unexpected data format.")
            return jsonify({"error": "Unexpected data format"}), 400

    except KeyError as e:
        print(f"Error extracting data: {e}")
        return jsonify({"error": "Error processing incoming message"}), 500


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



# Candidate endpoints using candidateServices functions

# 1. Get all candidates
@app.route('/candidates', methods=['GET'])
def all_candidates():
    try:
        candidates = get_all_candidates()
        return jsonify({"data": candidates}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching candidates: {e}"}), 500

# 2. Get candidate by ID
@app.route('/candidates/<int:candidate_id>', methods=['GET'])
def get_candidate(candidate_id):
    try:
        candidate = get_candidate_by_id(candidate_id)
        if candidate:
            return jsonify({"data": candidate}), 200
        return jsonify({"error": "Candidate not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching candidate: {e}"}), 500
    
# 4. Create a new candidate
@app.route('/candidates', methods=['POST'])
def add_candidate():
    try:
        candidate_data = request.json
        candidate = create_candidate(candidate_data)
        if candidate:
            return jsonify({"message": "Candidate created successfully", "candidate": candidate}), 201
        return jsonify({"error": "Failed to create candidate"}), 500
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error creating candidate: {e}"}), 500

# 5. Update candidate by ID
@app.route('/candidates/<int:candidate_id>', methods=['PUT'])
def modify_candidate(candidate_id):
    try:
        update_data = request.json
        updated_candidate = update_candidate(candidate_id, update_data)
        if updated_candidate:
            return jsonify({"message": "Candidate updated successfully", "candidate": updated_candidate}), 200
        return jsonify({"error": "Failed to update candidate or candidate not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating candidate: {e}"}), 500

# 6. Delete candidate by ID
@app.route('/candidates/<int:candidate_id>', methods=['DELETE'])
def remove_candidate(candidate_id):
    try:
        success = delete_candidate(candidate_id)
        if success:
            return jsonify({"message": "Candidate deleted successfully"}), 200
        return jsonify({"error": "Failed to delete candidate or candidate not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error deleting candidate: {e}"}), 500

# 7. Update candidate status
@app.route('/candidates/<int:candidate_id>/status/<int:new_status>', methods=['PUT'])
def update_existing_candidate_status(candidate_id, new_status):
    try:
        updated_candidate = update_candidate_status(candidate_id, new_status)
        if update_candidate:
            return jsonify({"message": "Candidate updated successfully", "candidate": updated_candidate}), 200
        return jsonify({"error": "Failed to update candidate or candidate not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating candidate: {e}"}), 500 

# 7. Delete candidate in screening by phone number
@app.route('/candidates/screening/<phone_number>', methods=['DELETE'])
def delete_candidate_in_screening(phone_number):
    """
    Deletes a candidate's JSON data in the screening process by their phone number.
    """
    json_file_path = os.path.join("Stored_context/applicants_in_progress", f"{phone_number}.json")
    try:
        if os.path.exists(json_file_path):
            os.remove(json_file_path)
            return jsonify({"message": f"Candidate data for phone number {phone_number} successfully deleted."}), 200
        else:
            return jsonify({"error": f"No screening data found for phone number {phone_number}."}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to delete candidate screening data: {str(e)}"}), 500

# 1. Get all users
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
    
# 7. Update user status
@app.route('/users/<int:user_id>/status/<int:new_status>', methods=['PUT'])
def update_existing_user_status(user_id, new_status):
    try:
        updated_user = update_user_status(user_id, new_status)
        if update_user:
            return jsonify({"message": "User updated successfully", "user": updated_user}), 200
        return jsonify({"error": "Failed to update user or user not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating user: {e}"}), 500 



# Positions endpoints
@app.route('/positions', methods=['GET'])
def all_positions():
    try:
        positions = get_all_positions()
        return jsonify({"data": positions}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching positions: {e}"}), 500

@app.route('/positions/<int:position_id>', methods=['GET'])
def get_position(position_id):
    try:
        position = get_position_by_id(position_id)
        if position:
            return jsonify({"data": position}), 200
        return jsonify({"error": "Position not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching position: {e}"}), 500

@app.route('/positions', methods=['POST'])
def add_position():
    try:
        position_data = request.json
        position = create_position(position_data)
        if position:
            return jsonify({"message": "Position created successfully", "position": position}), 201
        return jsonify({"error": "Failed to create position"}), 500
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error creating position: {e}"}), 500

@app.route('/positions/<int:position_id>', methods=['PUT'])
def modify_position(position_id):
    try:
        update_data = request.json
        updated_position = update_position(position_id, update_data)
        if updated_position:
            return jsonify({"message": "Position updated successfully", "position": updated_position}), 200
        return jsonify({"error": "Failed to update position or position not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating position: {e}"}), 500

@app.route('/positions/<int:position_id>', methods=['DELETE'])
def remove_position(position_id):
    try:
        success = delete_position(position_id)
        if success:
            return jsonify({"message": "Position deleted successfully"}), 200
        return jsonify({"error": "Failed to delete position or position not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error deleting position: {e}"}), 500

# Locations endpoints
@app.route('/locations', methods=['GET'])
def all_locations():
    try:
        locations = get_all_locations()
        return jsonify({"data": locations}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching locations: {e}"}), 500

@app.route('/locations/<int:location_id>', methods=['GET'])
def get_location(location_id):
    try:
        location = get_location_by_id(location_id)
        if location:
            return jsonify({"data": location}), 200
        return jsonify({"error": "Location not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching location: {e}"}), 500

@app.route('/locations', methods=['POST'])
def add_location():
    try:
        location_data = request.json
        location = create_location(location_data)
        if location:
            return jsonify({"message": "Location created successfully", "location": location}), 201
        return jsonify({"error": "Failed to create location"}), 500
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error creating location: {e}"}), 500

@app.route('/locations/<int:location_id>', methods=['PUT'])
def modify_location(location_id):
    try:
        update_data = request.json
        updated_location = update_location(location_id, update_data)
        if updated_location:
            return jsonify({"message": "Location updated successfully", "location": updated_location}), 200
        return jsonify({"error": "Failed to update location or location not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating location: {e}"}), 500

@app.route('/locations/<int:location_id>', methods=['DELETE'])
def remove_location(location_id):
    try:
        success = delete_location(location_id)
        if success:
            return jsonify({"message": "Location deleted successfully"}), 200
        return jsonify({"error": "Failed to delete location or location not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error deleting location: {e}"}), 500


@app.route('/createModels', methods=["POST"])
def createModels():
    try:
        createModelsMain()
        return jsonify({"message": "Models created Successfully"}), 200

    except SQLAlchemyError as e:
        return jsonify({"error": f"Error deleting location: {e}"}), 500

@app.route('/createDBfromModels', methods=["POST"])
def createDbfromModels():
    try:
        createDbMain()
        return jsonify({"message": "DB created Successfully"}), 200

    except SQLAlchemyError as e:
        return jsonify({"error": f"Error deleting location: {e}"}), 500


@app.route('/messenger_webhook', methods=["GET", "POST"])
def messenger_hook():
    if request.method == 'GET':
        if 'hub.mode' in request.args and 'hub.verify_token' in request.args:
            mode = request.args.get('hub.mode')
            token = request.args.get('hub.verify_token')
            if mode == 'subscribe' and token == MESSENGER_WEBHOOK_VERIFY_TOKEN:
                print('WEBHOOK VERIFIED')
                challenge = request.args.get('hub.challenge')
                return challenge, 200
            else:
                return 'ERROR', 403
        return 'SOMETHING', 200

    if request.method == 'POST':
        data = request.data
        body = json.loads(data.decode('utf-8'))

        if 'object' in body and body['object'] == 'page':
            entries = body['entry']
            for entry in entries:
                webhookEvent = entry['messaging'][0]
                print(webhookEvent)

                senderPsid = webhookEvent['sender']['id']
                print('Sender PSID: {}'.format(senderPsid))

                if 'message' in webhookEvent:
                    receivedMessage = webhookEvent['message']

                    # Check if the received message contains text
                    if 'text' in receivedMessage:
                        response = {"text": 'Deployed version. You just sent -> {}'.format(receivedMessage['text'])}
                    else:
                        response = {"text": 'This chatbot only accepts text messages'}

                    # Call the Sender API
                    payload = {
                        'recipient': {'id': senderPsid},
                        'message': response,
                        'messaging_type': 'RESPONSE'
                    }
                    headers = {'content-type': 'application/json'}

                    url = 'https://graph.facebook.com/v10.0/me/messages?access_token={}'.format(MESSENGER_PAGE_ACCESS_TOKEN)
                    r = requests.post(url, json=payload, headers=headers)
                    print(r.text)

                return 'EVENT_RECEIVED', 200
        else:
            return 'ERROR', 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
