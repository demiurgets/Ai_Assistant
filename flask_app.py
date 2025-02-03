from flask import Flask, render_template, request, jsonify

from message_reciever import recieve_message, find_or_create_candidate_json
import os
from dotenv import load_dotenv
import requests
from sqlalchemy.exc import SQLAlchemyError
import json
from uuid import UUID
import uuid
from DataAccessLayer.createModels import createModelsMain
from DataAccessLayer.createDatabaseORM import createDbMain
from Injestor.pdf_reader import analyze_CV

from DataAccessLayer.services.candidateServices import (
    get_all_candidates,
    get_candidate_by_id,
    create_candidate,
    update_candidate,
    delete_candidate,
    update_candidate_status,
    delete_by_candidate_identifier,
    get_candidates_by_status,
    load_issues,
    save_new_issue,
    match_cv_to_positions
)
from DataAccessLayer.services.userServices import (
    get_all_users,
    get_user_by_id,
    create_user,
    update_user,
    delete_user,
    update_user_status,
    validate_password,
    get_users_by_status,
    get_user_by_email
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
from DataAccessLayer.services.assistantServices import (
    toggle_greeter_direction,
    updateAssistantContext
)
from DataAccessLayer.services.customerServices import ( 
    get_customer_settings, 
    get_all_customers, 
    create_customer, 
    update_customer_setting, 
    delete_customer )


app = Flask(__name__)

SECURITY_TOKEN = os.getenv('FLASK_API_TOKEN')

GRAPH_API_TOKEN  = os.getenv('WHATSAPP_GRAPH_API_TOKEN')
HILOS_API_KEY = os.getenv('HILOS_API_TOKEN')
WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY")

MESSENGER_WEBHOOK_VERIFY_TOKEN = os.getenv('MESSENGER_WEBHOOK_VERIFY_TOKEN')
MESSENGER_PAGE_ACCESS_TOKEN = os.getenv('MESSENGER_PAGE_ACCESS_TOKEN')

def validate_token():
    token = request.headers.get('Authorization')
    if token != f"Bearer {SECURITY_TOKEN}":
        return jsonify({'error': 'Unauthorized access'}), 403
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/report_issue', methods=['POST'])
def report_issue():
    print("reporting in flask")
    """Saves a new issue to the issues.json file."""
    data = request.json
    new_issue = save_new_issue(data)
    return jsonify({'success': True, 'message': 'Issue reported successfully', 'issue': new_issue}), 201


@app.route('/get_issues', methods=['GET'])
def get_issues():
    """Retrieves all the issue reports stored in the issues.json file."""
    issues = load_issues()
    return jsonify({'issues': issues}), 200


@app.route('/ui_send_message', methods=['POST'])
def send_message():
    data = request.json
    message = data.get('message')
    candidate_identifier = data.get('candidate_identifier')

    if message and candidate_identifier:
        response = recieve_message(message, candidate_identifier)
        return jsonify({'response': response})
    else:
        return jsonify({'error': 'Invalid message or candidate_identifier'}), 400


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


@app.route('/hilos_webhook', methods=['POST', 'GET'])
def hilos_webhook_endpoint():
    if request.method == 'GET':
        return jsonify({"message": "GET request received, but only POST requests are processed"}), 200

    # Extract the incoming data
    data = request.json
    if data['event_data']['direction'] != "INBOUND":
        print("not inbound. skipping...")
        
        return jsonify({"processed_message": "message not inbound"}), 200
    try:
        print(f"Received data: {data}")

        # Extract sender info
        sender_number = data['event_data']['from_number']
        message = data['event_data']['body']
        sender_number = "".join(filter(str.isdigit, sender_number))
        # Extract the InboxContact ID
        inbox_contact_id = data['event_data']['inbox_contact']  # Update this to match the actual key for inbox_contact_id
        print(f"Message from {sender_number}: {message}")
        print(f"Received message: {message} from number: {sender_number}")

        
        # Process the message and generate a response
        response_message = recieve_message(message, sender_number)
        #response_message = f"Recieved message: {message}"

        
        # Send the response message to the candidate
        send_hilos_message(inbox_contact_id, response_message)
        
        return jsonify({"processed_message": response_message}), 200
    except KeyError as e:
        print(f"Error extracting data: {e}")
        return jsonify({"error": "Error processing incoming message"}), 500

def send_hilos_message(inbox_contact_id, message):
    """Send a message to Hilos using the contact's InboxContact ID."""
    HILOS_API_URL = "https://api.hilos.io/api/inbox/contact"
    url = f"{HILOS_API_URL}/{inbox_contact_id}/message"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {HILOS_API_KEY}"  # Bearer token for Hilos API
    }
    payload = {
        'body': message, 
        'msg_type': 'text', 
        'is_deleted': False
    }

    print("\n--- REQUEST DATA ---")
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("--------------------\n")
        
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            print(f"Message successfully sent to inbox_contact_id {inbox_contact_id}")
        else:
            print(f"Failed to send message. Status code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Error sending message to Hilos: {e}")


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



