from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session
from app.modules.company.schemas import CompanyCreate, CompanyOutWithRole, AssignUserToCompany
from app.modules.auth.utils import create_access_token
from app.dependencies.dbDependecies import db_dependency
from app.modules.auth.models import User, UserCompany
from app.modules.company.models import Company
from uuid import UUID

def create_company(db: db_dependency, company_data: CompanyCreate, current_user: User) -> Company:
    """
    Create a new company in the database.

    Args:
        company_data (CompanyCreate): The company data to create.

    Returns:
        Company: The created company object.
    """

    if db.query(Company).filter_by(name=company_data.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company name already exists")

    company = Company(**company_data.model_dump())
    db.add(company)
    db.flush()

    user_company = UserCompany(user_id=current_user.id, company_id=company.id, is_active=True, role="admin")
    db.add(user_company)
    db.commit()
    db.refresh(company)

    return company

def assign_user_to_company(db: db_dependency, assignment: AssignUserToCompany) -> dict:
    """
    Assign a user to a company with a specific role.

    Args:
        user_id (str): The ID of the user to assign.
        company_id (str): The ID of the company to assign the user to.
        role (str): The role of the user in the company.

    Returns:
        UserCompany: The UserCompany object representing the assignment.

    Raises:
        HTTPException: If the user or company does not exist, or if the assignment already exists.
    """
    
    existing_assignment = db.query(UserCompany).filter_by(user_id=assignment.user_id, company_id=assignment.company_id).first()
    if existing_assignment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already assigned to this company")

    company = db.query(Company).filter_by(id=assignment.company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    relation = UserCompany(
        user_id=assignment.user_id,
        company_id=assignment.company_id,
        role=assignment.role
    )

    db.add(relation)
    db.commit()

    return {"message": "User assigned to company successfully", "user_company": relation}

def get_companies_for_user(db: db_dependency, user_id: UUID) -> list[CompanyOutWithRole]:
    """
    Get all companies associated with a user.

    Args:
        db (db_dependency): The database session.
        user (User): The user for whom to retrieve companies.

    Returns:
        list[CompanyOutWithRole]: A list of companies associated with the user.
    """

    all_user_companies = db.query(UserCompany).filter_by(user_id=user_id, is_active=True).all()
    if not all_user_companies:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No companies found for this user")
    return [
        CompanyOutWithRole(
            **vars(user_company.company),
            role=str(user_company.role)
        )
        for user_company in all_user_companies
    ]
    
def select_company(db: db_dependency, company_id: UUID, current_user: User):
    """
    Select a company for the current user and return new access token with company context.
    """

    user_company = db.query(UserCompany).filter_by(user_id=current_user.id, company_id=company_id).first()
    if not user_company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Don't have access to this company")

    token = create_access_token({
        "email": current_user.email,
        "first_name": current_user.profile.first_name,
        "role": user_company.role,
        "company_id": str(user_company.company_id),
        "sub": str(current_user.id)
    })
    
    return {"access_token": token, "token_type": "bearer"}

def create_tenant_company(db: Session, name: str, owner_id: UUID) -> Company:
    """
    Crear nueva empresa para multi-tenant con configuración completa.
    
    Args:
        db: Sesión de base de datos
        name: Nombre de la empresa
        owner_id: ID del usuario propietario
        
    Returns:
        Company: Empresa creada
    """
    # Verificar que no exista una empresa con el mismo nombre
    existing_company = db.query(Company).filter(Company.name == name).first()
    if existing_company:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una empresa con este nombre"
        )
    
    # Crear la empresa
    from uuid import uuid4
    company = Company(
        name=name,
        description=f"Empresa creada para {name}",
        is_active=True,
        nit=f"NIT-{uuid4()}",
        phone_number=None
        # Los demás campos se pueden llenar posteriormente
    )
    
    db.add(company)
    db.flush()  # Para obtener el ID
    
    # Aquí podrías agregar lógica adicional de tenant:
    # - Crear schemas específicos si usas schema-per-tenant
    # - Configurar límites por defecto
    # - Crear PDVs por defecto
    # - Inicializar configuraciones base
    
    db.commit()
    db.refresh(company)
    
    return company

