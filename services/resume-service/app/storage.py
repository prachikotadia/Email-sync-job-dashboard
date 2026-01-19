"""
File Storage Abstraction for Resume Service
Supports local storage (dev) and cloud storage (S3/GCS) for production
"""
import os
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Storage configuration
STORAGE_TYPE = os.getenv("RESUME_STORAGE_TYPE", "local")  # 'local' or 's3' or 'gcs'
LOCAL_STORAGE_PATH = os.getenv("RESUME_STORAGE_PATH", "/app/storage/resumes")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_RESUME_SIZE_MB", "5"))


class StorageError(Exception):
    """Storage operation error"""
    pass


class LocalStorage:
    """Local filesystem storage (for development)"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local storage initialized at: {self.base_path}")
    
    def save_file(self, file_content: bytes, user_id: str, file_name: str) -> Tuple[str, str]:
        """
        Save file to local storage
        
        Returns:
            Tuple of (file_url, checksum)
        """
        try:
            # Create user directory
            user_dir = self.base_path / str(user_id)
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename (timestamp + original name)
            # Cross-platform safe filename generation (Windows invalid chars: < > : " | ? * \ /)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            # Remove invalid characters for Windows and Unix
            invalid_chars = '<>:"|?*\\/'
            safe_filename = "".join(c for c in file_name if c not in invalid_chars)
            # Replace spaces with underscores for better cross-platform compatibility
            safe_filename = safe_filename.replace(" ", "_")
            # Ensure filename is not empty
            if not safe_filename:
                safe_filename = "resume"
            unique_filename = f"{timestamp}_{safe_filename}"
            file_path = user_dir / unique_filename
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Calculate checksum
            checksum = hashlib.sha256(file_content).hexdigest()
            
            # Return relative path as URL (for local storage)
            file_url = f"local://{user_id}/{unique_filename}"
            
            logger.info(f"File saved: {file_url} (size: {len(file_content)} bytes)")
            return file_url, checksum
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise StorageError(f"Failed to save file: {str(e)}")
    
    def get_file(self, file_url: str) -> bytes:
        """Retrieve file from local storage"""
        try:
            # Parse local:// URL
            if not file_url.startswith("local://"):
                raise StorageError(f"Invalid local storage URL: {file_url}")
            
            path_parts = file_url.replace("local://", "").split("/", 1)
            if len(path_parts) != 2:
                raise StorageError(f"Invalid local storage URL format: {file_url}")
            
            user_id, filename = path_parts
            file_path = self.base_path / user_id / filename
            
            if not file_path.exists():
                raise StorageError(f"File not found: {file_url}")
            
            with open(file_path, 'rb') as f:
                return f.read()
        
        except Exception as e:
            logger.error(f"Error retrieving file {file_url}: {e}")
            raise StorageError(f"Failed to retrieve file: {str(e)}")
    
    def delete_file(self, file_url: str) -> bool:
        """Delete file from local storage"""
        try:
            if not file_url.startswith("local://"):
                return False
            
            path_parts = file_url.replace("local://", "").split("/", 1)
            if len(path_parts) != 2:
                return False
            
            user_id, filename = path_parts
            file_path = self.base_path / user_id / filename
            
            if file_path.exists():
                file_path.unlink()
                logger.info(f"File deleted: {file_url}")
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error deleting file {file_url}: {e}")
            return False


class CloudStorage:
    """Cloud storage abstraction (S3/GCS) - Placeholder for future implementation"""
    
    def __init__(self, storage_type: str):
        self.storage_type = storage_type
        raise NotImplementedError(f"Cloud storage ({storage_type}) not yet implemented")
    
    def save_file(self, file_content: bytes, user_id: str, file_name: str) -> Tuple[str, str]:
        raise NotImplementedError
    
    def get_file(self, file_url: str) -> bytes:
        raise NotImplementedError
    
    def delete_file(self, file_url: str) -> bool:
        raise NotImplementedError


def get_storage():
    """Get storage instance based on configuration"""
    if STORAGE_TYPE == "local":
        return LocalStorage(LOCAL_STORAGE_PATH)
    elif STORAGE_TYPE in ("s3", "gcs"):
        return CloudStorage(STORAGE_TYPE)
    else:
        raise ValueError(f"Unknown storage type: {STORAGE_TYPE}")


def validate_file(file_content: bytes, filename: str) -> Tuple[str, int]:
    """
    Validate uploaded file
    
    Returns:
        Tuple of (file_type, file_size_kb)
    
    Raises:
        StorageError if validation fails
    """
    # Check file size
    file_size_mb = len(file_content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise StorageError(f"File size ({file_size_mb:.2f}MB) exceeds maximum ({MAX_FILE_SIZE_MB}MB)")
    
    # Check file type
    file_type = None
    if filename.lower().endswith('.pdf'):
        file_type = 'pdf'
        # Basic PDF validation (check magic bytes)
        if not file_content.startswith(b'%PDF'):
            raise StorageError("Invalid PDF file")
    elif filename.lower().endswith('.docx'):
        file_type = 'docx'
        # Basic DOCX validation (check magic bytes - ZIP format)
        if not file_content.startswith(b'PK\x03\x04'):
            raise StorageError("Invalid DOCX file")
    else:
        raise StorageError("Only PDF and DOCX files are supported")
    
    file_size_kb = len(file_content) // 1024
    
    return file_type, file_size_kb
