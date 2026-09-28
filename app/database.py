from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings


# Create engine
engine = create_engine(settings.DATABASE_URL)

# Create session

SessionLocal = sessionmaker(
    autocommit =False,
    autoflush=False,
    bind= engine
)

# Base class for all models
Base = declarative_base()

# Dependency with proper error handling

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


