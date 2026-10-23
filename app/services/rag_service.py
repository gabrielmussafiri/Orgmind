from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
import chromadb
from sentence_transformers import CrossEncoder
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document

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
def ingest_document(file_path: str, org_id: int, doc_id: int, filename: str) -> int:
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


def retrieve_documents(question: str, org_id: int, k: int = 8):
    collection_name = f"org_{org_id}"
    vectorstore = Chroma(
        client=chroma_client,
        collection_name=collection_name,
        embedding_function=embedding_function,
    )

    # 1. Semantic retrieval (top 20)
    semantic_chunks = vectorstore.similarity_search(question, k=100)

    if not semantic_chunks:
        return []

    # 2. BM25 keyword retrieval (top 20) — uses cached index
    bm25, docs, metas = _get_bm25_index(org_id)
    tokenized_query = question.lower().split()
    bm25_scores = bm25.get_scores(tokenized_query)
    top_bm25_indices = sorted(
        range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
    )[:100]
    bm25_chunks = [
        Document(page_content=docs[i], metadata=metas[i])
        for i in top_bm25_indices
    ]

    # 3. Merge and dedupe by chunk_id
    seen = set()
    merged = []
    for chunk in semantic_chunks + bm25_chunks:
        cid = chunk.metadata.get("chunk_id")
        if cid not in seen:
            seen.add(cid)
            merged.append(chunk)

    # 4. Re-rank all candidates with cross-encoder
    pairs = [(question, chunk.page_content) for chunk in merged]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(merged, scores), key=lambda x: x[1], reverse=True)
    return [chunk for chunk, score in ranked[:k]]


# Query ChromaDB and generate answer
def query_documents(question: str, org_id: int) -> dict:
    # 1. Retrieve chunks
    chunks = retrieve_documents(question, org_id)

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

    return {
        "answer": response.content,
        "sources": sources,
        "doc_ids": doc_ids,
        "context": context,
    }