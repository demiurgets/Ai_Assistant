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
import time
import shutil
import PyPDF2



# Load the .env file
load_dotenv()

api_key = os.getenv('API_KEY')
reader_id = os.getenv('ASST_ID_READER')
interviewer_id = os.getenv('ASST_INTERVIEWER')
admin_assistant_id = os.getenv('ASST_ADMIN')
cv_analyzer = os.getenv('CV_ANALYZER')

config = load_config()
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

document_embeddings = np.load('Stored_context/document_embeddings.npy')
with open('Stored_context/document_chunks.json', 'r') as f:
    document_metadata = json.load(f)

dimension = document_embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(document_embeddings)

model_name = "sentence-transformers/all-MiniLM-L6-v2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

def analyze_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
            key = api_key
    asstId = cv_analyzer
    client = OpenAI(api_key=key)
    thread = client.beta.threads.create()

    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=text
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
       
        response = "Error processing request with AI Assistant"
    print(response)
    folder_path = os.path.join(os.getcwd(), 'Stored_context')
    file_path = os.path.join(folder_path, 'cv_reports.json')
    
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print("made file")
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            all_data = json.load(f)
    else:
        all_data = []
    
    all_data.append(response)
    
    with open(file_path, 'w') as f:
        json.dump(all_data, f, indent=4)

def get_embedding(text):
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

def search(query):
    result_length = config['ai_assistant_settings']['processing']['result_length']
    query_embedding = get_embedding(query).reshape(1, -1)
    D, I = index.search(query_embedding, k=result_length)
    
    # Debugging print statements
    print(f"Indices from search: {I}")
    print(f"Document metadata length: {len(document_metadata)}")
    
    # Ensure indices are within bounds
    if all(i < len(document_metadata) for i in I[0]):
        results = [document_metadata[i] for i in I[0]]
    else:
        results = []
    
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

#wrapper method for admin messages/threads
def admin_query(query, thread_id):
    key = api_key
    asstId = admin_assistant_id
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

#wrapper method for an embeddings search pointed to reader asst
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
    pdf_folder = os.path.join(os.getcwd(),  'Stored_context')
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]
    return pdf_files

def delete_pdf(pdf_name):
    pdf_path = os.path.join(os.getcwd(), 'Stored_context', pdf_name)
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    with open('Stored_context/document_chunks.json', 'r') as f:
        document_metadata = json.load(f)
    document_metadata = [chunk for chunk in document_metadata if chunk['title'] != pdf_name]
    with open('Stored_context/document_chunks.json', 'w') as f:
        json.dump(document_metadata, f, indent=4)

def delete_url(url):
    with open('Stored_context/document_chunks.json', 'r') as f:
        document_metadata = json.load(f)
    document_metadata = [chunk for chunk in document_metadata if chunk['title'] != url]
    with open('Stored_context/document_chunks.json', 'w') as f:
        json.dump(document_metadata, f, indent=4)

def assistant_generate_json(thread_id):
    key = api_key
    asstId = interviewer_id
    client = OpenAI(api_key=key)
    query = "Using all the information you just received, generate a JSON with the following fields: name, age, location, position, experience, lead source, availability, contact."
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
        save_applicant_json(json_data)
        return True
    return False



def save_applicant_json(json_data):
    """Save the extracted JSON data to 'applicants.json' inside 'Injestor/Stored_context'."""
    folder_path = os.path.join(os.getcwd(), 'Stored_context')
    file_path = os.path.join(folder_path, 'applicants.json')
    
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            all_data = json.load(f)
    else:
        all_data = []
    
    all_data.append(json_data)
    
    # Move the uploaded CV file to the final destination folder
    temp_folder_path = os.path.join(os.getcwd(),  'Stored_context', 'temp_uploaded_Cvs')
    final_folder_path = os.path.join(os.getcwd(), 'Stored_context', 'uploaded_Cvs')
    
    if os.path.exists(temp_folder_path):
        for file_name in os.listdir(temp_folder_path):
            shutil.move(os.path.join(temp_folder_path, file_name), final_folder_path)
    
    with open(file_path, 'w') as f:
        json.dump(all_data, f, indent=4)

#here we update the admin bot instructions with new applicant
    textInstructions = "You are an assistant to a job interviewer. You keep track of all the applicants and answer any questions about them. Be warm and kind"
    all_data_str = json.dumps(all_data)  

    client = OpenAI(api_key=api_key)

    my_updated_assistant = client.beta.assistants.update(
        admin_assistant_id,
        instructions=textInstructions + all_data_str
    )
