import os
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from ..database import get_db
from ..models.user import User
from ..schemas.auth import UserCreate, UserResponse, UserLogin, GoogleLogin, Token, TokenData
from ..utils.security import verify_password, get_password_hash, create_access_token, SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    new_user = User(email=user.email, hashed_password=hashed_password, full_name=user.full_name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_credentials.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    if not user.hashed_password or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/google", response_model=Token)
def google_login(login_data: GoogleLogin, db: Session = Depends(get_db)):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured (missing GOOGLE_CLIENT_ID)")

    email = None
    full_name = None

    # First attempt: Verify as ID Token (OpenID Connect)
    try:
        # Verify the token
        # In a real production environment, you should also verify the 'aud' (audience) claim
        # matches your Google Client ID.
        idinfo = id_token.verify_oauth2_token(login_data.token, google_requests.Request(), GOOGLE_CLIENT_ID)

        email = idinfo.get('email')
        full_name = idinfo.get('name')

    except ValueError:
        # Second attempt: Treat as Access Token (OAuth2) and fetch user info
        try:
            response = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {login_data.token}"}
            )

            if response.status_code == 200:
                user_info = response.json()
                email = user_info.get("email")
                full_name = user_info.get("name")
            else:
                 raise ValueError("Invalid access token")

        except Exception as e:
             raise HTTPException(status_code=400, detail=f"Invalid Google token: {str(e)}")

    if not email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from Google token")

    user = db.query(User).filter(User.email == email).first()

    if not user:
        # Create new user
        # Generar una contraseña aleatoria para cumplir el NOT NULL y bloquear login por password
        random_pwd = secrets.token_urlsafe(16)
        new_user = User(
            email=email,
            hashed_password=get_password_hash(random_pwd),
            full_name=full_name,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        user = new_user

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(current_user)
    db.commit()
    return
