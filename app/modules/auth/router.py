from fastapi import APIRouter

auth_router = APIRouter()

@auth_router.post("/login")
async def login():
    return {"message": "Login endpoint"}

@auth_router.post("/register")
async def register():
    return {"message": "Register endpoint"}