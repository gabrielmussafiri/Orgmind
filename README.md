# OrgMind 🧠

AI-powered institutional memory system for humanitarian
and international organizations.

![Status](https://img.shields.io/badge/status-week%202%20complete-blue)
![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## The Problem

When staff leave humanitarian organizations, critical
knowledge leaves with them. Field reports, WhatsApp
messages, security briefs, and lessons learned disappear
into personal folders or are simply forgotten.

## The Solution

OrgMind ingests organizational documents and lets staff
ask questions in plain language, getting instant answers
with source citations — preserving institutional memory
regardless of staff turnover.

**Read-only by design.** No write actions. Every answer is
grounded in retrieved source documents. When the answer
isn't in the corpus, the system says so.

## Current Status

**Week 2 complete: RAG pipeline v2.**

| Metric                  | W1 baseline | **W2 current** | Target |
| ----------------------- | ----------- | -------------- | ------ |
| Retrieval hit rate @5   | 100%        | **100%**       | ≥ 90%  |
| Retrieval precision @5  | 100%        | **100%**       | ≥ 80%  |
| Faithfulness (AI judge) | 98%\*       | **97.5%**      | ≥ 90%  |
| Answer correctness      | 50%         | **90%**        | ≥ 80%  |
| Refusal accuracy        | 60%         | **100%**       | ≥ 90%  |

_\*W1 faithfulness was inflated by frequent refusals — the LLM refused instead of hallucinating._

**What moved the needle (in order):**

1. Prompt engineering (3 iterations): 50% → 50%. No effect.
2. Chunking 500→1000 chars: refusal 80% → 100%. No effect on correctness.
3. Embedding swap MiniLM → BGE-large (with query prefix): 50% → 60%.
4. Hybrid search (BGE + BM25) + cross-encoder reranker + k=8: **60% → 90%**.

**One case remains:** the health-and-wellbeing question returns a sub-program
figure (84.7M) instead of the strategic-priority total (89.8M). Week 3 will
address this with semantic chunking.

Week 3 focuses on access control (sensitivity tags + per-role filtering),
citation verification, and query traces.

See [docs/metrics.md](docs/metrics.md) for definitions and
[eval/results/](eval/results/) for raw runs.

## Architecture

    User → FastAPI → Auth (JWT) → Retrieval (Chroma) → Generation (Groq) → Citations → UI

- **Multi-tenant**: each organization has its own Chroma collection
- **Hybrid retrieval**: BGE-large (semantic) + BM25 (keyword) + cross-encoder reranker
- **Access control**: enforced at retrieval time (Week 3)
- **Citations**: every claim must reference a chunk ID (Week 3)
- **Traces**: every query logged for debugging (Week 3)

See [ARCHITECTURE.md](ARCHITECTURE.md) and [DECISIONS/](DECISIONS/)
for design rationale.

## Tech Stack

**Backend**

- Python 3.13, FastAPI, SQLAlchemy
- PostgreSQL (Supabase) for metadata, conversations, traces
- JWT auth with bcrypt

**RAG**

- LangChain for orchestration
- ChromaDB for vector storage (one collection per org)
- Groq (`openai/gpt-oss-20b`) for generation
- `BAAI/bge-large-en-v1.5` for embeddings (1024d, with query prefix)
- `BAAI/bge-reranker-v2-m3` for cross-encoder re-ranking
- `rank-bm25` for keyword retrieval (hybrid search)

**Evaluation**

- Claude Haiku 4.5 (Anthropic) as AI judge
- Custom metrics: hit rate, precision, faithfulness, correctness, refusal
- JSON baseline snapshots in `eval/results/`

## Features

- Multi-tenant (each organization's data is isolated)
- Upload PDF documents
- Ask questions in plain language
- AI answers with source citations
- Conversation history per organization
- Reproducible evaluation pipeline with saved baselines

## API Endpoints

### Auth

- `POST /auth/register-org`
- `POST /auth/login`
- `GET /auth/me`

### Documents

- `POST /documents/uploads`
- `GET /documents/`
- `DELETE /documents/{id}`

### Query

- `POST /query/`
- `GET /query/history`

## Evaluation

The eval set lives in [`eval/eval_set.json`](eval/eval_set.json):
20 cases across 3 categories.

| Type             | Count | What it tests                         |
| ---------------- | ----- | ------------------------------------- |
| `answerable`     | 10    | Correct answers with citations        |
| `unanswerable`   | 5     | Correct refusals (no hallucination)   |
| `access_control` | 5     | Permissions enforced before retrieval |

Run the evaluation:

    uv run python -m app.evaluation

Results are saved to `eval/results/{timestamp}.json` with
both summary metrics and per-case details.

## Run Locally

1. Clone the repo
2. Install dependencies:

   uv sync

3. Create `.env`:

   GROQ_API_KEY=...
   ANTHROPIC_API_KEY=...
   DATABASE_URL=...
   JWT_SECRET=...
   CHROMA_DB_PATH=./chroma_db

4. Start the server:

   uv run python run.py

5. Visit [http://localhost:8000/docs](http://localhost:8000/docs)

## Tested With

Real IFRC 2024 Annual Report (2,414 chunks). System correctly
answered questions about specific figures including
DREF's 76.5% direct allocation, the 45-year anniversary,
the Global Climate Resilience Platform's 1B CHF target,
and the top 5 funding countries (US 151.0M, EU 106.3M,
UK 57.2M, Switzerland 49.9M, Netherlands 35.2M).

## Roadmap

- [x] **Week 1** — Baseline eval (20 cases), ADR, metrics
- [x] **Week 2** — Prompt v3, BGE-large, hybrid search, reranker. Correctness 50%→90%
- [ ] **Week 3** — Access control, citation verification, traces
- [ ] **Week 4** — PII redaction, model gateway, sensitivity routing
- [ ] **Week 5** — Streamlit UI, user feedback
- [ ] **Week 6** — Chroma vs Qdrant comparison, semantic chunking
- [ ] **Week 7** — Docker, deployment
- [ ] **Week 8** — Multilingual eval
- [ ] **Week 9** — Portfolio packaging

## What I Learned

- **The retrieval stack matters more than the prompt.** Three prompt
  iterations moved correctness by 0 points. One embedding swap + hybrid
  search + reranker moved it by 30 points. A prompt can't fix what the
  model never sees.
- **Bi-encoders and cross-encoders do different jobs.** BGE-large
  (bi-encoder) finds candidates fast. BGE-reranker (cross-encoder) scores
  them accurately. You need both.
- **Evaluation-driven development works.** Writing the eval set
  before touching the prompt forced me to separate retrieval
  failures from generation failures. The baseline (50% correctness)
  was not obvious from ad-hoc testing.
- **AI judges need parsing guardrails.** Claude wraps JSON in
  Markdown fences by default; a small `parse_json_response`
  helper is required.
- **Multi-document isolation matters.** Two IFRC reports in the
  same Chroma collection polluted retrieval. Deleting the
  unused one moved precision from 46% to 100%.
- **Faithfulness ≠ correctness.** A correct refusal is
  100% faithful but 0% correct. Both metrics are needed.

## License

MIT
