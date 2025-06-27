from fastapi import Depends, HTTPException, status
import jwt
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.modules.auth.models import User
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings
from uuid import UUID

oauth2_scheme = HTTPBearer()

SECRET_KEY = settings.APP_SECRET_STRING
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def get_current_user_and_company(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        company_id = payload.get("company_id")
        role = payload.get("role")

        if not user_id or not company_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin contexto de empresa")

        user = db.query(User).get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return {
            "user": user,
            "company_id": UUID(company_id),
            "role": role
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")