from fastapi import APIRouter , Depends , HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import User , Conversation
from app.services.auth_service import get_current_user
from app.services.rag_service import  query_documents


router = APIRouter(prefix ="/query", tags=['Query'])

# Schema
class QueryRequest(BaseModel):
    question : str

# Query Route
@router.post("/")
def ask_question(
    request:QueryRequest,
    db : Session = Depends(get_db),
    current_user : User = Depends(get_current_user)
):
    #  1.  Get Answer from RAG
    result = query_documents(
        question = request.question,
        org_id = current_user.organization_id
    )
    
    # 2. Save Conversation to database
    import json
    conversation = Conversation(
        question = request.question,
        answer = result['answer'],
        sources = json.dumps(result['sources']),
        user_id = current_user.id,
        organization_id = current_user.organization_id
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    # 3. Return Answer with Sources
    return{
        "question": request.question,
        "answer": result['answer'],
        "sources": result['sources'],
        "saved_at": conversation.created_at.isoformat()
    }

# ── Get conversation history ──────────────────────────
@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conversations = db.query(Conversation).filter(
        Conversation.organization_id == current_user.organization_id
    ).order_by(Conversation.created_at.desc()).all()

    return [conv.to_dict() for conv in conversations]