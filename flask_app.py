from flask import Flask, request, jsonify
from DataAccessLayer.models.candidateManager import CandidateManager
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


@app.route('/messenger_webhook', methods=["GET", "POST"])
def index():
    if request.method == 'GET':
        VERIFY_TOKEN = config.VERIFY_TOKEN
        if 'hub.mode' in request.args and 'hub.verify_token' in request.args:
            mode = request.args.get('hub.mode')
            token = request.args.get('hub.verify_token')
            if mode == 'subscribe' and token == VERIFY_TOKEN:
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
                    PAGE_ACCESS_TOKEN = config.PAGE_ACCESS_TOKEN
                    payload = {
                        'recipient': {'id': senderPsid},
                        'message': response,
                        'messaging_type': 'RESPONSE'
                    }
                    headers = {'content-type': 'application/json'}

                    url = 'https://graph.facebook.com/v10.0/me/messages?access_token={}'.format(PAGE_ACCESS_TOKEN)
                    r = requests.post(url, json=payload, headers=headers)
                    print(r.text)

                return 'EVENT_RECEIVED', 200
        else:
            return 'ERROR', 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
