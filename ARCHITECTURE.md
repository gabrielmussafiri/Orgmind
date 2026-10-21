
## Components

### Application layer
- **FastAPI** exposes REST endpoints (`/auth`, `/documents`, `/query`)
- **JWT auth** identifies users and their organization
- **SQLAlchemy** models: `Organization`, `User`, `Document`, `Conversation`

### RAG layer
- **ChromaDB**: one collection per organization (`org_{org_id}`)
- **SentenceTransformers** (`all-MiniLM-L6-v2`): local embeddings, no API cost
- **Groq** (`openai/gpt-oss-20b`): answer generation
- **LangChain**: orchestration and chunking

### Evaluation layer
- **Claude Haiku 4.5** (Anthropic): AI judge for faithfulness and correctness
- **eval/eval_set.json**: 20 cases across 3 categories
- **eval/results/**: timestamped JSON snapshots for baseline tracking

## Security model

- **Access control** enforced at retrieval time (Week 2)
- **Multi-tenant**: each org's Chroma collection is isolated
- **No write actions**: read-only by design
- **Audit logs**: every query traced (Week 2)

## Evolution

- **Week 1**: baseline eval (hit=100%, precision=100%, faith=98%, correct=50%, refusal=60%)
- **Week 2**: prompt engineering, access control, citations, traces
- **Week 3+**: uv migration, CI, deployment, multi-document support

See [DECISIONS/0001-rag-first.md](DECISIONS/0001-rag-first.md) for why RAG before finetuning.
