import openai
import tiktoken
from dotenv import load_dotenv
import os
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from DataAccessLayer.models.positions import Positions
from sqlalchemy import update
import numpy as np
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore


load_dotenv(override=True)

dbname = os.getenv("dbname")
user = os.getenv("user")
password = os.getenv("password")
host = os.getenv("host")
port = os.getenv("pg_port")

# Database URL
database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)

openai.api_key = os.getenv("API_KEY")


def formatted_text_for_position_embedding(position):
    # Use default values for potentially null fields
    name = position.get("name") or "No name provided"
    description = position.get("description") or "No description found"
    key_responsibilities = position.get("key_responsibilities") or []
    qualifications = position.get("qualifications") or []

    formatted_text = f"Name: {name} - Description: {description}"

    # Add key responsibilities and qualifications if provided
    if key_responsibilities:
        formatted_text += f" - Key Responsibilities: {', '.join(key_responsibilities)}"
    if qualifications:
        formatted_text += f" - Qualifications: {', '.join(qualifications)}"

    return formatted_text


def get_positions_with_embeddings():
    try:
        # Fetch positions from the database where is_active is True
        positions = (
            db_session.query(Positions).filter(Positions.is_active == True).all()
        )

        positions_data = [
            {
                "id": pos.id,
                "name": pos.name,
                "description": pos.description,
                "key_responsibilities": pos.key_responsibilities,
                "qualifications": pos.qualifications,
                "position_embedding": pos.position_embedding,
            }
            for pos in positions
        ]
        documents = []
        for position in positions_data:
            # Extract the embedding
            embedding = np.array(position["position_embedding"])

            # Create the page_content as a concatenation of the fields
            page_content = formatted_text_for_position_embedding(position)

            # Create a Document object for LangChain, storing the embedding in the metadata
            document = Document(
                page_content=page_content,
                metadata={
                    "id": position["id"],
                    "source": dbname,
                    "embedding": embedding,
                },  # Adding embedding to metadata
            )
            documents.append(document)

        return documents

    except SQLAlchemyError as e:
        print(f"Error fetching positions: {e}")
        db_session.rollback()
        return []
    finally:
        db_session.remove()


def add_documents_to_vector_store(vector_store):
    """
    This function retrieves documents from the database and adds them to the vector store.
    The documents are added along with their embeddings.
    """
    # Get the positions with embeddings
    documents = get_positions_with_embeddings()

    if not documents:
        print("No documents to add.")
        return

    # Add documents to the vector store
    try:
        vector_store.add_documents(
            documents, embeddings=[doc.metadata["embedding"] for doc in documents]
        )
        print(f"Added {len(documents)} documents to the vector store.")

    except Exception as e:
        print(f"Error adding documents to vector store: {e}")


def run_similarity_search(query, k=5, filter=None, threshold=1.0):
    """
    This function tests similarity search by querying the vector store and returning the top k most similar documents.

    :param query: The query string for similarity search.
    :param k: The number of similar documents to retrieve (default is 5).
    :param filter: An optional filter for metadata (e.g., by source).
    :param threshold: A threshold to filter documents by their similarity score (0-2, lower means similar)
    :return: List of similar documents with their metadata.
    """
    try:

        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small", openai_api_key=openai.api_key
        )
        index = faiss.IndexFlatL2(len(embeddings.embed_query("hello world")))

        vector_store = FAISS(
            embedding_function=embeddings,
            index=index,
            docstore=InMemoryDocstore(),
            index_to_docstore_id={},
        )

        # Add documents (positions) to the vector store
        add_documents_to_vector_store(vector_store)

        # Perform the similarity search and filter by given threshold (default <= 1.0)
        results = vector_store.similarity_search_with_score(query, k=k, filter=filter)
        filtered_results = [
            (doc, score) for doc, score in results if score <= threshold
        ]

        if not filtered_results:
            print("No similar documents found.")
            return []

        clear_faiss_vector_store(vector_store)

        return filtered_results

    except Exception as e:
        print(f"Error performing similarity search: {e}")
        clear_faiss_vector_store(vector_store)
        return []


def clear_faiss_vector_store(vector_store):
    # Clear the FAISS index and docstore
    vector_store.index.reset()
    vector_store.index_to_docstore_id = {}
    print("FAISS vector store cleared.")


# query = "Job experience in software development or software engineering with great responsibilities, develop solutions with software technologies."
# query = "Experience in eating pies, working hard and being funny "
# query = "Job experience in sales, driving sales iniciatives in business and working along different customers and providers"
# query = "Experience in finance, accounting, financial risk management, working along customers and tracking trading operations "
query = "Experience eating, engaging with hamburger business owners and give feedback about their products"
filter_metadata = {"source": dbname}  # Example filter (optional)

similar_documents = run_similarity_search(query, k=5, filter=filter_metadata)
similar_documents_results = [
    (res.metadata.get("id"), (res.page_content), score)
    for res, score in similar_documents
]

# Sort the list of tuples by score in descending order
id_and_score_tuples = [(tuple[0], tuple[2]) for tuple in similar_documents_results]

print(f"Top similar documents for the query: '{query}':\n")

for tuple in similar_documents_results:
    print(tuple)


for tuple in id_and_score_tuples:
    print(tuple)


# clear_faiss_vector_store(vector_store)
