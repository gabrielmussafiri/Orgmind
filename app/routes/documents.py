import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import Document, User
from app.services.auth_service import get_current_user
from app.services.rag_service import (
    ingest_document,
    VALID_SENSITIVITIES,
    ROLE_SENSITIVITY,
    update_chunk_sensitivity,
    delete_document_chunks,
)

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = "uploads"


class SensitivityUpdate(BaseModel):
    sensitivity: str


@router.patch("/{doc_id}/sensitivity")
def update_sensitivity(
    doc_id: int,
    body: SensitivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can change sensitivity")

    if body.sensitivity not in VALID_SENSITIVITIES:
        raise HTTPException(
            status_code=400,
            detail=f"sensitivity must be one of {VALID_SENSITIVITIES}",
        )

    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.organization_id == current_user.organization_id,
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    old = doc.sensitivity
    doc.sensitivity = body.sensitivity
    db.commit()

    updated = update_chunk_sensitivity(
        org_id=current_user.organization_id,
        doc_id=doc_id,
        new_sensitivity=body.sensitivity,
    )

    return {
        "id": doc.id,
        "old_sensitivity": old,
        "new_sensitivity": doc.sensitivity,
        "chunks_updated": updated,
    }


# Upload document
@router.post("/uploads", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    sensitivity: str = Form("internal"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Validate file type
    allowed_types = ["application/pdf", "text/plain"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and text files allowed",
        )

    # 2. Validate sensitivity
    if sensitivity not in VALID_SENSITIVITIES:
        raise HTTPException(
            status_code=400,
            detail=f"sensitivity must be one of {VALID_SENSITIVITIES}",
        )

    # Only admin can upload restricted docs
    if sensitivity == "restricted" and current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admin can upload restricted documents",
        )

    # 3. Save file to disk
    org_folder = os.path.join(UPLOAD_DIR, str(current_user.organization_id))
    os.makedirs(org_folder, exist_ok=True)
    file_path = os.path.join(org_folder, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 4. Save document metadata to PostgreSQL with sensitivity
    doc = Document(
        filename=file.filename,
        original_name=file.filename,
        file_type=file.content_type,
        source="upload",
        status="processing",
        sensitivity=sensitivity,
        organization_id=current_user.organization_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 5. Ingest into ChromaDB (RAG)
    try:
        chunk_count = ingest_document(
            file_path=file_path,
            org_id=current_user.organization_id,
            doc_id=doc.id,
            filename=file.filename,
            sensitivity=sensitivity,
        )
        doc.status = "ready"
        doc.chunk_count = chunk_count
        db.commit()
    except Exception as e:
        doc.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    return doc.to_dict()


# Get all documents
@router.get("/")
def get_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = ROLE_SENSITIVITY.get(current_user.role, ["public"])

    docs = db.query(Document).filter(
        Document.organization_id == current_user.organization_id,
        Document.sensitivity.in_(allowed),
    ).all()

    return [doc.to_dict() for doc in docs]


# Delete document
@router.delete("/{doc_id}")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.organization_id == current_user.organization_id,
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    db.delete(doc)
    db.commit()

    # Delete chunks from Chroma
    deleted_chunks = delete_document_chunks(
        org_id=current_user.organization_id,
        doc_id=doc_id,
    )

    return {
        "message": "Document deleted successfully",
        "chunks_deleted": deleted_chunks,
    }