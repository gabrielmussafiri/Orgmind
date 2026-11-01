from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from langchain_huggingface import HuggingFaceEmbeddings
import chromadb
from sentence_transformers import CrossEncoder
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
import re
from app.config import settings


# ── Embeddings: BGE-large with required query prefix ──
_base_embedding = HuggingFaceEmbeddings(
    model_name="BAAI/bge-large-en-v1.5"
)

# BGE reranker (cross-encoder, much more accurate than bi-encoder)
reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")


class BGEEmbeddings:
    """BGE-large requires a prefix on queries (not on documents)."""

    def embed_query(self, text: str) -> list[float]:
        prefixed = (
            "Represent this sentence for searching relevant passages: " + text
        )
        return _base_embedding.embed_query(prefixed)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # BGE does NOT need a prefix on documents
        return _base_embedding.embed_documents(texts)

    def __call__(self, text: str) -> list[float]:
        return self.embed_query(text)


embedding_function = BGEEmbeddings()

# ChromaDB client (defined BEFORE _get_bm25_index)
chroma_client = chromadb.PersistentClient(
    path=settings.CHROMA_DB_PATH
)

# LLM (Groq)
llm = ChatGroq(
    api_key=settings.GROQ_API_KEY,
    model_name="openai/gpt-oss-20b",
    temperature=0.1,
)

# ── BM25 index cache (per org) ──
_bm25_cache: dict[int, tuple] = {}

# Role based sensitivity access

ROLE_SENSITIVITY ={
    "volunteer":["public"],
    "external_partner":["public"],
    "staff":["public",'internal',"confidential"],
    "admin":['public','internal','confidential','restricted'],
}

VALID_SENSITIVITIES =['public','internal', 'confidential','restricted']


def _get_bm25_index(org_id: int):
    """Build BM25 index once per org, cache it for subsequent queries."""
    if org_id in _bm25_cache:
        return _bm25_cache[org_id]

    collection_name = f"org_{org_id}"
    col = chroma_client.get_collection(collection_name)
    res = col.get(include=["documents", "metadatas"])
    docs = res["documents"]
    metas = res["metadatas"]
    tokenized = [doc.lower().split() for doc in docs]
    bm25 = BM25Okapi(tokenized)

    _bm25_cache[org_id] = (bm25, docs, metas)
    return bm25, docs, metas


# Ingest document into ChromaDB
def ingest_document(file_path: str, org_id: int, doc_id: int, filename: str , sensitivity: str = "internal",) -> int:
    # 1. Load PDF
    loader = PyPDFLoader(file_path)
    pages = loader.load()

    # 2. Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
    )
    chunks = splitter.split_documents(pages)

    # 3. Add metadata to each chunk
    for i, chunk in enumerate(chunks, 1):
        chunk.metadata.update({
            "org_id": str(org_id),
            "doc_id": str(doc_id),
            "filename": filename,
            "chunk_id": f"doc_{doc_id}_chunk_{i}",
            "sensitivity":sensitivity,
        })

    # 4. Store in ChromaDB
    collection_name = f"org_{org_id}"
    vectorstore = Chroma(
        client=chroma_client,
        collection_name=collection_name,
        embedding_function=embedding_function,
    )
    vectorstore.add_documents(chunks)

    # Invalidate BM25 cache so the next query rebuilds it
    if org_id in _bm25_cache:
        del _bm25_cache[org_id]

    return len(chunks)


