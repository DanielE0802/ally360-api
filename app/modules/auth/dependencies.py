"""
Dependencias de autenticación para FastAPI.
"""
from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, selectinload
import jwt

from app.dependencies.dbDependecies import get_db
from app.modules.auth.models import User, UserCompany
from app.modules.auth.schemas import AuthContext
from app.core.config import settings

# Security scheme
security = HTTPBearer()

class AuthDependencies:
    """Dependencias de autenticación reutilizables."""

    @staticmethod
    def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
    ) -> User:
        """
        Obtener usuario actual desde token JWT.
        No requiere tenant_id (para endpoints generales).
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudieron validar las credenciales",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jwt.decode(
                credentials.credentials, 
                settings.APP_SECRET_STRING, 
                algorithms=[settings.ALGORITHM]
            )
            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception
        except jwt.PyJWTError:
            raise credentials_exception

        user = db.query(User).options(
            selectinload(User.profile),
            selectinload(User.user_companies).selectinload(UserCompany.company)
        ).filter(User.id == user_id).first()
        
        if user is None or not user.is_active:
            raise credentials_exception

        return user

    @staticmethod
    def get_auth_context(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
    ) -> AuthContext:
        """
        Obtener contexto de autenticación completo con tenant.
        Requiere X-Company-ID header o token de contexto.
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudieron validar las credenciales",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.APP_SECRET_STRING,
                algorithms=[settings.ALGORITHM]
            )
            
            user_id: str = payload.get("sub")
            token_type: str = payload.get("type", "access")
            
            if user_id is None:
                raise credentials_exception

        except jwt.PyJWTError:
            raise credentials_exception

        # Obtener usuario
        user = db.query(User).options(
            selectinload(User.profile),
            selectinload(User.user_companies).selectinload(UserCompany.company)
        ).filter(User.id == user_id).first()
        
        if user is None or not user.is_active:
            raise credentials_exception

        # Determinar tenant_id
        tenant_id = None
        user_role = None

        if token_type == "context":
            # Token de contexto ya tiene tenant_id
            tenant_id = payload.get("tenant_id")
            user_role = payload.get("user_role")
        else:
            # Token de acceso, buscar en header o state
            company_id_str = request.headers.get("X-Company-ID") or getattr(request.state, 'tenant_id', None)
            if company_id_str:
                try:
                    tenant_id = str(UUID(company_id_str))
                    # Verificar que el usuario pertenece a esta empresa
                    user_company = next(
                        (uc for uc in user.user_companies 
                         if str(uc.company_id) == tenant_id and uc.is_active), 
                        None
                    )
                    if user_company:
                        user_role = user_company.role
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="No tienes acceso a esta empresa"
                        )
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="ID de empresa inválido"
                    )

        # Crear contexto
        companies = []
        for uc in user.user_companies:
            if uc.is_active:
                from app.modules.auth.schemas import UserCompanyOut
                companies.append(UserCompanyOut(
                    id=uc.id,
                    company_id=uc.company_id,
                    role=uc.role,
                    is_active=uc.is_active,
                    joined_at=uc.joined_at,
                    company_name=uc.company.name
                ))

        return AuthContext(
            user_id=UUID(user_id),
            tenant_id=UUID(tenant_id) if tenant_id else None,
            user_role=user_role,
            companies=companies
        )

    @staticmethod
    def require_role(allowed_roles: list[str]):
        """
        Dependencia para requerir roles específicos.
        """
        def role_checker(auth_context: AuthContext = Depends(AuthDependencies.get_auth_context)):
            if not auth_context.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Se requiere seleccionar una empresa"
                )
            
            if auth_context.user_role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Se requiere uno de estos roles: {', '.join(allowed_roles)}"
                )
            
            return auth_context
        return role_checker

    @staticmethod
    def require_owner_or_admin():
        """Dependencia para requerir rol de owner o admin."""
        return AuthDependencies.require_role(["owner", "admin"])

    @staticmethod
    def require_any_role():
        """Dependencia que requiere cualquier rol activo en una empresa."""
        return AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"])

# Instancias de dependencias
get_current_user = AuthDependencies.get_current_user
get_auth_context = AuthDependencies.get_auth_context
require_owner_or_admin = AuthDependencies.require_owner_or_admin
require_any_role = AuthDependencies.require_any_role