import os
import json
import requests
from bs4 import BeautifulSoup
from config_loader import load_config

#I've had to put this file outside the injestor, because of issues accessing specific configs from a subdirectory.
#example sites to scrape: https://www.va.gov/disability/how-to-file-claim/
#https://www.military.com/benefits/veteran-state-benefits/texas-state-veterans-benefits.html
config = load_config()

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
    current_directory = os.path.dirname(os.path.abspath(__file__))
    all_chunks = []

    # Load existing chunks from JSON file
    subdirectory_path = os.path.join(current_directory, 'injestor', 'Stored_context')
    os.makedirs(subdirectory_path, exist_ok=True)
    output_path = os.path.join(subdirectory_path, 'document_chunks.json')
    
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            existing_chunks = json.load(f)
    else:
        existing_chunks = []

    existing_titles = {chunk['title'] for chunk in existing_chunks}

    for url in config['ai_assistant_settings']['scraping']['urls']:
        if url in existing_titles:
            print(f"URL '{url}' already exists in the JSON. Skipping.")
            continue

        content, link_url = scrape_and_clean_url(url)
        doc_chunks = split_document(content, config['ai_assistant_settings']['processing']['chunk_size'])
        for i, chunk in enumerate(doc_chunks):
            all_chunks.append({
                "title": url,
                "content": chunk,
                "chunk_id": i,
                "link": link_url
            })

    existing_chunks.extend(all_chunks)
    with open(output_path, 'w') as f:
        json.dump(existing_chunks, f, indent=4)

    embedder_path = os.path.join(current_directory, 'Embedder')
    generate_embeddings_script = os.path.join(embedder_path, "generate_embeddings.py")
    # subprocess.run(["python", generate_embeddings_script], check=True, cwd=embedder_path)  # Uncomment to run the script

    app_script = os.path.join(current_directory, "app.py")
    # subprocess.run(["streamlit", "run", app_script], check=True, cwd=current_directory)  # Uncomment to run the script

if __name__ == "__main__":
    main()