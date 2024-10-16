from flask import Flask, request, jsonify
from Classes.candidates import CandidateManager
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

# New endpoints
@app.route('', methods=['PUT'])
def update_candidate_route():
    data = request.json
    candidate_manager = CandidateManager()
    return candidate_manager.update_candidate(data["candidate_id"], data)

@app.route('', methods=['GET'])
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

@app.route('', methods=['GET'])
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
