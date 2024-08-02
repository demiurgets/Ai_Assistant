import os
import json

def read_json_content(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data

def split_content_into_chunks(content, chunk_size=500):
    chunks = []
    current_chunk = ""
    words = content.split()
    
    for word in words:
        if len(current_chunk) + len(word) + 1 > chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = word + " "
        else:
            current_chunk += word + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def main():
    downloads_folder = os.path.expanduser('~/Downloads')
    
    json_files = [
        os.path.join(downloads_folder, 'example.json'),
    ]
    
    output_file = 'document_chunks.json'
    
    all_chunks = []
    
    for json_file in json_files:
        json_content = read_json_content(json_file)

        if isinstance(json_content, dict):
            for key, value in json_content.items():
                doc_chunks = split_content_into_chunks(value)
                for i, chunk in enumerate(doc_chunks):
                    all_chunks.append({
                        "file_name": json_file,
                        "key": key,
                        "content": chunk,
                        "chunk_id": i
                    })
        elif isinstance(json_content, str):
            doc_chunks = split_content_into_chunks(json_content)
            for i, chunk in enumerate(doc_chunks):
                all_chunks.append({
                    "file_name": json_file,
                    "content": chunk,
                    "chunk_id": i
                })
    
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            existing_chunks = json.load(f)
    else:
        existing_chunks = []
    
    existing_chunks.extend(all_chunks)
    
    with open(output_file, 'w') as f:
        json.dump(existing_chunks, f, indent=4)

if __name__ == "__main__":
    main()
