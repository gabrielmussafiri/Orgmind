
# ============================================================
# 1. IMPORTS
# ============================================================

import chromadb

from rank_bm25 import BM25Okapi

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import settings


# ============================================================
# 2. CONFIGURATION: EMBEDDINGS AND TEXT SPLITTER
# ============================================================

# Converts text into numerical vectors for semantic search.
embedding_function = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2"
)

# Splits PDF pages into smaller text chunks.
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)


# ============================================================
# 3. CONNECT TO THE EXISTING CHROMA DATABASE
# ============================================================

chroma_client = chromadb.PersistentClient(
    path=settings.CHROMA_DB_PATH
)

# Connect to the collection containing OrgMind's stored chunks.
collection = chroma_client.get_collection(name="org_1")

# Optional: check how many chunks are stored.
# print(f"Stored chunks: {collection.count()}")


# ============================================================
# 4. LOAD STORED CHUNK IDS AND TEXT
# ============================================================

# Retrieve the stored documents and their corresponding IDs.
results = collection.get(
    include=["documents"]
)

document_ids = results["ids"]
documents = results["documents"]

print("Number of IDs:", len(document_ids))
print("Number of documents:", len(documents))

# Each document_ids[i] belongs to documents[i].
# Keep these lists aligned throughout the experiments.


# ============================================================
# 5. INSPECT THE TARGET FUNDING TABLE
# ============================================================

target_text = "2024 Top funding countries"

matching_chunks = 0

for document in documents:
    if document and target_text in document:
        matching_chunks += 1

        # Uncomment to inspect the complete matching chunk.
        # print(document)

print("Matching chunks:", matching_chunks)


# ============================================================
# 6. DENSE RETRIEVAL: SEARCH WITH CHROMA
# ============================================================

def retrieve_documents(
    question: str,
    org_id: int,
    k: int = 5,
    doc_id: str = "2"
):
    collection_name = f"org_{org_id}"

    vectorstore = Chroma(
        client=chroma_client,
        collection_name=collection_name,
        embedding_function=embedding_function
    )

    # Currently restricted to document ID "2" (the 2024 report).
    # Remove or change this filter when testing other documents.
    retrieved_results = vectorstore.similarity_search_with_score(question,k=k,filter={"doc_id": doc_id})

    return retrieved_results


# ============================================================
# 7. TEST DENSE RETRIEVAL
# ============================================================

question = "What is the 2024 top funding countries?"

dense_results = retrieve_documents(question=question,org_id=1,k=20,doc_id="2")

for rank, (document, distance) in enumerate(dense_results,start=1):
    document , distance = dense_results[0]
    print(document.page_content[:100])
    print(document.metadata)
    if target_text in document.page_content:
        print(f"Target found at rank {rank}")
        print(f"Distance: {distance:.4f}")
        print(document.page_content[:500])
        

    # Uncomment to inspect every result.
    # print(f"\n--- Rank {rank} | Distance: {distance:.4f} ---")
    # print(document.page_content[:150])

# Inspect the IDs returned by Chroma for the same question.
dense_chroma_results = collection.query(
    query_embeddings=[
        embedding_function.embed_query(question)
    ],
    n_results=20,
    where={"doc_id": "2"}
)

print(dense_chroma_results["ids"][0][:5])
# ============================================================
# 8. BM25 RETRIEVAL: PREPARE THE TEXT INDEX
# ============================================================

# BM25 uses keyword matching rather than embedding similarity.
tokenized_documents = [document.lower().split()for document in documents]
bm25 = BM25Okapi(tokenized_documents)


# ============================================================
# 9. TEST BM25 RETRIEVAL
# ============================================================

tokenized_query = question.lower().split()

# Calculate a relevance score for every stored document.
bm25_scores = bm25.get_scores(tokenized_query)

# Retrieve the IDs of the five highest-ranked documents.
top_bm25_ids = bm25.get_top_n(tokenized_query,document_ids, n=5)

# Create a lookup so we can find a document from its ID.
id_to_document = dict(zip(document_ids, documents))

print("\nNumber of BM25 results:", len(top_bm25_ids))

for rank, doc_id in enumerate(top_bm25_ids, start=1):
    document_text = id_to_document[doc_id]
    if target_text in document_text:
        print(f"Target found at BM25 rank {rank}")
        
    print(f"\n--- BM25 Rank {rank} ---")
    print("Document ID:", doc_id)

    # Display the text belonging to this ranked ID.
    print(id_to_document[doc_id][:500])


# ============================================================
# 10. RECIPROCAL RANK FUSION (RRF) — PRACTICE EXAMPLE
# ============================================================

# These are dummy IDs for learning how RRF combines rankings.
# They are NOT the real results from Chroma or BM25.

# dense_results_example = ["chunkA", "chunkB", "chunkC"]
# bm25_results_example = ["chunkC", "chunkA", "chunkD"]

# rrf_scores = {}
# rrf_constant = 60

# for rank, chunk_id in enumerate(dense_results_example, start=1):
#     contribution = 1 / (rrf_constant + rank)
#     rrf_scores[chunk_id] = (
#         rrf_scores.get(chunk_id, 0) + contribution
#     )

# for rank, chunk_id in enumerate(bm25_results_example, start=1):
#     contribution = 1 / (rrf_constant + rank)
#     rrf_scores[chunk_id] = (
#         rrf_scores.get(chunk_id, 0) + contribution
#     )

# ranked_chunks = sorted(
#     rrf_scores.items(),
#     key=lambda item: item[1],
#     reverse=True
# )

# print("\nRRF rankings:")
# for chunk_id, score in ranked_chunks:
#     print(chunk_id, score)


# ============================================================
# 11. PDF EXTRACTION AND SPLITTING — OPTIONAL EXPERIMENT
# ============================================================

def inspect_pdf_chunks(file_path: str):
    # Load the PDF pages.
    loader = PyPDFLoader(file_path)
    pages = loader.load()

    # Split the pages into chunks.
    chunks = splitter.split_documents(pages)

    print("PDF pages:", len(pages))
    print("Generated chunks:", len(chunks))

    # Inspect chunks containing the funding table.
    for chunk_number, chunk in enumerate(chunks, start=1):
        if target_text in chunk.page_content:
            print(f"\nMatching chunk: {chunk_number}")
            print(chunk.page_content)


# Run this function only when you want to inspect the PDF again.
# inspect_pdf_chunks("uploads/1/IFRC_2024_Annual_Report.pdf")
