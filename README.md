# OrgMind 🧠

AI-powered institutional memory system for humanitarian
and international organizations.

![Status](https://img.shields.io/badge/status-week%201%20complete-blue)
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

**Week 1 complete: baseline evaluation.**

| Metric                  | Baseline | Target |
| ----------------------- | -------- | ------ |
| Retrieval hit rate @5   | **100%** | ≥ 90%  |
| Retrieval precision @5  | **100%** | ≥ 80%  |
| Faithfulness (AI judge) | **98%**  | ≥ 90%  |
| Answer correctness      | **50%**  | ≥ 80%  |
| Refusal accuracy        | **60%**  | ≥ 90%  |

**Diagnosis:** retrieval is solid. Generation is the bottleneck.
Two hallucinations detected on unanswerable questions (salary,
board members). Week 2 focuses on prompt engineering and
access control.

See [docs/metrics.md](docs/metrics.md) for definitions and
[eval/results/](eval/results/) for raw runs.

## Architecture

    User → FastAPI → Auth (JWT) → Retrieval (Chroma) → Generation (Groq) → Citations → UI

- **Multi-tenant**: each organization has its own Chroma collection
- **Access control**: enforced at retrieval time (Week 2)
- **Citations**: every claim must reference a chunk ID (Week 2)
- **Traces**: every query logged for debugging (Week 2)

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
- SentenceTransformers `all-MiniLM-L6-v2` for embeddings (local, free)

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
and the Global Climate Resilience Platform's 1B CHF target.

## Roadmap

- [x] **Week 1** — Baseline eval (20 cases), ADR, metrics
- [ ] **Week 2** — Prompt engineering, access control, citations, traces
- [ ] **Week 3** — uv migration, CI pipeline, portfolio README
- [ ] **Week 4** — PII redaction, sensitivity routing, model gateway
- [ ] **Week 5** — Streamlit UI, user feedback
- [ ] **Week 6** — Chroma vs Qdrant comparison, hybrid retrieval
- [ ] **Week 7** — Docker, deployment
- [ ] **Week 8** — Multilingual eval
- [ ] **Week 9** — Portfolio packaging

## What I Learned

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
