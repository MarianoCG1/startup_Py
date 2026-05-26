import os
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from app.database import Database, verify_password

SECRET_KEY = os.getenv("SECRET_KEY", "demandarest-secret-key-2026-default")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

async def get_current_user(request: Request) -> Optional[dict]:
    """Obtiene el usuario actual leyendo la cookie del token de sesión."""
    token = request.cookies.get("session_token")
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload:
        return None
        
    email = payload.get("email")
    if not email:
        return None
        
    # Obtener perfil del usuario (desde SQLite o Supabase)
    user = Database.get_user_by_email(email)
    if not user:
        return None
        
    return {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "location_id": user.get("location_id"),
        "location_name": user.get("location_name")
    }

async def require_user(request: Request, user: Optional[dict] = Depends(get_current_user)):
    """Verifica que el usuario haya iniciado sesión. Redirige a /login si no."""
    if not user:
        # Si es una petición HTMX, enviar cabecera HX-Redirect para redirigir en el cliente
        if request.headers.get("hx-request"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"HX-Redirect": "/login"}
            )
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return user

class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    def __call__(self, request: Request, user: dict = Depends(require_user)):
        if user["role"] not in self.allowed_roles:
            if request.headers.get("hx-request"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    headers={"HX-Redirect": "/login?error=Unauthorized"}
                )
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/login?error=Unauthorized"}
            )
        return user
