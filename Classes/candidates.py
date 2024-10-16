from flask import Flask, request, jsonify
import psycopg2

app = Flask(__name__)

class CandidateManager:
    def __init__(self):
        self.conn = None
        self.cursor = None
    
    def connect_db(self):
        self.conn = psycopg2.connect(
            host='',
            database='',
            user='',
            password='',
            port='5432'
        )
        self.cursor = self.conn.cursor()
    

    def close_db(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def update_candidate(self, candidate_id, data):
        try:
            self.connect_db()

            update_query = """
                  SET first_name = %s, last_name = %s, email = %s, phone = %s, age = %s, addresse = %s, 

                    enrollment_start_timestamp = %s, enrollment_end_timestamp = %s, date_created = %s, date_updated = %s

                 WHERE id = %s

                  RETURNING id, first_name, last_name, email, phone, age, addresse, enrollment_start_timestamp, enrollment_end_timestamp, date_created, date_updated;

            """

            values = (
                data.get('first_name'),
                data.get('last_name'),
                data.get('email'),
                data.get('phone'),
                data.get('age'),
                data.get('addresse'),
                data.get('enrollment_start_timestamp'),
                data.get('enrollment_end_timestamp'),
                data.get('date_created'),
                data.get('date_updated'),
                candidate_id
            )

            self.cursor.execute(update_query, values)
            updated_candidate = self.cursor.fetchone()

            self.conn.commit()

            if not updated_candidate:
                return jsonify({"error": "Candidate not found"}), 404

            return jsonify({
                "message": "Candidate updated successfully",
                "candidate": {
                    "id": updated_candidate[0],
                    "first_name": updated_candidate[1],
                    "last_name": updated_candidate[2],
                    "email": updated_candidate[3],
                    "phone": updated_candidate[4],
                    "age": updated_candidate[5],
                    "addresse": updated_candidate[6],
                    "enrollment_start_timestamp": updated_candidate[7],
                    "enrollment_end_timestamp": updated_candidate[8],
                    "date_created": updated_candidate[9],
                    "date_updated": updated_candidate[10]
                }
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            self.close_db()
    
    def get_all_candidates(self):
        self.connect_db()
        
        self.cursor.execute('SELECT first_name, last_name, email, phone, age, addresse, enrollment_start_timestamp, enrollment_end_timestamp, date_created, date_updated FROM candidates')
        candidates = self.cursor.fetchall()
        
        self.close_db()
        
        return candidates
    
    def especific_candidate(self, candidate_id):
        self.connect_db()
        
        query = 'SELECT first_name, last_name, email, phone, age, addresse, enrollment_start_timestamp, enrollment_end_timestamp, date_created, date_updated FROM candidates WHERE id = %s'
        self.cursor.execute(query, (candidate_id,))
        candidate = self.cursor.fetchone()
        
        self.close_db()
        
        return candidate



if __name__ == '__main__':
    app.run(debug=True)