# Candidate endpoints using candidateServices functions

# 1. Get all candidates
@app.route('/candidates', methods=['GET'])
def all_candidates():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        candidates = get_all_candidates()
        return jsonify({"data": candidates}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching candidates: {e}"}), 500

# 2. Get candidate by ID
@app.route('/candidates/<int:candidate_id>', methods=['GET'])
def get_candidate(candidate_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        candidate = get_candidate_by_id(candidate_id)
        if candidate:
            return jsonify({"data": candidate}), 200
        return jsonify({"error": "Candidate not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching candidate: {e}"}), 500
    
# 3. Get candidates by status
@app.route('/candidates/status/<int:status_id>', methods=['GET'])
def candidates_by_status(status_id):
    try:
        candidates = get_candidates_by_status(status_id)
        return jsonify({"data": candidates}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching candidates by status: {e}"}), 500    
    
# 4. Create a new candidate
@app.route('/candidates', methods=['POST'])
def add_candidate():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        candidate_data = request.json
        candidate = create_candidate(candidate_data)
        if candidate:
            return jsonify({"message": "Candidate created successfully", "data": candidate}), 201
        return jsonify({"error": "Failed to create candidate"}), 500
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error creating candidate: {e}"}), 500

# 5. Update candidate by ID
@app.route('/candidates/<int:candidate_id>', methods=['PUT'])
def modify_candidate(candidate_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        update_data = request.json
        updated_candidate = update_candidate(candidate_id, update_data)
        if updated_candidate:
            return jsonify({"message": "Candidate updated successfully", "data": updated_candidate}), 200
        return jsonify({"error": "Failed to update candidate or candidate not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating candidate: {e}"}), 500

# 6. Delete candidate by ID
@app.route('/candidates/<int:candidate_id>', methods=['DELETE'])
def remove_candidate(candidate_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
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
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        updated_candidate = update_candidate_status(candidate_id, new_status)
        if update_candidate:
            return jsonify({"message": "Candidate updated successfully", "data": updated_candidate}), 200
        return jsonify({"error": "Failed to update candidate or candidate not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating candidate: {e}"}), 500 

@app.route('/conversation_by_candidate_identifier/<candidate_identifier>', methods=['GET'])
def find_conversation_by_candidate_identifier(candidate_identifier):
    # Call the function to find the candidate by candidate identifier
    candidate_data = find_or_create_candidate_json(candidate_identifier)
    #print(candidate_data)
    return jsonify(candidate_data)

#  Delete candidate in screening by candidate identifier
@app.route('/candidates/candidate_identifier/<candidate_identifier>', methods=['DELETE'])
def delete_by_candidate_identifier_endpoint(candidate_identifier):
    try:
        return delete_by_candidate_identifier(candidate_identifier)
        
    except Exception as e:
        return jsonify({"error": f"Failed to delete candidate screening data: {str(e)}"}), 500


#@app.route('/candidates/in_progress', methods=['GET'])
#def get_applicants_in_progress_endpoint():
#    # Call the function to find the candidate by candidate_identifier
#    candidate_data = get_applicants_in_progress()
#    #print(candidate_data)
#    return jsonify(candidate_data)

# 1. Get All Customers
@app.route('/customers', methods=['GET'])
def get_customers():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        customers = get_all_customers()
        return jsonify({"data": customers}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching customers: {e}"}), 500

# 2. Get Customer Settings by Customer ID
@app.route('/customers/<uuid:customer_id>/settings', methods=['GET'])
def get_customer_settings_by_id(customer_id: UUID):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        settings = get_customer_settings(customer_id)
        if settings:
            return jsonify({"data": settings}), 200
        return jsonify({"error": "Customer settings not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching settings: {e}"}), 500

# 3. Create a New Customer with Settings
@app.route('/customers', methods=['POST'])
def add_customer():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        customer_data = request.json.get("customer")
        settings_data = request.json.get("settings", {})

        if not customer_data or "name" not in customer_data:
            return jsonify({"error": "Customer data must include 'name'"}), 400

        new_customer = create_customer(customer_data, settings_data)
        if new_customer:
            return jsonify({"message": "Customer created successfully", "data": new_customer}), 201
        return jsonify({"error": "Failed to create customer"}), 500
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error creating customer: {e}"}), 500

# 4. Update a Customer's Setting
@app.route('/customers/<uuid:customer_id>/settings', methods=['PUT'])
def update_customer_setting_by_id(customer_id: UUID):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        update_data = request.json
        setting_name = update_data.get("setting_name")
        new_value = update_data.get("new_value")

        if not setting_name or new_value is None:
            return jsonify({"error": "Both 'setting_name' and 'new_value' are required"}), 400

        updated = update_customer_setting(customer_id, setting_name, new_value)
        if updated:
            return jsonify({"message": "Customer setting updated successfully"}), 200
        return jsonify({"error": "Failed to update setting or setting not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating customer setting: {e}"}), 500

# 5. Delete a Customer by ID
@app.route('/customers/<uuid:customer_id>', methods=['DELETE'])
def delete_customer_by_id(customer_id: UUID):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        deleted = delete_customer(customer_id)
        if deleted:
            return jsonify({"message": "Customer deleted successfully"}), 200
        return jsonify({"error": "Failed to delete customer or customer not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error deleting customer: {e}"}), 500


@app.route('/documents/analyze_cv/<candidate_identifier>', methods=['POST'])
def analyze_cv_endpoint(candidate_identifier):
    if 'cv' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['cv']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and file.filename.endswith('.pdf'):
        # Save the file if needed or process it directly
        file_path = f"Stored_context/uploaded_CVs/{file.filename}"
        file.save(file_path)

        # Call the analyze_CV function with the file path and candidate identifier
        analysis = analyze_CV(file_path, candidate_identifier)
        #print(analysis)
        return jsonify({'analysis': analysis})

    return jsonify({'error': 'Invalid file type'}), 400


@app.route('/documents/match_cv/<candidate_identifier>', methods=['GET'])
def match_cv_endpoint(candidate_identifier):
    match_response = match_cv_to_positions(candidate_identifier)
    print(match_response)
    return jsonify({"matchingPositions": match_response})


@app.route('/validate-password', methods=['POST'])
#for sign in if validation is to be done in backend
def validate_password_endpoint():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    data = request.json
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required"}), 400

    if validate_password(email, password):
        return jsonify({"success": True, "message": "Password is valid"})
    else:
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route('/toggle_greeter_direction', methods=['POST'])
def toggleDirection():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        updated_instructions = toggle_greeter_direction()
        return jsonify({"Updated Successfully": updated_instructions}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching users: {e}"}), 500
    
@app.route('/contextualize_greeter_instructions')
# 1. Get all users
@app.route('/users', methods=['GET'])
def addContext():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        updated_instructions = updateAssistantContext()
        return jsonify({"Updated Successfully": updated_instructions}), 200

    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching users: {e}"}), 500

# 2. Get a user by ID
@app.route('/users/<int:user_id>', methods=['GET'])
def user_by_id(user_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        user = get_user_by_id(user_id)
        if user:
            return jsonify({"data": user}), 200
        return jsonify({"error": "User not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching user by ID: {e}"}), 500
    
# 3. Get users by status
@app.route('/users/status/<int:status_id>', methods=['GET'])
def users_by_status(status_id):
    try:
        users = get_users_by_status(status_id)
        return jsonify({"data": users}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching users by status: {e}"}), 500
    


# 4. Create a new user
@app.route('/users', methods=['POST'])
def create_new_user():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        user_data = request.json
        user = create_user(user_data)
        if user:
            return jsonify({"message": "User created successfully", "data": user}), 201
        return jsonify({"error": "Failed to create user"}), 500
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error creating user: {e}"}), 500

# 5. Update user by ID
@app.route('/users/<int:user_id>', methods=['PUT'])
def update_existing_user(user_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        update_data = request.json
        updated_user = update_user(user_id, update_data)
        if updated_user:
            return jsonify({"message": "User updated successfully", "data": updated_user}), 200
        return jsonify({"error": "Failed to update user or user not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating user: {e}"}), 500

# 6. Delete user by ID
@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_existing_user(user_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
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
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        updated_user = update_user_status(user_id, new_status)
        if update_user:
            return jsonify({"message": "User updated successfully", "data": updated_user}), 200
        return jsonify({"error": "Failed to update user or user not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating user: {e}"}), 500 


# 8. Get user by email
@app.route('/users/email/<string:email>', methods=['GET'])
def user_by_email(email):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        user = get_user_by_email(email)
        if user:
            return jsonify({"data": user}), 200
        return jsonify({"error": "User not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching user by email: {e}"}), 500

# Positions endpoints
@app.route('/positions', methods=['GET'])
def all_positions():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        positions = get_all_positions()
        return jsonify({"data": positions}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching positions: {e}"}), 500

@app.route('/positions/<int:position_id>', methods=['GET'])
def get_position(position_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        position = get_position_by_id(position_id)
        if position:
            return jsonify({"data": position}), 200
        return jsonify({"error": "Position not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching position: {e}"}), 500

@app.route('/positions', methods=['POST'])
def add_position():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        position_data = request.json
        position = create_position(position_data)
        if position:
            return jsonify({"message": "Position created successfully", "data": position}), 201
        return jsonify({"error": "Failed to create position"}), 500
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error creating position: {e}"}), 500

@app.route('/positions/<int:position_id>', methods=['PUT'])
def modify_position(position_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        update_data = request.json
        updated_position = update_position(position_id, update_data)
        if updated_position:
            return jsonify({"message": "Position updated successfully", "data": updated_position}), 200
        return jsonify({"error": "Failed to update position or position not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating position: {e}"}), 500

@app.route('/positions/<int:position_id>', methods=['DELETE'])
def remove_position(position_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
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
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        locations = get_all_locations()
        return jsonify({"data": locations}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching locations: {e}"}), 500

@app.route('/locations/<int:location_id>', methods=['GET'])
def get_location(location_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        location = get_location_by_id(location_id)
        if location:
            return jsonify({"data": location}), 200
        return jsonify({"error": "Location not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error fetching location: {e}"}), 500

@app.route('/locations', methods=['POST'])
def add_location():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        location_data = request.json
        location = create_location(location_data)
        if location:
            return jsonify({"message": "Location created successfully", "data": location}), 201
        return jsonify({"error": "Failed to create location"}), 500
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error creating location: {e}"}), 500

@app.route('/locations/<int:location_id>', methods=['PUT'])
def modify_location(location_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        update_data = request.json
        updated_location = update_location(location_id, update_data)
        if updated_location:
            return jsonify({"message": "Location updated successfully", "data": updated_location}), 200
        return jsonify({"error": "Failed to update location or location not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error updating location: {e}"}), 500

@app.route('/locations/<int:location_id>', methods=['DELETE'])
def remove_location(location_id):
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        success = delete_location(location_id)
        if success:
            return jsonify({"message": "Location deleted successfully"}), 200
        return jsonify({"error": "Failed to delete location or location not found"}), 404
    except SQLAlchemyError as e:
        return jsonify({"error": f"Error deleting location: {e}"}), 500


@app.route('/createModels', methods=["POST"])
def createModels():
    auth_error = validate_token()
    if auth_error:
        return auth_error
    try:
        createModelsMain()
        return jsonify({"message": "Models created Successfully"}), 200

    except SQLAlchemyError as e:
        return jsonify({"error": f"Error deleting location: {e}"}), 500

@app.route('/createDBfromModels', methods=["POST"])
def createDbfromModels():
    auth_error = validate_token()
    if auth_error:
        return auth_error
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
                        response = {"text": '{}'.format(recieve_message(receivedMessage['text'], senderPsid))}
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
    app.run(host="0.0.0.0", port=80) ## dejar puerto 80 para que funcione en azure
