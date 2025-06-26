from fastapi import APIRouter, HTTPException, status, Depends
from app.modules.auth import service
from app.modules.auth.schemas import UserCreate, UserOut, CompanyCreate, CompanyOut, TokenResponse, UserOut, AssignUserToCompany, CompanyOutWithRole
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.dependencies.dbDependecies import db_dependency
from app.dependencies.userDependencies import user_dependency
from app.modules.auth.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

auth_router = APIRouter()
company_router = APIRouter()

@auth_router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    db: db_dependency,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Endpoint for user login.
    """
    token = service.login_user(db, form_data.username, form_data.password)
    return token

@auth_router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: db_dependency):
    """
    Register a new user.
    """
    try:
        user = service.create_user(db, user)
        return user
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    

@auth_router.get("/me", response_model=UserOut)
def get_me(current_user: User = user_dependency):
    """
    Endpoint to get the current authenticated user.
    """
    return current_user

@company_router.post("/", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(company: CompanyCreate, db: db_dependency,
                         current_user: User = user_dependency):
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
async def get_my_companies(db: db_dependency, current_user: User = user_dependency):
    """
    Endpoint to get all companies for the current user.
    """
    try:
        import uuid

        user_id = current_user.id
        if not isinstance(user_id, uuid.UUID):
            user_id = uuid.UUID(str(user_id))
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