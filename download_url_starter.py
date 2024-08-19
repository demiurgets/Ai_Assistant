import os
import zipfile
import glob
import json
import shutil
import subprocess
from bs4 import BeautifulSoup
import requests
from config_loader import load_config
#THIS STARTER FILE WILL TAKE A DOWNLOADED ZIP FROM LEARN3, AS WELL AS URLS AND SAVED PDFS/MP4S AND CREATE CHUNKS AND EMBEDDINGS 
config = load_config()

settings = {
    'openAi_assistant': 'asst_PfhKQbC3NCCnTVpw8osZjXeq',
    'openAi_key': '53Mu7zXn59m0dgxQRU7kT3BlbkFJgvRmEEpP907IMakf8FSc',
    'urls': [
        'https://www.tarrantcountytx.gov/en/veteran-services/va-benefit-programs/veterans-benefits-from-the-state-of-texas.html',
        'https://www.military.com/benefits/veteran-state-benefits/texas-state-veterans-benefits.html',
         "https://www.wati.io/blog/what-is-whatsapp-chatbot/"

    ],
    'course_id': 24,
    'chunk_size': 500,
    'results_size': 3,
    'results_length': 'medium'  
}

def find_most_recent_zip(downloads_path):
    zip_files = glob.glob(os.path.join(downloads_path, "*.zip"))
    if not zip_files:
        raise FileNotFoundError("No zip files found in the specified directory.")
    return max(zip_files, key=os.path.getctime)

def extract_files_from_zip(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    return extract_to

def find_index_files(extract_to, keyword):
    index_files = []
    for root, _, files in os.walk(extract_to):
        for file in files:
            if keyword in file and file.endswith('.html'):
                index_files.append(os.path.join(root, file))
    return index_files

def read_and_clean_html_files(file_paths):
    contents = []
    for file_path in file_paths:
        with open(file_path, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            links = soup.find_all('a', href=True)
            link_url = links[2]['href'] if len(links) >= 3 else None
            contents.append((os.path.basename(os.path.dirname(file_path)), text, link_url))
    return contents

def scrape_and_clean_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    response = requests.get(url, headers=headers)    
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve the web page. Status code: {response.status_code}")
    
    soup = BeautifulSoup(response.content, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    links = soup.find_all('a', href=True)
    link_url = links[2]['href'] if len(links) >= 3 else None
    return text, link_url

def split_document(content, chunk_size=500):
    sentences = content.split('. ')
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > chunk_size:  
            chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "
        else:
            current_chunk += sentence + ". "
    
    if current_chunk:  
        chunks.append(current_chunk.strip())
    
    return chunks

def main():
    downloads_path = os.path.expanduser("~/Downloads")
    current_directory = os.path.dirname(os.path.abspath(__file__))
    extract_to = os.path.join(downloads_path, "extracted_content")
    keyword = "index"
    os.makedirs(downloads_path, exist_ok=True)
    os.makedirs(extract_to, exist_ok=True)
    
    zip_path = find_most_recent_zip(downloads_path)
    extract_files_from_zip(zip_path, extract_to)
    index_files = find_index_files(extract_to, keyword)
    zip_contents = read_and_clean_html_files(index_files)
    
    all_chunks = []

    for title, text, link_url in zip_contents:
        doc_chunks = split_document(text, config['ai_assistant_settings']['processing']['chunk_size'])
        for i, chunk in enumerate(doc_chunks):
            all_chunks.append({
                "title": title,
                "content": chunk,
                "chunk_id": i,
                "link": link_url
            })
    
    for url in config['ai_assistant_settings']['scraping']['urls']:
        content, link_url = scrape_and_clean_url(url)
        doc_chunks = split_document(content, config['ai_assistant_settings']['processing']['chunk_size'])
        for i, chunk in enumerate(doc_chunks):
            all_chunks.append({
                "title": url,
                "content": chunk,
                "chunk_id": i,
                "link": link_url
            })
    
    subdirectory_path = os.path.join(current_directory, 'injestor', 'Stored_context')

    # Ensure the subdirectory path exists
    os.makedirs(subdirectory_path, exist_ok=True)

    # Define the output path for document_chunks.json
    output_path = os.path.join(subdirectory_path, 'document_chunks.json')
    
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            existing_chunks = json.load(f)
    else:
        existing_chunks = []
    
    existing_chunks.extend(all_chunks)
    
    with open(output_path, 'w') as f:
        json.dump(existing_chunks, f, indent=4)

    embedder_path = os.path.join(current_directory, 'Embedder')
    generate_embeddings_script = os.path.join(embedder_path, "generate_embeddings.py")
    subprocess.run(["python", generate_embeddings_script], check=True, cwd=embedder_path)  # Specify the working directory

    app_script = os.path.join(current_directory, "app.py")
    subprocess.run(["streamlit", "run", app_script], check=True, cwd=current_directory)  # Specify the working directory


if __name__ == "__main__":
    main()
