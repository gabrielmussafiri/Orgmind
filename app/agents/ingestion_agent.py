from typing import TypeDict , List , Optional
from langgraph.graph import StateGraph , END
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_slitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from lanchain_huggingface import HuggingFaceEmbeddings
import chromadb
import os


from app.config import settings

# --- State Definitions ---
class IngestionState(TypeDict):
    file_path : str
    org_id : int
    doc_id : int
    filename : str
    pages : List
    chunks : List
    chunk_count: int
    status : str
    error : Optional[str]

# --- Embedding function using HuggingFace ---
embedding_function = HuggingFaceEmbeddings(
    model_name ='all-MiniLM-L6-v2'
)



