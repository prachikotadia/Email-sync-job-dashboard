"""
Backend Unit Tests for Resume Service
Tests all endpoints: upload, list, rename, delete, set-default, link to application
"""
import pytest
import uuid
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey, text
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch, MagicMock
import tempfile
from datetime import datetime, timezone

# Set TESTING environment variable before importing app modules
os.environ["TESTING"] = "true"

from app.main import app
from app.database import Base, get_db, Resume, ApplicationResume, engine, SessionLocal, UUIDType
from app.storage import get_storage, LocalStorage


# Test database setup - use file-based SQLite for tests (more reliable than in-memory)
import tempfile
_test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
_test_db_path = _test_db_file.name
_test_db_file.close()

SQLALCHEMY_DATABASE_URL = f"sqlite:///{_test_db_path}"
test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Override the app's engine to use the test engine
# This ensures the app uses the same database as the tests
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
        db.commit()  # Commit any changes
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture
def client(db):
    """Create test client with database override"""
    # Ensure tables exist - create them using the test engine
    Base.metadata.create_all(bind=test_engine)
    
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Mock JWT verification
    def mock_get_current_user():
        return "test@example.com"
    
    from app.main import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    # Create a unique user for this test
    mock_user_id = str(uuid.uuid4())  # String for SQLite
    
    # CRITICAL: Create the user in the test database
    # This ensures foreign key constraints are satisfied
    try:
        # Check if user already exists (use same email for consistency)
        result = db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": "test@example.com"}).first()
        if result:
            mock_user_id = result[0]
        else:
            # Create new user
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
        # Try to get existing user
        try:
            result = db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": "test@example.com"}).first()
            if result:
                mock_user_id = result[0]
        except Exception:
            pass
    
    # Mock user_id lookup
    mock_get_user_id = patch('app.main.get_user_id_from_email', return_value=mock_user_id)
    mock_get_user_id.start()
    
    # Mock storage
    temp_dir = tempfile.mkdtemp()
    storage = LocalStorage(temp_dir)
    mock_get_storage = patch('app.main.get_storage', return_value=storage)
    mock_get_storage.start()
    
    try:
        client = TestClient(app)
        yield client
    finally:
        # Cleanup
        mock_get_storage.stop()
        mock_get_user_id.stop()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        app.dependency_overrides.clear()


@pytest.fixture
def sample_pdf_content():
    """Generate sample PDF content for testing"""
    # Minimal valid PDF header - make it at least 1KB to ensure file_size_kb > 0
    base_pdf = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 0\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
    # Pad to ensure it's at least 1KB
    padding = b' ' * (1024 - len(base_pdf) + 100)  # Add extra padding
    return base_pdf + padding


@pytest.fixture
def sample_docx_content():
    """Generate sample DOCX content for testing"""
    # ZIP file header (DOCX is a ZIP file) - make it at least 1KB
    base_docx = b'PK\x03\x04\x14\x00\x00\x00\x08\x00\x00\x00!\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    # Pad to ensure it's at least 1KB
    padding = b' ' * (1024 - len(base_docx) + 100)  # Add extra padding
    return base_docx + padding


