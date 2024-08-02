import json
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
import os

# This script will take file of chunks and create file of embeddings and metadata

model_name = "sentence-transformers/all-MiniLM-L6-v2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

def get_embedding(text):
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

# Construct the path to the document_chunks.json file
current_directory = os.path.dirname(os.path.abspath(__file__))
document_chunks_path = os.path.join(current_directory, '..', 'Injestor', 'Stored_context', 'document_chunks.json')

# Load the document chunks
with open(document_chunks_path, 'r') as f:
    chunks = json.load(f)

embeddings = []
metadata = []

for chunk in chunks:
    embedding = get_embedding(chunk["content"])
    embeddings.append(embedding)
    metadata.append({
        "title": chunk["title"],
        "chunk_id": chunk["chunk_id"],
        "link": chunk["link"],
        "content": chunk["content"]
    })

np.save('../Injestor/Stored_context/document_embeddings.npy', embeddings)

with open('document_metadata.json', 'w') as f:
    json.dump(metadata, f, indent=4)
