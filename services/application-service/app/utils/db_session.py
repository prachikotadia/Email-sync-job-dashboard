from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# For now we use SQLite for simplicity if no DB url provided, or fallback to mock
# In prod, settings.DATABASE_URL will be populated
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL or "sqlite:///./app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
# Import Base to allow Alembic/Auto-creation
from app.db.models import Base
# Create All Tables (Dev Mode)
Base.metadata.create_all(bind=engine)
