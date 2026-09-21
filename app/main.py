from fastapi import FastAPI
from app.database import engine , Base
from app.config import settings

from app.models import Organization , User , Document , Conversation

# Create all table in DB
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version= settings.VERSION,
    description= ' AI Institutional Memory System for Humanitarian Organization'
)

@app.get('/')
def root():
    return{
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        'status':'running'
    }

@app.get('/health')
def health():
    return{'status':'healthy'}