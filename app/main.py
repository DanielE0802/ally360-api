from fastapi import FastAPI
import app.modules.auth.models as models
from app.database.database import engine, Base
from app.modules.auth.models import User, Profile
from app.modules.auth.router import auth_router
from app.modules.company.router import company_router
from app.modules.pdv.router import pdv_router
from app.modules.products.router import product_router
from app.modules.brands.router import brand_router
from app.modules.categories.router import categories_router
from app.modules.products.router import product_router

app = FastAPI(title="Ally360 API",
             description="API for Ally360 is a ERP system for managing employee relations.",
             version="1.0.0",
             contact={
                 "name": "Ally360 Support",
                 "url": "https://ally360.com/support",
                 "email": "support@ally360.com"
             }
           )


app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(company_router, prefix="/company", tags=["Companies"])
app.include_router(categories_router)
app.include_router(pdv_router, prefix="/pdv", tags=["PDVs"])
app.include_router(product_router)
app.include_router(brand_router)

Base.metadata.create_all(bind=engine)

@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}


