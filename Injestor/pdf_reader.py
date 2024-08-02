import os
import json
import PyPDF2
import hashlib

# Define the path to the folder and JSON file
folder_path = 'Stored_context'
json_file_path = os.path.join(folder_path, 'document_chunks.json')

# Define chunk size (number of characters per chunk)
chunk_size = 500

# Function to generate a unique chunk ID
def generate_chunk_id(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()

# Function to split text into chunks
def split_text_into_chunks(text, chunk_size):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

# Function to extract text from a PDF
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
    return text

# Load existing chunks from JSON file if it exists
if os.path.exists(json_file_path):
    with open(json_file_path, 'r') as json_file:
        chunks_data = json.load(json_file)
else:
    chunks_data = []

# Process each PDF in the folder
for pdf_filename in os.listdir(folder_path):
    if pdf_filename.endswith('.pdf'):
        pdf_path = os.path.join(folder_path, pdf_filename)
        text = extract_text_from_pdf(pdf_path)
        chunks = split_text_into_chunks(text, chunk_size)
        
        for i, chunk in enumerate(chunks):
            chunk_data = {
                "title": pdf_filename,
                "content": chunk,
                "chunk_id": generate_chunk_id(chunk),
                "link": os.path.basename(pdf_path)
            }
            chunks_data.append(chunk_data)

# Save the updated chunks to the JSON file
with open(json_file_path, 'w') as json_file:
    json.dump(chunks_data, json_file, indent=4)

print(f"Processed {len(chunks_data)} chunks and saved to {json_file_path}")
