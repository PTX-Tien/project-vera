import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
# --- CHANGED IMPORT TO FIX WARNING ---
from langchain_huggingface import HuggingFaceEmbeddings 
from langchain_core.tools import tool

# Global variable to store the retriever instance temporarily
CURRENT_RETRIEVER = None

def process_document(file_path):
    """
    Reads a PDF, chunks it, and creates a searchable Vector Store.
    """
    global CURRENT_RETRIEVER
    
    # 1. Load the PDF
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    
    # 2. Split into chunks (smaller pieces are easier to match)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    splits = text_splitter.split_documents(docs)
    
    # 3. Create Embeddings (Local CPU model - Free & Fast)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # 4. Create Vector Store
    vectorstore = FAISS.from_documents(splits, embeddings)
    
    # 5. Create a Retriever interface
    CURRENT_RETRIEVER = vectorstore.as_retriever()
    return True

@tool
def lookup_document(query: str):
    """
    Use this tool to search for information inside the uploaded PDF document.
    Input should be a specific question or keyword related to the document.
    """
    if CURRENT_RETRIEVER is None:
        return "Error: No document has been uploaded yet."
    
    # Retrieve relevant chunks
    docs = CURRENT_RETRIEVER.invoke(query)
    
    # Combine chunks into a single string context
    return "\n\n".join([doc.page_content for doc in docs])

# --- ADD THIS FUNCTION AT THE END ---
def is_document_uploaded():
    """Returns True if a document is currently loaded in memory."""
    return CURRENT_RETRIEVER is not None