def upload_cv():
    uploaded_file = st.file_uploader("Upload your CV (PDF or Word document)", type=["pdf", "docx"])
    
    if 'cv_uploaded' not in st.session_state:
        st.session_state.cv_uploaded = False
    
    if uploaded_file is not None:
        if not st.session_state.cv_uploaded:
            # Save the uploaded file to a temporary folder
            temp_folder_path = os.path.join(os.getcwd(), 'Stored_context', 'temp_uploaded_Cvs')
            if not os.path.exists(temp_folder_path):
                os.makedirs(temp_folder_path)
            
            file_path = os.path.join(temp_folder_path, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.session_state.cv_uploaded = True
            analysis = analyze_pdf(file_path)
            st.success("CV uploaded successfully to the temporary folder!")

        else:
            st.warning("You can only upload one CV per session.")

#Sends a message and updates chat history
def message_send():
    query = st.session_state.query_input
    response_length = st.session_state.response_length

    # Clear the input box
    st.session_state.query_input = ""

    # Add user message to chat history
    st.session_state.chat_history.append({'role': 'user', 'content': query})

    if query.lower().startswith("tell me"):
        assistant_response_text = embeddings_search(query, response_length)
    elif st.session_state.admin_conversation:
        if st.session_state.password_correct == False:
            st.error(f"Enter admin password")
            assistant_response_text = "Enter the admin password to access applicant data"
        else:
            if st.session_state.admin_thread_id is None:
                key = api_key
                client = OpenAI(api_key=key)
                adminThread = client.beta.threads.create()
                st.session_state.admin_thread_id = adminThread.id

            assistant_response_text = admin_query(query, st.session_state.admin_thread_id)
    else:
        # Create a new thread if it does not exist
        if st.session_state.thread_id is None:
            key = api_key
            client = OpenAI(api_key=key)
            thread = client.beta.threads.create()
            st.session_state.thread_id = thread.id
        assistant_response_text = assistant_response(st.session_state.thread_id, query, response_length)

    # Add assistant response to chat history
    finalMessageFound = detect_trigger_string(assistant_response_text, st.session_state.thread_id)
    st.session_state.chat_history.append({'role': 'assistant', 'content': assistant_response_text})

    # Display the assistant's response
    #st.text_area("Assistant:", value=assistant_response_text, disabled=True, height=150)

    if query.lower().startswith("tell me"):
        st.subheader("Response Sources")
        results = search(query)
        for result in results:
            st.write(f"Document: {result['title']}")
            st.write(f"Chunk {result['chunk_id']}")
            st.write(f"Content: {result['content']}")
            st.write(f"Link: {result['link']}")
            st.write("__________________________")

# Load the applicants data from the JSON file
def load_applicants():
    with open(os.path.join('Stored_context', 'applicants.json'), 'r') as f:
        applicants = json.load(f)
    return applicants
def save_applicants(applicants):
    with open(os.path.join('Stored_context', 'applicants.json'), 'w') as f:
        json.dump(applicants, f, indent=4)


# Define the path to your text file in the Stored_context folder
def get_file_path():
    base_dir = os.path.dirname(__file__)  # Directory of the current script
    stored_context_dir = os.path.join(base_dir, 'Stored_context')
    return os.path.join(stored_context_dir, 'interviewer_instructions.txt')

# Load instructions from the text file
def load_instructions(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            return file.read()
    except UnicodeDecodeError as e:
        st.error(f"Error decoding file {file_path}: {e}")
        return ""
# Save instructions to the text file
def save_instructions(file_path, text):
    with open(file_path, 'w') as file:
        file.write(text)
    client = OpenAI(api_key=api_key)

    my_updated_assistant = client.beta.assistants.update(
    interviewer_id,
    instructions=text
    )




def main():
    st.markdown("""
        <style>
        .chat-container {
            display: flex;
            flex-direction: column;
            width: 100%;
            max-width: 800px;
            margin: auto;
        }
        .chat-bubble {
            max-width: 70%;
            padding: 10px 15px;
            margin: 5px;
            border-radius: 10px;
            font-size: 14px;
            line-height: 1.5;
            color: #333; /* Dark color for text */
        }
        .user-bubble {
            background-color: #DCF8C6;
            align-self: flex-end;
        }
        .assistant-bubble {
            background-color: #FFFFFF;
            align-self: flex-start;
            border: 1px solid #E1E1E1;
        }
        </style>
        """, unsafe_allow_html=True)
    
    st.title("Welcome")
    if 'urls' not in st.session_state:
        st.session_state.urls = load_urls()
    if 'thread_id' not in st.session_state:
        st.session_state.thread_id = None
    if 'admin_thread_id' not in st.session_state:
        st.session_state.admin_thread_id = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'admin_conversation' not in st.session_state:
        st.session_state.admin_conversation = None
    # Initialize the session state for the password
    if 'password_correct' not in st.session_state:
        st.session_state.password_correct = False
    if 'phone_number' not in st.session_state:
        st.session_state.phone_number = None
    if 'cv_uploaded' not in st.session_state:
        st.session_state.cv_uploaded = False

    correct_password = "admin"
    with st.expander("Manage"):

        password = st.text_input("Admin password required", type="password")
        
        # Add a button to verify the password
        if st.button("Enter"):
            if password == correct_password:
                st.session_state.password_correct = True
                st.success("Access granted")
            else:
                st.error("Access denied. Please enter the correct password.")

        if st.session_state.password_correct:

            if st.checkbox("Applicants"):
                applicants = load_applicants()
                applicants_str = json.dumps(applicants, indent=4)
                # Add the download button
                st.download_button(
                    label="Download Applicants",
                    data=applicants_str,
                    file_name='applicants.json',
                    mime='application/json'
                )
                st.table(applicants)

                if st.checkbox("Edit Applicants"):
                    editable_applicants = st.text_area("Applicants JSON", value=applicants_str, height=300)
                    if st.button("Save Changes"):
                        try:
                            updated_applicants = json.loads(editable_applicants)
                            save_applicants(updated_applicants)
                            st.success("Applicants data saved successfully!")
                        except json.JSONDecodeError:
                            st.error("Invalid JSON format. Please correct it and try again.")

                    for i, applicant in enumerate(applicants):
                        if st.button(f"Delete Applicant {i}"):
                            applicants.pop(i)
                            save_applicants(applicants)
                            st.success(f"Applicant {i} deleted successfully!")

            if st.checkbox("Interviewer's Script"):
                file_path = get_file_path()
                # Load and display instructions
                if os.path.exists(file_path):
                    instructions = load_instructions(file_path)
                    st.text_area("Instructions", instructions, height=300, key='instructions')

                    # Save instructions
                    if st.button("Save Instructions"):
                        updated_instructions = st.session_state['instructions']
                        save_instructions(file_path, updated_instructions)
                        st.success("Instructions saved successfully!")
                else:
                    st.error(f"File not found: {file_path}")

            st.subheader("NOTE: For deep searches on uploaded content, start message with 'tell me'.")

            pdf_file = st.file_uploader("Upload a PDF", type="pdf")
            video_file = st.file_uploader("Upload a video (under construction)", type=["mp4", "avi", "mov"])
            if pdf_file:
                pdf_filename = pdf_file.name
                pdf_path = os.path.join("Stored_context", pdf_filename)
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
                    #streamlit_js_eval(js_expressions="parent.window.location.reload()")

            st.subheader("PDF Names")
            pdf_names = load_pdfs()
            for i, pdf in enumerate(pdf_names):
                cols = st.columns([3, 1])
                pdf_link = f'<a href="Stored_context/{pdf}" target="_blank">{pdf}</a>'
                cols[0].markdown(pdf_link, unsafe_allow_html=True)
                if cols[1].button("Delete", key=f"delete_pdf_{i}"):
                    delete_pdf(pdf)
                    #streamlit_js_eval(js_expressions="parent.window.location.reload()")

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

    if st.session_state.password_correct:
        admin_conversation = st.checkbox("Admin Chat")
        if admin_conversation:
            st.session_state.admin_conversation = True
        else:
            st.session_state.admin_conversation = False

    # Step 1: Phone number input
    if not st.session_state.phone_number:
        phone_number = st.text_input("Please enter your phone number:")
        
        if st.button("Submit Phone Number"):
            if phone_number:
                st.session_state.phone_number = phone_number
                #create_empty_record(phone_number)  # Create an empty record in DB
                st.success("Phone number submitted successfully!")
            else:
                st.error("Please enter a valid phone number.")
    
    # Display chat history
    if st.session_state.phone_number:
        st.subheader("Chat")
        for message in st.session_state.chat_history:
            if message['role'] == 'user':
                st.markdown(f'<div class="chat-bubble user-bubble">{message["content"]}</div>', unsafe_allow_html=True)
            elif message['role'] == 'assistant':
                st.markdown(f'<div class="chat-bubble assistant-bubble">{message["content"]}</div>', unsafe_allow_html=True)

        #st.session_state.response_length = st.selectbox("Select response length:", ["One Sentence", "One Paragraph", "Multiple paragraphs"])
        st.session_state.response_length = "One paragraph"

        query = st.text_input("", key="query_input", on_change=message_send)

        if not st.session_state.cv_uploaded:
            upload_cv()
        else:
            st.write("You have already uploaded a CV in this session.")


if __name__ == "__main__":
    main()


