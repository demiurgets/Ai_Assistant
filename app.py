import streamlit as st
from streamlit_js_eval import streamlit_js_eval
import numpy as np
import json
import faiss
import torch
from transformers import AutoTokenizer, AutoModel
from openai import OpenAI
import os
import subprocess
import re
from config_loader import load_config
import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# Access the API keys
api_key = os.getenv('API_KEY')
reader_id = os.getenv('ASST_ID_READER')
interviewer_id = os.getenv('ASST_INTERVIEWER')

config = load_config()
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

document_embeddings = np.load('Injestor/Stored_context/document_embeddings.npy')
with open('Injestor/Stored_context/document_chunks.json', 'r') as f:
    document_metadata = json.load(f)

dimension = document_embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(document_embeddings)

model_name = "sentence-transformers/all-MiniLM-L6-v2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

def get_embedding(text):
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

def search(query):
    result_length = config['ai_assistant_settings']['processing']['result_length']
    query_embedding = get_embedding(query).reshape(1, -1)
    D, I = index.search(query_embedding, k=result_length)
    results = [document_metadata[i] for i in I[0]]
    return results

def assistant_response(thread_id, query, response_length):
    key = api_key
    asstId = interviewer_id
    client = OpenAI(api_key=key)
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=query
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=asstId,
    )
    response = "Error with AI API"
    if run.status == 'completed':
        response_page = client.beta.threads.messages.list(thread_id=thread_id)
        response = response_page.data[0].content[0].text.value
    else:
        response = "Error processing request with AI Assistant"
    return response

def embeddings_search(query, response_length):
    key = api_key
    asstId = reader_id
    client = OpenAI(api_key=key)
    thread = client.beta.threads.create()
    contextResults = search(query)
    context_str = "\n\n".join([f"Title: {result['title']}\nChunk ID: {result['chunk_id']}\nContent: {result['content']}" for result in contextResults])
    length_specification = f" in {response_length}"
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="Analyze this information: " + context_str + " to answer this: " + query + length_specification
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=asstId,
    )
    response = "Error with AI API"
    if run.status == 'completed':
        response_page = client.beta.threads.messages.list(thread_id=thread.id)
        response = response_page.data[0].content[0].text.value
    else:
        response = "Error processing request with OpenAI"
    return response

def load_urls():
    with open('config.json', 'r') as f:
        config_data = json.load(f)
    return config_data['ai_assistant_settings']['scraping']['urls']

def save_urls(urls):
    with open('config.json', 'r') as f:
        config_data = json.load(f)
    config_data['ai_assistant_settings']['scraping']['urls'] = urls
    with open('config.json', 'w') as f:
        json.dump(config_data, f, indent=4)

def load_pdfs():
    pdf_folder = os.path.join(os.getcwd(), 'Injestor', 'Stored_context')
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]
    return pdf_files

def delete_pdf(pdf_name):
    pdf_path = os.path.join(os.getcwd(), 'Injestor', 'Stored_context', pdf_name)
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    with open('Injestor/Stored_context/document_chunks.json', 'r') as f:
        document_metadata = json.load(f)
    document_metadata = [chunk for chunk in document_metadata if chunk['title'] != pdf_name]
    with open('Injestor/Stored_context/document_chunks.json', 'w') as f:
        json.dump(document_metadata, f, indent=4)

def delete_url(url):
    with open('Injestor/Stored_context/document_chunks.json', 'r') as f:
        document_metadata = json.load(f)
    document_metadata = [chunk for chunk in document_metadata if chunk['title'] != url]
    with open('Injestor/Stored_context/document_chunks.json', 'w') as f:
        json.dump(document_metadata, f, indent=4)

def assistant_generate_json(thread_id):
    key = api_key
    asstId = interviewer_id
    client = OpenAI(api_key=key)
    query = "Using all the information you just received, generate a JSON with the following fields: name, age, location, position, experience, contact."
    message = client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=query
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id, assistant_id=asstId,
    )
    response = "Error with AI API"
    if run.status == 'completed':
        response_page = client.beta.threads.messages.list(thread_id=thread_id)
        response = response_page.data[0].content[0].text.value
    else:
        response = "Error processing request with AI Assistant"
    return response

def detect_trigger_string(text, thread_id):
    """Detect 'have a great day' string and trigger AI assistant."""
    trigger_phrase = "have a great day"
    print("TRIGGERED")
    if trigger_phrase in text.lower():
        json_response = assistant_generate_json(thread_id)
        json_data = json.loads(json_response)
        print(json_data)
        save_extracted_json(json_data)
        return True
    return False

def save_extracted_json(json_data):
    """Save the extracted JSON data to 'applicants.json' inside 'Injestor/Stored_context'."""
    folder_path = os.path.join(os.getcwd(), 'Injestor', 'Stored_context')
    file_path = os.path.join(folder_path, 'applicants.json')
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            all_data = json.load(f)
    else:
        all_data = []
    all_data.append(json_data)
    with open(file_path, 'w') as f:
        json.dump(all_data, f, indent=4)

