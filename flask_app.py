from flask import Flask, request, jsonify
from whatsapp_controller import recieve_query_from_whatsapp

app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process_data():
    # Get data from the POST request
    data = request.json
    print(f"Received data: {data}")
    
    # Process the data (here, we're just echoing it)
    processed_data = f"Processed: {data['message']}"
    response = recieve_query_from_whatsapp(data['message'], data['number'])

    # Return a response
    return jsonify({"processed_message": response}), 200


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

@app.route('/applicants', methods=['GET'])
def get_applicants():
    with open('Stored_context/applicants.json', 'r') as file:
        applicants_data = json.load(file)
    return jsonify(applicants_data), 200

@app.route('/applicant/<int:applicant_id>', methods=['GET'])
def get_applicant_details(applicant_id):
    with open('Stored_context/applicants.json', 'r') as file:
        applicants_data = json.load(file)
        for applicant in applicants_data:
            if applicant.get('id') == applicant_id:
                return jsonify(applicant), 200
    return jsonify({"message": "Applicant not found"}), 404
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
