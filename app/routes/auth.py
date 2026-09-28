from fastapi import APIRouter , Depends , HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import Organization , User
from app.services.auth_service import(
    hash_password,
    verify_password,
    create_token,
    get_current_user
)

router = APIRouter(prefix='/auth',tags=['Authentication'])

# Schemas Pydantic

class RegisterOrgRequest(BaseModel):
    org_name : str
    sector : str ='NGO'
    email : str
    password : str
    full_name : str
    
class LoginRequest(BaseModel):
    email : str
    password : str
    
# Routes

@router.post("/register-org", status_code=201)
def register_org(request:RegisterOrgRequest , db: Session = Depends(get_db)):
    
    # 1. Check email not already used
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=409 , detail='Email already registered')
    
    # 2. Create Organization
    org = Organization(
        name = request.org_name,
        sector = request.sector
    )
    db.add(org)
    db.flush() # get org.id without committing yet
    
    # 3. Create first admin user
    user = User(
        email = request.email,
        password = hash_password(request.password),
        full_name = request.full_name ,
        role ='admin',
        organization_id = org.id
        
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create JWt token
    token = create_token(user_id=user.id , org_id=org.id)
    return {
        "message":"organization created successfully",
        "token":token,
        "user": user.to_dict(),
        "org": org.to_dict()
    }
    
@router.post('/login')
def login(request:LoginRequest , db:Session = Depends(get_db)):
    
    # 1. Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    
    # 2. Check user exists and password matches
    if not user or not verify_password(request.password , user.password):
        raise HTTPException(status_code=401 , detail='Invalid email or password')
    
    # 3. check user is active
    if not user.is_active:
        raise HTTPException(status_code=401 , detail='Account is inactive')
    
    # 4. Create token
    token = create_token(user_id = user.id , org_id=user.organization_id)
    
    return{
        "token":token,
        "user": user.to_dict()
    }

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user.to_dict()