from app.database import Base
from sqlalchemy import Column ,Integer , String , Text ,DateTime , ForeignKey , Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

class Organization(Base):
    __tablename__ ='organizations'
    
    id= Column(Integer, primary_key = True)
    name = Column(String(200), nullable=False)
    sector = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    
    users = relationship('User',backref='organization',lazy=True)
    documents = relationship('Document',backref='organization',lazy=True)
    conversations = relationship("Conversation", backref="organization", lazy=True)
    
    def __repr__(self):
        return f'<Organization {self.name}>'
    
    def to_dict(self):
        return {
            'id':         self.id,
            'name':       self.name,
            'sector':     self.sector,
            'created_at': self.created_at.isoformat(),
        }

class User(Base):
    __tablename__='users'
    
    id = Column(Integer , primary_key=True)
    email = Column(String(120), unique=True , nullable =False)
    password = Column(String(120),nullable=False)
    full_name = Column(String(100))
    role = Column(String(50), default='staff')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime,default=datetime.utcnow)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    
    # Relationship
    conversation = relationship("Conversation",backref='user',lazy=True)
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        return {
            'id':        self.id,
            'email':     self.email,
            'full_name': self.full_name,
            'role':      self.role,
            'is_active': self.is_active,
        }

class Document(Base):
    
    __tablename__='documents'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable= False)
    original_name = Column(String(255))
    file_type = Column(String(50)) # pdf, docx, txt
    file_size = Column(Integer) # in bytes
    source = Column(String(100)) # upload, google_drive, email, whatsapp
    status = Column(String(50), default='processing') # processing, ready, failed
    chunk_count = Column(Integer,default=0) # How many chunk for chromaDb
    uploaded_at = Column(DateTime , default=datetime.utcnow)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    
    def __repr__(self):
        return f'<Document{self.filename}>'
    
    def to_dict(self):
        return{
            'id': self.id,
            'filename':self.filename,
            'original_name':self.original_name,
            'file_type':self.file_type,
            'source':self.source,
            'status': self.status,
            'chunk_count':self.chunk_count,
            'uploaded_at':self.uploaded_at.isoformat()
        }

class Conversation(Base):
    __tablename__ ='conversations'
    
    id = Column(Integer,primary_key=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable =False)
    sources = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    def __repr__(self):
        return f"<Conversation {self.id}>"

    def to_dict(self):
        return {
            "id":         self.id,
            "question":   self.question,
            "answer":     self.answer,
            "sources":    self.sources,
            "created_at": self.created_at.isoformat(),
        }