def main():
    st.title("AI Assistant")

    if 'urls' not in st.session_state:
        st.session_state.urls = load_urls()

    if 'thread_id' not in st.session_state:
        st.session_state.thread_id = None

    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    with st.expander("Manage Context"):
        pdf_file = st.file_uploader("Upload a PDF", type="pdf")
        video_file = st.file_uploader("Upload a video", type=["mp4", "avi", "mov"])

        if pdf_file:
            pdf_filename = pdf_file.name
            pdf_path = os.path.join("Injestor", "Stored_context", pdf_filename)
            with open(pdf_path, "wb") as f:
                f.write(pdf_file.getbuffer())
            injestor_path = os.path.join(os.getcwd(), 'Injestor')
            subprocess.run(["python", "pdf_reader.py"], check=True, cwd=injestor_path)
            st.success("PDF has been uploaded successfully.")
            streamlit_js_eval(js_expressions="parent.window.location.reload()")

        st.subheader("URLs")
        new_url = st.text_input("Add new URL:")
        if st.button("Add URL"):
            if new_url:
                if new_url not in st.session_state.urls:
                    st.session_state.urls.append(new_url)
                    save_urls(st.session_state.urls)
                    cwdpath = os.path.join(os.getcwd())
                    subprocess.run(["python", "url_scraper.py"], check=True, cwd=cwdpath)
                else:
                    st.warning("URL already exists in the list.")

        for i, url in enumerate(st.session_state.urls):
            cols = st.columns([3, 1])
            cols[0].write(url)
            if cols[1].button("Delete", key=f"delete_url_{i}"):
                st.session_state.urls.pop(i)
                save_urls(st.session_state.urls)
                delete_url(url)
                streamlit_js_eval(js_expressions="parent.window.location.reload()")

        st.subheader("PDF Names")
        pdf_names = load_pdfs()
        for i, pdf in enumerate(pdf_names):
            cols = st.columns([3, 1])
            pdf_link = f'<a href="Injestor/Stored_context/{pdf}" target="_blank">{pdf}</a>'
            cols[0].markdown(pdf_link, unsafe_allow_html=True)
            if cols[1].button("Delete", key=f"delete_pdf_{i}"):
                delete_pdf(pdf)
                streamlit_js_eval(js_expressions="parent.window.location.reload()")

        st.subheader("Video Names")
        video_names = [{"name": "example.mp4", "delete": False}, {"name": "another-example.mp4", "delete": False}]
        for i, video in enumerate(video_names):
            cols = st.columns([3, 1])
            cols[0].write(video["name"])
            if cols[1].button("Delete", key=f"delete_video_{i}"):
                video_names.pop(i)

        if st.button("Generate Embeddings"):
            embedder_path = os.path.join(os.getcwd(), 'Embedder')
            subprocess.run(["python", "generate_embeddings.py"], check=True, cwd=embedder_path)
            st.success("Embeddings have been generated successfully.")

    # Display chat history
    st.subheader("Chat History")
    for message in st.session_state.chat_history:
        if message['role'] == 'user':
            st.write(f"You: {message['content']}")
        elif message['role'] == 'assistant':
            st.write(f"Assistant: {message['content']}")
            

    response_length = st.selectbox("Select response length:", ["One Sentence", "One Paragraph", "Multiple paragraphs"])
    query = st.text_input("Enter your query:")

    if query:
        # Add user message to chat history
        st.session_state.chat_history.append({'role': 'user', 'content': query})

        if query.lower().startswith("tell me"):
            assistant_response_text = embeddings_search(query, response_length)
        else:
            # Create a new thread if it does not exist
            if st.session_state.thread_id is None:
                key = api_key
                client = OpenAI(api_key=key)
                thread = client.beta.threads.create()
                st.session_state.thread_id = thread.id
            assistant_response_text = assistant_response(st.session_state.thread_id, query, response_length)

        # Add assistant response to chat history
        finalMessageFound = detect_trigger_string(assistant_response_text,  st.session_state.thread_id)
        st.session_state.chat_history.append({'role': 'assistant', 'content': assistant_response_text})

        # Display the assistant's response
        st.text_area("Assistant:", value=assistant_response_text, disabled=True, height=150)
        
        st.subheader("Response Sources")
 
        if query.lower().startswith("tell me"):
            results = search(query)
            for result in results:
                st.write(f"Document: {result['title']}")
                st.write(f"Chunk {result['chunk_id']}")
                st.write(f"Content: {result['content']}")
                st.write(f"Link: {result['link']}")
                st.write("__________________________")

if __name__ == "__main__":
    main()
