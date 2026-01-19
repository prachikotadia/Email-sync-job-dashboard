"""
Integration Tests for Resume Service
Tests end-to-end flows: upload -> link -> delete, default resume workflow, etc.
"""
import pytest
import uuid
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch
import tempfile
from datetime import datetime, timezone

# Set TESTING environment variable before importing app modules
os.environ["TESTING"] = "true"

from app.main import app
from app.database import Base, get_db, Resume, ApplicationResume, engine, SessionLocal, UUIDType
from app.storage import LocalStorage
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, text


# Test database setup - use file-based SQLite for tests (more reliable than in-memory)
import tempfile
_test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
_test_db_path = _test_db_file.name
_test_db_file.close()

SQLALCHEMY_DATABASE_URL = f"sqlite:///{_test_db_path}"
test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Override the app's engine to use the test engine
import app.database as db_module
db_module.engine = test_engine
db_module.SessionLocal = TestingSessionLocal

# Create minimal stub models for foreign key references
# Use extend_existing to avoid redefinition errors when importing multiple test modules
try:
    class User(Base):
        """Stub User model for tests"""
        __tablename__ = "users"
        __table_args__ = {'extend_existing': True}
        id = Column(UUIDType, primary_key=True)
        email = Column(String, unique=True, nullable=False)
        created_at = Column(DateTime(timezone=True), nullable=False)

    class Application(Base):
        """Stub Application model for tests"""
        __tablename__ = "applications"
        __table_args__ = {'extend_existing': True}
        id = Column(UUIDType, primary_key=True)
        user_id = Column(UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
        gmail_message_id = Column(String, nullable=False)
        gmail_thread_id = Column(String)
        gmail_web_url = Column(Text, nullable=False)
        company_name = Column(String)
        category = Column(String)
        subject = Column(Text)
        received_at = Column(DateTime(timezone=True))
        created_at = Column(DateTime(timezone=True), nullable=False)
except Exception:
    # Models already defined in another test module, that's okay
    pass


@pytest.fixture(scope="session")
def setup_test_db():
    """Create test database tables once per test session"""
    # Disable foreign key checks in SQLite for tests
    with test_engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        conn.commit()
    
    # Create all tables (including stub User and Application models)
    Base.metadata.create_all(bind=test_engine)
    
    # Re-enable foreign keys
    with test_engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.commit()
    
    yield
    
    # Cleanup at end of test session
    Base.metadata.drop_all(bind=test_engine)
    import os
    try:
        os.unlink(_test_db_path)
    except Exception:
        pass

@pytest.fixture(scope="function")
def db(setup_test_db):
    """Get database session for each test"""
    db = TestingSessionLocal()
    
    # Clear data between tests to ensure isolation
    try:
        db.execute(text("DELETE FROM application_resumes"))
        db.execute(text("DELETE FROM resumes"))
        db.execute(text("DELETE FROM applications"))
        db.execute(text("DELETE FROM users"))
        db.commit()
    except Exception:
        db.rollback()
    
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture
def client(db):
    """Create test client with database override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    def mock_get_current_user():
        return "test@example.com"
    
    from app.main import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    with patch('app.main.get_user_id_from_email') as mock_get_user_id:
        mock_user_id = str(uuid.uuid4())  # String for SQLite
        
        # CRITICAL: Create the user in the test database
        try:
            db.execute(text("""
                INSERT INTO users (id, email, created_at) 
                VALUES (:id, :email, :created_at)
            """), {
                "id": mock_user_id,
                "email": "test@example.com",
                "created_at": datetime.now(timezone.utc)
            })
            db.commit()
        except Exception:
            db.rollback()
        
        mock_get_user_id.return_value = mock_user_id
        
        with patch('app.main.get_storage') as mock_get_storage:
            temp_dir = tempfile.mkdtemp()
            storage = LocalStorage(temp_dir)
            mock_get_storage.return_value = storage
            
            client = TestClient(app)
            yield client
            
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_pdf_content():
    return b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 0\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'


class TestResumeWorkflow:
    """Test complete resume workflow"""
    
    def test_complete_resume_lifecycle(self, client, db, sample_pdf_content):
        """Test: Upload -> Set Default -> Link to App -> Get Usage -> Delete"""
        from sqlalchemy import text
        
        # Setup: Get or create user and application
        user_result = db.execute(
            text("SELECT id FROM users WHERE email = 'test@example.com'")
        ).first()
        
        if not user_result:
            user_id = str(uuid.uuid4())  # Convert to string for SQLite
            db.execute(
                text("INSERT INTO users (id, email, created_at) VALUES (:id, :email, :created_at)"),
                {"id": user_id, "email": "test@example.com", "created_at": datetime.now(timezone.utc)}
            )
            db.commit()
        else:
            user_id = str(user_result[0])  # Ensure string for SQLite
        
        app_id = str(uuid.uuid4())  # Convert to string for SQLite
        db.execute(
            text("""
                INSERT INTO applications (id, user_id, gmail_message_id, gmail_thread_id, gmail_web_url, 
                                         company_name, category, subject, received_at, created_at)
                VALUES (:id, :user_id, :msg_id, :thread_id, :web_url, :company, :category, :subject, :received_at, :created_at)
            """),
            {
                "id": app_id,
                "user_id": user_id,
                "msg_id": "test_msg_id",
                "thread_id": "test_thread_id",
                "web_url": "https://mail.google.com/mail/u/0/#all/test_msg_id",
                "company": "Test Company",
                "category": "APPLIED",
                "subject": "Test Subject",
                "received_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
            }
        )
        db.commit()
        
        # 1. Upload resume
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files, params={"file_name": "My Resume"})
        assert upload_response.status_code == 201
        resume_id = upload_response.json()["id"]
        
        # 2. Set as default
        default_response = client.post(f"/resumes/{resume_id}/set-default")
        assert default_response.status_code == 200
        assert default_response.json()["is_default"] is True
        
        # 3. Link to application
        link_response = client.post(f"/applications/{app_id}/resume/{resume_id}")
        assert link_response.status_code == 201
        
        # 4. Verify usage count
        list_response = client.get("/resumes")
        assert list_response.status_code == 200
        resume_data = next(r for r in list_response.json() if r["id"] == resume_id)
        assert resume_data["usage_count"] == 1
        
        # 5. Get application resume
        app_resume_response = client.get(f"/applications/{app_id}/resume")
        assert app_resume_response.status_code == 200
        assert app_resume_response.json()["resume"]["id"] == resume_id
        
        # 6. Try to delete (should fail - linked to application)
        delete_response = client.delete(f"/resumes/{resume_id}")
        assert delete_response.status_code == 400
        assert "linked" in delete_response.json()["detail"].lower()
        
        # 7. Unlink (by linking different resume or deleting link manually)
        # For now, we'll just verify the link exists
        assert app_resume_response.json()["resume"] is not None
    
    def test_multiple_resumes_default_switching(self, client, sample_pdf_content):
        """Test: Upload multiple resumes, switch default"""
        # Upload 3 resumes
        resume_ids = []
        for i in range(3):
            content = sample_pdf_content + f"extra{i}".encode()
            files = {"file": (f"resume{i}.pdf", content, "application/pdf")}
            upload_response = client.post("/resumes/upload", files=files)
            assert upload_response.status_code == 201
            resume_ids.append(upload_response.json()["id"])
        
        # Set first as default
        client.post(f"/resumes/{resume_ids[0]}/set-default")
        
        # Verify only first is default
        list_response = client.get("/resumes")
        resumes = list_response.json()
        defaults = [r for r in resumes if r["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["id"] == resume_ids[0]
        
        # Switch to second
        client.post(f"/resumes/{resume_ids[1]}/set-default")
        
        # Verify only second is default now
        list_response = client.get("/resumes")
        resumes = list_response.json()
        defaults = [r for r in resumes if r["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["id"] == resume_ids[1]
    
    def test_resume_rename_and_usage_tracking(self, client, db, sample_pdf_content):
        """Test: Upload -> Rename -> Link -> Verify usage count updates"""
        from sqlalchemy import text
        
        # Setup: Get or create user
        user_result = db.execute(
            text("SELECT id FROM users WHERE email = 'test@example.com'")
        ).first()
        
        if not user_result:
            user_id = str(uuid.uuid4())  # Convert to string for SQLite
            db.execute(
                text("INSERT INTO users (id, email, created_at) VALUES (:id, :email, :created_at)"),
                {"id": user_id, "email": "test@example.com", "created_at": datetime.now(timezone.utc)}
            )
            db.commit()
        else:
            user_id = str(user_result[0])  # Ensure string for SQLite
        
        app_id1 = str(uuid.uuid4())  # Convert to string for SQLite
        app_id2 = str(uuid.uuid4())  # Convert to string for SQLite
        for app_id in [app_id1, app_id2]:
            db.execute(
                text("""
                    INSERT INTO applications (id, user_id, gmail_message_id, gmail_thread_id, gmail_web_url, 
                                             company_name, category, subject, received_at, created_at)
                    VALUES (:id, :user_id, :msg_id, :thread_id, :web_url, :company, :category, :subject, :received_at, :created_at)
                """),
                {
                    "id": app_id,
                    "user_id": user_id,
                    "msg_id": f"test_msg_id_{app_id}",
                    "thread_id": f"test_thread_id_{app_id}",
                    "web_url": f"https://mail.google.com/mail/u/0/#all/test_msg_id_{app_id}",
                    "company": "Test Company",
                    "category": "APPLIED",
                    "subject": "Test Subject",
                    "received_at": datetime.now(timezone.utc),
                    "created_at": datetime.now(timezone.utc),
                }
            )
        db.commit()
        
        # Upload resume
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        resume_id = upload_response.json()["id"]
        
        # Rename
        rename_response = client.put(
            f"/resumes/{resume_id}/rename",
            json={"file_name": "Updated Resume Name"}
        )
        assert rename_response.status_code == 200
        assert rename_response.json()["file_name"] == "Updated Resume Name"
        
        # Link to first application
        client.post(f"/applications/{app_id1}/resume/{resume_id}")
        
        # Verify usage count = 1
        list_response = client.get("/resumes")
        resume_data = next(r for r in list_response.json() if r["id"] == resume_id)
        assert resume_data["usage_count"] == 1
        
        # Link to second application
        client.post(f"/applications/{app_id2}/resume/{resume_id}")
        
        # Verify usage count = 2
        list_response = client.get("/resumes")
        resume_data = next(r for r in list_response.json() if r["id"] == resume_id)
        assert resume_data["usage_count"] == 2
