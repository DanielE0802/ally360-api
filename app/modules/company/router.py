from fastapi import APIRouter, HTTPException, status, Path, UploadFile, File, Depends
from sqlalchemy.orm import Session
from app.modules.company import service
from app.modules.company.schemas import CompanyCreate, CompanyOut, AssignUserToCompany, CompanyOutWithRole, CompanyUpdate, CompanyImageUploadResponse, CompanyLogoResponse
from app.dependencies.dbDependecies import db_dependency, get_db
from app.dependencies.userDependencies import user_dependency
from app.modules.auth.dependencies import get_current_user
from uuid import UUID

# imports from auth module
from app.modules.auth.schemas import UserOut
from app.modules.auth.models import User


company_router = APIRouter()

@company_router.post("/", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(company: CompanyCreate, db: db_dependency,
                         current_user: user_dependency):
    """
    Endpoint to create a company.
    """
    try:
        company = service.create_company(db, company, current_user)
        return company
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@company_router.get("/my_companies", response_model=list[CompanyOut], status_code=status.HTTP_200_OK)
async def get_my_companies(db: db_dependency, current_user: user_dependency):
    """
    Endpoint to get all companies for the current user.
    """
    try:

        user_id = current_user.id
        if not isinstance(user_id, UUID):
            user_id = UUID(str(user_id))
        user_companies = service.get_companies_for_user(db, user_id)
        return user_companies
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@company_router.post("/assign_user", response_model=UserOut, status_code=status.HTTP_200_OK)
async def assign_user(
    db: db_dependency,
    assignment: AssignUserToCompany,
):
    """
    Assign a user to a company with a specific role.
    """
    return service.assign_user_to_company(db, assignment)

@company_router.post("/select-company", status_code=status.HTTP_200_OK)
async def select_company(
    db: db_dependency,
    company_id: UUID,
    current_user: user_dependency
):
    """
    Select a company for the current user and return new token with company context.
    """
    return service.select_company(db, company_id, current_user)


@company_router.patch("/me", response_model=CompanyOut)
async def update_company(
    company_update: CompanyUpdate,
    db: db_dependency,
    current_user: user_dependency
):
    """
    Actualizar información de la empresa actual del usuario.
    No permite cambiar NIT.
    """
    return service.update_company(db, company_update, current_user)


@company_router.post("/me/logo", response_model=CompanyImageUploadResponse)
async def upload_company_logo(
    db: db_dependency,
    current_user: user_dependency,
    file: UploadFile = File(...)
):
    """
    Subir logo de la empresa actual del usuario.
    """
    return service.upload_company_logo(db, file, current_user)


@company_router.get("/me/logo", response_model=CompanyLogoResponse)
async def get_company_logo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener URL temporal para acceder al logo de la empresa actual.
    """
    return service.get_company_logo_url(db, current_user)


