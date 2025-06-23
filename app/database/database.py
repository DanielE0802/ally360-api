from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.core.config import settings

DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency para FastAPI
def get_db():
    """Genera una sesión de base de datos para ser usada en las rutas de FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base = declarative_base()

