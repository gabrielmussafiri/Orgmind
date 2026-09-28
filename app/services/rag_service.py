from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_community.embeddings import SentenceTransformerEmbeddings
import chromadb
import os

from app.config import settings

# Embedding function using Groq
from langchain_community.embeddings import SentenceTransformerEmbeddings

embedding_function = SentenceTransformerEmbeddings(
    model_name ='all-MiniLM-L6-v2'
)

# ChromaDB client
chroma_client = chromadb.PersistentClient(
    path=settings.CHROMA_DB_PATH
)

# LLM(Groq)

llm = ChatGroq(
    api_key= settings.GROQ_API_KEY,
    model_name ="llama3-8b-8192",
    temperature=0.1
)

# Ingest document into ChromaDB

def ingest_document(file_path : str , org_id:int , doc_id:int , filename:str) -> int:
    # 1. Load Pdf
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    
    # 2. Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size =500,
        chunk_overlap =50
    )
    chunks =splitter.split_documents(pages)
    
    # 3. Add metadata to each chunk
    for chunk in chunks:
        chunk.metadata.update({
            "org_id": str(org_id),
            "doc_id":str(doc_id),
            "filename": filename
        })
    # 4. Store in ChromaDB
    collection_name = f'org_{org_id}'
    vectorstore = Chroma(
        client = chroma_client,
        collection_name= collection_name,
        embedding_function= embedding_function
    )
    vectorstore.add_documents(chunks)
    return len(chunks)

# Query ChromaDB and generate answer

def query_documents(question:str , org_id:int)-> dict:
    
    # 1. Get org's collection
    collection_name =f'org_{org_id}'
    vectorstore = Chroma(
        client= chroma_client,
        collection_name= collection_name,
        embedding_function= embedding_function
    )
    
    # 2. Search for relevant chunks
    results = vectorstore.similarity_search(question, k=5)
    
    if not results:
        return{
            "answer": 'No relevant documents found , Please Upload documents first',
            "sources":[]
        }
    # 3. Build Context from chunks
    context ="\n\n".join([doc.page_content for doc in results])
    sources = list(set([doc.metadata.get('filename','Unknown') for doc in results]))
    
    # 4. Build prompt
    prompt =f""" You are OrgMind , an AI assistant for humanitarian organisation and Company.
    Answer the question using ONLY the context provided below.
    Always cite which document you answer comes from.
    if the context doesn't contain the answer , say so clearlty.
    
    Context from organizational documents:
    {context}
    
    Question : {question}
    Answer:
    """
    # 5.Generate answer with Groq
    response = llm.invoke(prompt)
    
    return{
        "answer": response.content,
        'sources': sources
    }