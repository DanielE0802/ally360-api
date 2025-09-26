from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.modules.auth import service
from app.modules.auth.schemas import UserCreate, UserOut, TokenResponse
from app.dependencies.dbDependecies import db_dependency
from app.dependencies.userDependencies import user_dependency

auth_router = APIRouter()

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
        created_user = service.create_user(db, user)
        return created_user
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@auth_router.get("/me", response_model=UserOut)
def get_me(current_user: user_dependency):
    """
    Endpoint to get the current authenticated user.
    """
    return current_user

@auth_router.get("/health")
def auth_health():
    """Health check for auth module"""
    return {"status": "ok", "module": "auth"}