import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from uuid import UUID, uuid4
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, or_

from app.modules.auth.models import (
    User, Profile, UserCompany, EmailVerificationToken, 
    PasswordResetToken, CompanyInvitation
)
from app.modules.auth.schemas import (
    UserCreate, UserOut, TokenResponse, ContextTokenResponse,
    CompanyInvitationCreate, AuthContext, UserCompanyOut
)
from app.modules.auth.utils import (
    hash_password, verify_password, create_access_token, 
    create_context_token, create_refresh_token, verify_token
)
from app.modules.company.models import Company
from app.modules.email.tasks import (
    send_verification_email_task, send_invitation_email_task, 
    send_password_reset_email_task
)
from app.core.config import settings

class AuthService:
    """
    Servicio de autenticación multi-tenant completo.
    """

    def __init__(self, db: Session):
        self.db = db

    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generar token seguro aleatorio usando secrets module.
        
        Args:
            length: Longitud del token (default: 32)
            
        Returns:
            str: Token seguro alfanumérico
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def create_user(self, user_data: UserCreate) -> Tuple[User, str]:
        """
        Crear nuevo usuario con verificación de email.
        
        Returns:
            Tuple[User, str]: Usuario creado y token de verificación
        """
        # Verificar si el email ya existe
        existing_user = self.db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este email ya está registrado"
            )

        # Crear perfil
        profile = Profile(
            first_name=user_data.profile.first_name,
            last_name=user_data.profile.last_name,
            phone_number=user_data.profile.phone_number,
            dni=user_data.profile.dni
        )
        self.db.add(profile)
        self.db.flush()

        # Crear usuario
        hashed_password = hash_password(user_data.password)
        user = User(
            email=user_data.email,
            password=hashed_password,
            profile_id=profile.id,
            is_active=False,
            email_verified=False
        )
        self.db.add(user)
        self.db.flush()

        # Paso 1: Solo crear usuario (la empresa se crea y asocia en un paso posterior)

        # Generar token de verificación
        verification_token = self.generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        email_token = EmailVerificationToken(
            user_id=user.id,
            token=verification_token,
            expires_at=expires_at
        )
        self.db.add(email_token)
        self.db.commit()

        # Enviar email de verificación (asíncrono)
        send_verification_email_task.delay(
            user_email=user.email,
            user_name=user.profile.first_name,
            verification_token=verification_token,
            company_name=None
        )

        return user, verification_token

    def verify_email(self, token: str) -> User:
        """Verificar email con token."""
        email_token = self.db.query(EmailVerificationToken).filter(
            EmailVerificationToken.token == token,
            EmailVerificationToken.is_used == False,
            EmailVerificationToken.expires_at > datetime.now(timezone.utc)
        ).first()

        if not email_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de verificación inválido o expirado"
            )

        # Marcar token como usado
        email_token.is_used = True
        email_token.used_at = datetime.now(timezone.utc)

        # Activar usuario
        user = email_token.user
        user.is_active = True
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)

        self.db.commit()
        return user

    def resend_verification(self, email: str) -> bool:
        """Reenviar email de verificación si el usuario aún no ha verificado."""
        user = self.db.query(User).options(selectinload(User.profile)).filter(User.email == email).first()
        if not user:
            # No revelar existencia
            return True

        if user.email_verified and user.is_active:
            # Ya verificado; no es necesario reenviar
            return True

        # Invalidar tokens anteriores no usados
        self.db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.is_used == False
        ).update({"is_used": True})

        # Crear nuevo token
        verification_token = self.generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        token_record = EmailVerificationToken(
            user_id=user.id,
            token=verification_token,
            expires_at=expires_at
        )
        self.db.add(token_record)
        self.db.commit()

        # Enviar email (asíncrono)
        send_verification_email_task.delay(
            user_email=user.email,
            user_name=user.profile.first_name if user.profile else user.email,
            verification_token=verification_token,
            company_name=None
        )
        return True

    def login(self, email: str, password: str) -> TokenResponse:
        """
        Login de usuario con listado de empresas.
        """
        user = self.db.query(User).options(
            selectinload(User.profile),
            selectinload(User.user_companies).selectinload(UserCompany.company)
        ).filter(User.email == email).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas"
            )

        if not verify_password(password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta inactiva. Verifica tu email."
            )

        if not user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email no verificado. Revisa tu bandeja de entrada."
            )

        # Actualizar último login
        user.last_login = datetime.now(timezone.utc)
        self.db.commit()

        # Crear token de acceso (sin tenant_id aún)
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "user_name": user.profile.full_name
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(str(user.id))

        # Obtener empresas del usuario
        companies = []
        for uc in user.user_companies:
            if uc.is_active:
                companies.append(UserCompanyOut(
                    id=uc.id,
                    company_id=uc.company_id,
                    role=uc.role,
                    is_active=uc.is_active,
                    joined_at=uc.joined_at,
                    company_name=uc.company.name
                ))

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserOut.from_orm(user),
            companies=companies,
            refresh_token=refresh_token
        )

    def select_company(self, user_id: UUID, company_id: UUID) -> ContextTokenResponse:
        """
        Seleccionar empresa y generar token de contexto.
        """
        user_company = self.db.query(UserCompany).options(
            selectinload(UserCompany.company),
            selectinload(UserCompany.user).selectinload(User.profile)
        ).filter(
            UserCompany.user_id == user_id,
            UserCompany.company_id == company_id,
            UserCompany.is_active == True
        ).first()

        if not user_company:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esta empresa"
            )

        # Crear token de contexto con tenant_id
        token_data = {
            "sub": str(user_id),
            "email": user_company.user.email,
            "user_name": user_company.user.profile.full_name,
            "tenant_id": str(company_id),
            "user_role": user_company.role
        }
        
        context_token = create_context_token(token_data)

        return ContextTokenResponse(
            access_token=context_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            tenant_id=company_id,
            company_name=user_company.company.name,
            user_role=user_company.role
        )

    def request_password_reset(self, email: str) -> bool:
        """Solicitar restablecimiento de contraseña."""
        user = self.db.query(User).options(
            selectinload(User.profile)
        ).filter(User.email == email).first()

        if not user:
            # No revelar si el email existe o no
            return True

        # Invalidar tokens anteriores
        self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_used == False
        ).update({"is_used": True})

        # Crear nuevo token
        reset_token = self.generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        token_record = PasswordResetToken(
            user_id=user.id,
            token=reset_token,
            expires_at=expires_at
        )
        self.db.add(token_record)
        self.db.commit()

        # Enviar email (asíncrono)
        send_password_reset_email_task.delay(
            user_email=user.email,
            user_name=user.profile.first_name,
            reset_token=reset_token
        )

        return True

    def reset_password(self, token: str, new_password: str) -> User:
        """Restablecer contraseña con token."""
        reset_token = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.now(timezone.utc)
        ).first()

        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de restablecimiento inválido o expirado"
            )

        # Actualizar contraseña
        user = reset_token.user
        user.password = hash_password(new_password)

        # Marcar token como usado
        reset_token.is_used = True
        reset_token.used_at = datetime.now(timezone.utc)

        self.db.commit()
        return user

    def invite_user(
        self, 
        company_id: UUID, 
        invited_by_id: UUID, 
        invitation_data: CompanyInvitationCreate
    ) -> CompanyInvitation:
        """Invitar usuario a empresa."""
        # Verificar que quien invita tiene permisos
        inviter_company = self.db.query(UserCompany).filter(
            UserCompany.user_id == invited_by_id,
            UserCompany.company_id == company_id,
            UserCompany.role.in_(["owner", "admin"]),
            UserCompany.is_active == True
        ).first()

        if not inviter_company:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para invitar usuarios"
            )

        # Verificar si ya existe usuario con ese email en la empresa
        existing_user = self.db.query(User).filter(User.email == invitation_data.email).first()
        if existing_user:
            existing_relation = self.db.query(UserCompany).filter(
                UserCompany.user_id == existing_user.id,
                UserCompany.company_id == company_id
            ).first()
            if existing_relation:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Este usuario ya pertenece a la empresa"
                )

        # Verificar si ya existe invitación pendiente
        existing_invitation = self.db.query(CompanyInvitation).filter(
            CompanyInvitation.company_id == company_id,
            CompanyInvitation.invitee_email == invitation_data.email,
            CompanyInvitation.is_accepted == False,
            CompanyInvitation.expires_at > datetime.now(timezone.utc)
        ).first()

        if existing_invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una invitación pendiente para este email"
            )

        # Crear invitación
        invitation_token = self.generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        invitation = CompanyInvitation(
            company_id=company_id,
            invited_by_id=invited_by_id,
            invitee_email=invitation_data.email,
            role=invitation_data.role,
            token=invitation_token,
            expires_at=expires_at
        )
        self.db.add(invitation)
        self.db.commit()

        # Obtener datos para el email
        company = self.db.query(Company).filter(Company.id == company_id).first()
        inviter = self.db.query(User).options(selectinload(User.profile)).filter(User.id == invited_by_id).first()

        # Enviar email (asíncrono)
        send_invitation_email_task.delay(
            invitee_email=invitation_data.email,
            inviter_name=inviter.profile.full_name,
            company_name=company.name,
            invitation_token=invitation_token,
            role=invitation_data.role
        )

        return invitation

    def accept_invitation(self, token: str, password: str, profile_data: dict) -> Tuple[User, Company]:
        """Aceptar invitación y crear usuario."""
        invitation = self.db.query(CompanyInvitation).options(
            selectinload(CompanyInvitation.company)
        ).filter(
            CompanyInvitation.token == token,
            CompanyInvitation.is_accepted == False,
            CompanyInvitation.expires_at > datetime.now(timezone.utc)
        ).first()

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitación inválida o expirada"
            )

        # Verificar si ya existe usuario con ese email
        existing_user = self.db.query(User).filter(User.email == invitation.invitee_email).first()
        
        if existing_user:
            # Si el usuario ya existe, solo crear la relación
            user = existing_user
        else:
            # Crear nuevo usuario
            profile = Profile(**profile_data)
            self.db.add(profile)
            self.db.flush()

            user = User(
                email=invitation.invitee_email,
                password=hash_password(password),
                profile_id=profile.id,
                is_active=True,
                email_verified=True,
                email_verified_at=datetime.now(timezone.utc)
            )
            self.db.add(user)
            self.db.flush()

        # Crear relación usuario-empresa
        user_company = UserCompany(
            user_id=user.id,
            company_id=invitation.company_id,
            role=invitation.role,
            is_active=True
        )
        self.db.add(user_company)

        # Marcar invitación como aceptada
        invitation.is_accepted = True
        invitation.accepted_at = datetime.now(timezone.utc)

        self.db.commit()
        return user, invitation.company

    def list_invitations(
        self,
        company_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> list:
        """Listar invitaciones pendientes por empresa (paginadas)."""
        query = self.db.query(CompanyInvitation).options(
            selectinload(CompanyInvitation.company),
            selectinload(CompanyInvitation.invited_by).selectinload(User.profile)
        ).filter(
            CompanyInvitation.company_id == company_id,
            CompanyInvitation.is_accepted == False,
            CompanyInvitation.expires_at > datetime.now(timezone.utc)
        ).order_by(CompanyInvitation.created_at.desc())

        invitations = query.offset(offset).limit(min(limit, 100)).all()

        results = []
        for inv in invitations:
            results.append({
                "id": inv.id,
                "invitee_email": inv.invitee_email,
                "role": inv.role,
                "expires_at": inv.expires_at,
                "is_accepted": inv.is_accepted,
                "invited_by_name": inv.invited_by.profile.full_name if inv.invited_by and inv.invited_by.profile else "",
                "company_name": inv.company.name if inv.company else ""
            })
        return results

    def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Generar un nuevo access token a partir de un refresh token válido."""
        payload = verify_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token no es de tipo refresh")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token inválido")

        # Cargar usuario y empresas
        user = self.db.query(User).options(
            selectinload(User.profile),
            selectinload(User.user_companies).selectinload(UserCompany.company)
        ).filter(User.id == user_id).first()

        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inválido")

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "user_name": user.profile.full_name if user.profile else user.email
        }
        access_token = create_access_token(token_data)

        companies = []
        for uc in user.user_companies:
            if uc.is_active:
                companies.append(UserCompanyOut(
                    id=uc.id,
                    company_id=uc.company_id,
                    role=uc.role,
                    is_active=uc.is_active,
                    joined_at=uc.joined_at,
                    company_name=uc.company.name
                ))

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserOut.from_orm(user),
            companies=companies
        )

