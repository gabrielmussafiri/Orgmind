import os
import shutil
from fastapi import APIRouter , Depends , HTTPException , UploadFile , File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document , User
from app.services.auth_service import get_current_user
from app.services.rag_service import ingest_document

router = APIRouter(prefix="/documents",tags=['Documents'])

UPLOAD_DIR = "uploads"

# Upload document
@router.post("/uploads",status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Validate file type
    allowed =['application/pdf', "text/plain"]
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail='Only PDF and text files allowed'
        )
    
    # 2. Save file to disk
    org_folder = os.path.join(UPLOAD_DIR , str(current_user.organization_id))
    os.makedirs(org_folder, exist_ok=True)
    
    file_path = os.path.join(org_folder , file.filename)
    with open(file_path,'wb') as buffer:
        shutil.copyfileobj(file.file , buffer)
    
    # 3. Save document metadata to PostgreSQL
    doc = Document(
        filename = file.filename,
        original_name = file.filename,
        file_type = file.content_type,
        source ="upload",
        status='processing',
        organization_id = current_user.organization_id
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # 4. Ingest into ChromaDB ( RAG)
    try:
        chunk_count = ingest_document(
            file_path=file_path,
            org_id= current_user.organization_id,
            doc_id=doc.id,
            filename=file.filename
        )
        # 5. Update status to ready
        doc.status = 'ready'
        doc.chunk_count = chunk_count
        db.commit()
        
    except Exception as e :
        doc.status = 'failed'
        db.commit()
        raise HTTPException(status_code=500 , detail=f'Ingestion failed:{str(e)}')
    
    return doc.to_dict()

#  Get all documents
@router.get("/")
def get_documents(
    db: Session = Depends(get_db),
    current_user : User = Depends(get_current_user)
):
    docs = db.query(Document).filter(
        Document.organization_id == current_user.organization_id
    ).all()
    
    return[doc.to_dict() for doc in docs]

# Delete document
@router.delete("/{doc_id}")
def delete_document(
    doc_id : int,
    db:Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    docs = db.query(Document).filter(
        Document.id == doc_id,
        Document.organization_id == current_user.organization_id
    ).first()
    
    if not docs:
        raise HTTPException(status_code=404 , detail='Document not found')
    
    db.delete(docs)
    db.commit()
    
    return {"message": "Document deleted successfully"}