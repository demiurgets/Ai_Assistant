import os
import json
import PyPDF2

folder_path = 'Stored_context'
json_file_path = os.path.join(folder_path, 'document_chunks.json')

chunk_size = 500

def split_text_into_chunks(text, chunk_size):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
        return text

if os.path.exists(json_file_path):
    with open(json_file_path, 'r') as json_file:
        chunks_data = json.load(json_file)
else:
    chunks_data = []

chunk_id_counter = 1

for pdf_filename in os.listdir(folder_path):
    if pdf_filename.endswith('.pdf'):
        pdf_path = os.path.join(folder_path, pdf_filename)
        text = extract_text_from_pdf(pdf_path)
        chunks = split_text_into_chunks(text, chunk_size)
        for chunk in chunks:
            chunk_data = {
                "title": pdf_filename,
                "content": chunk,
                "chunk_id": chunk_id_counter,
                "link": pdf_path  
            }
            chunks_data.append(chunk_data)
            chunk_id_counter += 1

with open(json_file_path, 'w') as json_file:
    json.dump(chunks_data, json_file, indent=4)

print(f"Processed {len(chunks_data)} chunks and saved to {json_file_path}")