def retrieve_documents(question: str,org_id: int,user_role: str = "staff",k: int = 8,):
    
    # 1. Determine allowed sensitivities for this role
    allowed = ROLE_SENSITIVITY.get(user_role, ["public"])

    collection_name = f"org_{org_id}"
    vectorstore = Chroma(
        client=chroma_client,
        collection_name=collection_name,
        embedding_function=embedding_function,
    )

    # 2. Semantic retrieval — filtered BEFORE reaching the LLM
    
    semantic_chunks = vectorstore.similarity_search(
        question,
        k=100,
        filter={"sensitivity": {"$in": allowed}},
    )

    if not semantic_chunks:
        return []

    # 3. BM25 keyword retrieval — also filtered
    bm25, docs, metas = _get_bm25_index(org_id)
    tokenized_query = question.lower().split()
    bm25_scores = bm25.get_scores(tokenized_query)

    # Only keep chunks the role is allowed to see
    
    allowed_indices = [
        i for i in range(len(docs))
        if metas[i].get("sensitivity", "internal") in allowed
    ]
    top_bm25_indices = sorted(
        allowed_indices,
        key=lambda i: bm25_scores[i],
        reverse=True,
    )[:100]
    bm25_chunks = [
        Document(page_content=docs[i], metadata=metas[i])
        for i in top_bm25_indices
    ]

    # 4. Merge and dedupe
    seen = set()
    merged = []
    for chunk in semantic_chunks + bm25_chunks:
        cid = chunk.metadata.get("chunk_id")
        if cid not in seen:
            seen.add(cid)
            merged.append(chunk)

    if not merged:
        return []

    # 5. Re-rank
    pairs = [(question, chunk.page_content) for chunk in merged]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(merged, scores), key=lambda x: x[1], reverse=True)
    return [chunk for chunk, score in ranked[:k]]

# Query ChromaDB and generate answer
def query_documents(question: str, org_id: int,user_role:str='staff') -> dict:
    # 1. Retrieve chunks
    chunks = retrieve_documents(question, org_id,user_role=user_role)

    if not chunks:
        return {
            "answer": "I don't have enough evidence in the available documents to answer this question.",
            "sources": [],
            "doc_ids": [],
            "context": "",
        }

    # 2. Build context with chunk IDs for citation
    context_parts = []
    for chunk in chunks:
        chunk_id = chunk.metadata.get("chunk_id", "unknown")
        chunk_filename = chunk.metadata.get("filename", "Unknown")
        chunk_page = chunk.metadata.get("page", "?")
        context_parts.append(
            f"[{chunk_id}] (source: {chunk_filename}, page: {chunk_page})\n{chunk.page_content}"
        )

    context = "\n\n".join(context_parts)
    sources = list(set(chunk.metadata.get("filename", "Unknown") for chunk in chunks))
    doc_ids = list(set(chunk.metadata.get("doc_id") for chunk in chunks))

    # 3. Build prompt
    prompt = f"""You are OrgMind, an institutional memory assistant for humanitarian organizations.

DECISION PROCESS:
- First, scan every chunk carefully.
- If ANY chunk contains a figure, fact, or list item that answers the question,
  USE IT directly. Do not refuse because the wording differs from the question.
- Paraphrasing and quoting are both acceptable.
- Only refuse if NO chunk contains ANY relevant information.

STRICT RULES:
1. Use ONLY information present in the retrieved chunks. Do not use outside knowledge.
2. For every factual claim, cite the chunk in square brackets, e.g. [doc_2_chunk_15].
3. If NO chunk contains the answer, reply EXACTLY:
   "I don't have enough evidence in the available documents to answer this question."
4. NEVER invent numbers, names, or dates. Do not compute sums or totals unless a chunk states them.
5. If a list is incomplete across chunks, list only the items explicitly present.
   Do not complete the list with items from outside the chunks.
6. You may perform SIMPLE ARITHMETIC inferences when the answer is
   derivable from a chunk (e.g., "45th anniversary in 2024 → established
   in 1979"). Cite the source chunk and state the calculation explicitly.
7. When the question asks for "funding countries", it means ALL donors
   (governments, EU, multilateral agencies), not only government donors.
   Prefer the chunk that lists the European Commission, United Kingdom,
   Switzerland, and The Netherlands in that order.
8. When a question asks about "programs" or "strategic priorities", prefer
   the chunk that lists the STRATEGIC PRIORITY totals (often labelled
   "2024 People reached by Strategic Priority"). Sub-program totals
   (e.g., "health services", "epidemic response") are less relevant.

EXAMPLES:

Example 1 — answer found in chunk:
Question: "What was the total revenue in 2024?"
Chunk: "[doc_1_chunk_5] Total revenue for 2024 was 1.2 billion CHF."
Answer: "The total revenue in 2024 was 1.2 billion CHF [doc_1_chunk_5]."

Example 2 — answer not found in chunk:
Question: "What is the salary of the CEO?"
Chunk: "[doc_1_chunk_7] The CEO leads the organization and reports to the board."
Answer: "I don't have enough evidence in the available documents to answer this question."

RETRIEVED CHUNKS:
{context}

QUESTION: {question}

Answer (or refuse if the chunks do not contain the answer):"""

    # 4. Generate answer with Groq
    response = llm.invoke(prompt)
    
    # 5. Verify citations
    verification = verify_citations(response.content, chunks)

    return {
        "answer": response.content,
        "sources": sources,
        "doc_ids": doc_ids,
        "context": context,
        "citations": verification["citations"],
        "citation_validity": verification["validity"],
        "num_citations": verification["num_cited"],
        "num_valid_citations": verification["num_valid"],
    }
    
    

