from flask import Flask, request, jsonify
from message_reciever import recieve_message
import os
from dotenv import load_dotenv
import requests


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
@app.route('/update_candidate', methods=['PUT'])
def update_candidate_route():
    data = request.json
    candidate_manager = CandidateManager()
    return candidate_manager.update_candidate(data["candidate_id"], data)

@app.route('/get_candidates', methods=['GET'])
def show_candidates():
    candidate_manager = CandidateManager()  
    candidates = candidate_manager.get_all_candidates()

    candidates_list = [
        {
            "first_name": candidate[0],
            "last_name": candidate[1],
            "email": candidate[2],
            "phone": candidate[3],
            "age": candidate[4],
            "addresse": candidate[5],
            "enrollment_start_timestamp": candidate[6],
            "enrollment_end_timestamp": candidate[7],
            "date_created": candidate[8],
            "date_updated": candidate[9]
        }
        for candidate in candidates
    ]

    return jsonify({"candidates": candidates_list}), 200

@app.route('/get_candidate_by_id', methods=['GET'])
def show_candidate_details(candidate_id):
    candidate_manager = CandidateManager()  
    candidate = candidate_manager.especific_candidate(candidate_id)

    if not candidate:
        return jsonify({"error": f"Candidate with ID {candidate_id} not found"}), 404

    candidate_data = {
        "first_name": candidate[0],
        "last_name": candidate[1],
        "email": candidate[2],
        "phone": candidate[3],
        "age": candidate[4],
        "addresse": candidate[5],
        "enrollment_start_timestamp": candidate[6],
        "enrollment_end_timestamp": candidate[7],
        "date_created": candidate[8],
        "date_updated": candidate[9]
    }

    return jsonify({"candidate": candidate_data}), 200
# End of new endpoints

@app.route('/admin_process', methods=['POST'])
def process_data():
    # Get data from the POST request
    data = request.json
    print(f"Received data: {data}")
    
    # Process the data (here, we're just echoing it)
    processed_data = f"Processed: {data['message']}"
    response = recieve_query_from_whatsapp(data['message'], data['number'])

    # Return a response
    return jsonify({"processed_message": response}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
