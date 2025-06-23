from fastapi import FastAPI
import app.modules.auth.models as models
from app.database.database import engine
from app.modules.auth.models import User, Profile
from app.modules.auth.router import auth_router
from modules.inventory.router import product_router, category_router

app = FastAPI(title="Ally360 API",
             description="API for Ally360 is a ERP system for managing employee relations.",
             version="1.0.0",
             contact={
                 "name": "Ally360 Support",
                 "url": "https://ally360.com/support",
                 "email": "support@ally360.com"
             }
           )

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(product_router, prefix="/inventory", tags=["Products"])
app.include_router(category_router, prefix="/inventory", tags=["Categories"])


@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}