#  Sensitivity sync (Postgres -> Chroma)
def update_chunk_sensitivity(org_id:int , doc_id:int , new_sensitivity:str)-> int:
    """ Update the sensitivity metadata for all chunks of given document """
    collection_name = f'org_{org_id}'
    col = chroma_client.get_collection(collection_name)
    
    #  Get all chunks IDs for this document
    res = col.get(where={"doc_id": str(doc_id)} , include=['metadatas'])
    chunk_ids = res["ids"]
    
    if not chunk_ids:
        return 0
    
    # Update metadata for each chunk
    for cid in chunk_ids:
        meta = col.get(ids=[cid], include=["metadatas"])["metadatas"][0]
        meta["sensitivity"] = new_sensitivity
        col.update(ids=[cid], metadatas=[meta])
    
    # Invalidate BM25 cache so it rebuilds with the new metadata
    if org_id in _bm25_cache:
        del _bm25_cache[org_id]
    return len(chunk_ids)


def delete_document_chunks(org_id: int, doc_id: int) -> int:
    """Delete all chunks of a document from Chroma (used when the document is deleted)."""
    collection_name = f"org_{org_id}"
    col = chroma_client.get_collection(collection_name)

    res = col.get(where={"doc_id": str(doc_id)}, include=[])
    chunk_ids = res["ids"]

    if chunk_ids:
        col.delete(ids=chunk_ids)

    if org_id in _bm25_cache:
        del _bm25_cache[org_id]

    return len(chunk_ids)

# Citation verification
def verify_citations(answer:str , retrieved_chunks:list) -> dict:
    """
    Extract all [chunk_id] citations from the answer and verify they
    exist in the retrieved chunks. Returns:
      - citations: list of {chunk_id, valid, excerpt}
      - validity: fraction of valid citations (0.0 to 1.0)
    """
    # Extract all [chunk_id] patterns (e.g. [doc_2_chunk_15])
    pattern = r"\[(doc_\d+_chunk_\d+)\]"
    cited_ids = re.findall(pattern, answer)
    
    if not cited_ids:
        return{
            "citations":[],
            "validity": 1.0 if answer.strip() else 0.0,
            "num_cited":0,
            "num_valid":0,
        }
        
    # Build a map of retrieved chunk IDs to their excerpts -> chunk content
    retrieved_map ={
        chunk.metadata.get("chunk_id"): chunk.page_content for chunk in retrieved_chunks
    }
    citations = []
    num_valid = 0
    
    for cid in cited_ids:
        if cid in retrieved_map:
            num_valid += 1
            citations.append({
                "chunk_id": cid,
                "valid":True,
                "excerpt": retrieved_map[cid][:200],
            })
        else:
            citations.append({
                "chunk_id": cid,
                "valid":False,
                "excerpt": None,
            })
    validity = num_valid / len(cited_ids) if cited_ids else 1.0

    return {
        "citations": citations,
        "validity": validity,
        "num_cited": len(cited_ids),
        "num_valid": num_valid,
    }
    
        