class TestResumeUpload:
    """Test resume upload endpoint"""
    
    def test_upload_pdf_success(self, client, sample_pdf_content):
        """Test successful PDF upload"""
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        response = client.post("/resumes/upload", files=files)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["file_name"] == "resume"
        assert data["file_type"] == "pdf"
        assert data["file_size_kb"] > 0
        assert data["is_default"] is False
    
    def test_upload_docx_success(self, client, sample_docx_content):
        """Test successful DOCX upload"""
        files = {"file": ("resume.docx", sample_docx_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = client.post("/resumes/upload", files=files, params={"file_name": "My Resume"})
        
        assert response.status_code == 201
        data = response.json()
        assert data["file_name"] == "My Resume"
        assert data["file_type"] == "docx"
    
    def test_upload_invalid_file_type(self, client):
        """Test upload with invalid file type"""
        files = {"file": ("resume.txt", b"invalid content", "text/plain")}
        response = client.post("/resumes/upload", files=files)
        
        assert response.status_code == 400
        assert "Only PDF and DOCX" in response.json()["detail"]
    
    def test_upload_file_too_large(self, client, sample_pdf_content):
        """Test upload with file exceeding size limit"""
        # Create a large file (6MB)
        large_content = sample_pdf_content * (6 * 1024 * 1024 // len(sample_pdf_content) + 1)
        files = {"file": ("resume.pdf", large_content, "application/pdf")}
        
        response = client.post("/resumes/upload", files=files)
        
        assert response.status_code == 400
        assert "exceeds" in response.json()["detail"].lower()
    
    def test_upload_duplicate_file(self, client, sample_pdf_content):
        """Test upload of duplicate file (same checksum)"""
        files = {"file": ("resume1.pdf", sample_pdf_content, "application/pdf")}
        response1 = client.post("/resumes/upload", files=files)
        assert response1.status_code == 201
        
        # Try to upload same file again
        files2 = {"file": ("resume2.pdf", sample_pdf_content, "application/pdf")}
        response2 = client.post("/resumes/upload", files=files2)
        
        assert response2.status_code == 400
        assert "identical content" in response2.json()["detail"].lower()


class TestResumeList:
    """Test resume listing endpoint"""
    
    def test_list_resumes_empty(self, client):
        """Test listing resumes when none exist"""
        response = client.get("/resumes")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_list_resumes_with_data(self, client, sample_pdf_content):
        """Test listing resumes with data"""
        # Upload a resume
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        assert upload_response.status_code == 201
        
        # List resumes
        response = client.get("/resumes")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == upload_response.json()["id"]
        assert data[0]["usage_count"] == 0


class TestResumeOperations:
    """Test resume operations: get, rename, delete, set-default"""
    
    def test_get_resume(self, client, sample_pdf_content):
        """Test getting a specific resume"""
        # Upload a resume
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        resume_id = upload_response.json()["id"]
        
        # Get resume
        response = client.get(f"/resumes/{resume_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == resume_id
        assert data["file_name"] == "resume"
    
    def test_get_resume_not_found(self, client):
        """Test getting non-existent resume"""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/resumes/{fake_id}")
        
        assert response.status_code == 404
    
    def test_rename_resume(self, client, sample_pdf_content):
        """Test renaming a resume"""
        # Upload a resume
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        resume_id = upload_response.json()["id"]
        
        # Rename
        response = client.put(
            f"/resumes/{resume_id}/rename",
            json={"file_name": "Updated Resume Name"}
        )
        
        assert response.status_code == 200
        assert response.json()["file_name"] == "Updated Resume Name"
    
    def test_rename_resume_empty_name(self, client, sample_pdf_content):
        """Test renaming with empty name"""
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        resume_id = upload_response.json()["id"]
        
        response = client.put(
            f"/resumes/{resume_id}/rename",
            json={"file_name": ""}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_set_default_resume(self, client, sample_pdf_content):
        """Test setting default resume"""
        # Upload two resumes
        files1 = {"file": ("resume1.pdf", sample_pdf_content, "application/pdf")}
        upload1 = client.post("/resumes/upload", files=files1)
        resume_id_1 = upload1.json()["id"]
        
        # Create different content for second resume
        files2 = {"file": ("resume2.pdf", sample_pdf_content + b"extra", "application/pdf")}
        upload2 = client.post("/resumes/upload", files=files2)
        resume_id_2 = upload2.json()["id"]
        
        # Set first as default
        response1 = client.post(f"/resumes/{resume_id_1}/set-default")
        assert response1.status_code == 200
        assert response1.json()["is_default"] is True
        
        # Set second as default (should unset first)
        response2 = client.post(f"/resumes/{resume_id_2}/set-default")
        assert response2.status_code == 200
        assert response2.json()["is_default"] is True
        
        # Verify first is no longer default
        get_response = client.get(f"/resumes/{resume_id_1}")
        assert get_response.json()["is_default"] is False
    
    def test_delete_resume(self, client, sample_pdf_content):
        """Test deleting a resume"""
        # Upload a resume
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        resume_id = upload_response.json()["id"]
        
        # Delete
        response = client.delete(f"/resumes/{resume_id}")
        
        assert response.status_code == 204
        
        # Verify it's deleted (soft delete)
        get_response = client.get(f"/resumes/{resume_id}")
        assert get_response.status_code == 404
    
    def test_delete_resume_linked_to_application(self, client, db, sample_pdf_content):
        """Test deleting resume linked to application should fail"""
        # Upload a resume
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        resume_id = upload_response.json()["id"]
        
        # Create a fake application and link
        from sqlalchemy import text
        # Get user_id
        user_result = db.execute(
            text("SELECT id FROM users WHERE email = 'test@example.com'")
        ).first()
        
        if not user_result:
            # Create test user
            user_id = str(uuid.uuid4())  # Convert to string for SQLite
            db.execute(
                text("INSERT INTO users (id, email, created_at) VALUES (:id, :email, :created_at)"),
                {"id": user_id, "email": "test@example.com", "created_at": datetime.now(timezone.utc)}
            )
            db.commit()
        else:
            user_id = str(user_result[0])  # Ensure string for SQLite
        
        # Create fake application
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
        
        # Link resume to application
        link = ApplicationResume(
            id=str(uuid.uuid4()),  # Convert to string for SQLite
            application_id=app_id,
            resume_id=resume_id,  # Already a string from API response
        )
        db.add(link)
        db.commit()
        
        # Try to delete - should fail
        response = client.delete(f"/resumes/{resume_id}")
        
        assert response.status_code == 400
        assert "linked" in response.json()["detail"].lower()


class TestApplicationResumeLinking:
    """Test linking resumes to applications"""
    
    def test_link_resume_to_application(self, client, db, sample_pdf_content):
        """Test linking resume to application"""
        # Upload a resume
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        resume_id = upload_response.json()["id"]
        
        # Create test application
        from sqlalchemy import text
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
        
        # Link resume
        response = client.post(f"/applications/{app_id}/resume/{resume_id}")
        
        assert response.status_code == 201
        assert "success" in response.json()["message"].lower()
        
        # Get application resume
        get_response = client.get(f"/applications/{app_id}/resume")
        assert get_response.status_code == 200
        assert get_response.json()["resume"]["id"] == resume_id
    
    def test_get_application_resume_not_linked(self, client, db):
        """Test getting resume for application with no resume linked"""
        # Create test application
        from sqlalchemy import text
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
        
        # Get application resume
        response = client.get(f"/applications/{app_id}/resume")
        
        assert response.status_code == 200
        assert response.json()["resume"] is None


class TestDefaultResume:
    """Test default resume functionality"""
    
    def test_get_default_resume(self, client, sample_pdf_content):
        """Test getting default resume"""
        # Upload and set as default
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        resume_id = upload_response.json()["id"]
        
        client.post(f"/resumes/{resume_id}/set-default")
        
        # Get default
        response = client.get("/resumes/default")
        
        assert response.status_code == 200
        assert response.json()["resume"]["id"] == resume_id
    
    def test_get_default_resume_none_set(self, client):
        """Test getting default when none is set"""
        response = client.get("/resumes/default")
        
        assert response.status_code == 200
        assert response.json()["resume"] is None


class TestResumeDownload:
    """Test resume download and preview"""
    
    def test_download_resume(self, client, sample_pdf_content):
        """Test downloading a resume"""
        # Upload a resume
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        resume_id = upload_response.json()["id"]
        
        # Download
        response = client.get(f"/resumes/{resume_id}/download")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert len(response.content) > 0
    
    def test_preview_resume(self, client, sample_pdf_content):
        """Test previewing a resume"""
        # Upload a resume
        files = {"file": ("resume.pdf", sample_pdf_content, "application/pdf")}
        upload_response = client.post("/resumes/upload", files=files)
        resume_id = upload_response.json()["id"]
        
        # Preview
        response = client.get(f"/resumes/{resume_id}/preview")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "inline" in response.headers["content-disposition"]
        assert len(response.content) > 0
