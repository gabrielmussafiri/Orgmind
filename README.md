# OrgMind 🧠

AI-powered institutional memory system for humanitarian
and international organizations.

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

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy
- **AI/RAG:** LangChain, ChromaDB, Groq (Llama)
- **Database:** PostgreSQL (Supabase)
- **Auth:** JWT tokens, bcrypt
- **Embeddings:** SentenceTransformers (local, free)

## Features

- Multi-tenant (each organization's data is isolated)
- Upload PDF documents
- Ask questions in plain language
- AI answers with source citations
- Conversation history per organization

## API Endpoints

### Auth

- POST /auth/register-org
- POST /auth/login
- GET /auth/me

### Documents

- POST /documents/uploads
- GET /documents/
- DELETE /documents/{id}

### Query

- POST /query/
- GET /query/history

## Tested With

Real IFRC 2025 Annual Report — system correctly
answered questions about specific figures including
2.1 million people supported in migration programmes.

## Run Locally

1. Clone repo
2. Create virtual environment: python -m venv venv
3. Activate: source venv/bin/activate
4. Install: pip install -r requirements.txt
5. Create .env with DATABASE_URL and GROQ_API_KEY
6. Run: python run.py
7. Visit: http://localhost:8000/docs
