from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.models import User, RefreshToken, GmailConnection
from typing import Optional, Union
from datetime import datetime
import uuid
import json


class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.db.query(User).filter(User.email == email).first()
    
    def get_by_id(self, user_id: Union[str, uuid.UUID]) -> Optional[User]:
        """Get user by ID (accepts string or UUID)."""
        user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id
        return self.db.query(User).filter(User.id == user_id_str).first()
    
    def create_user(self, email: str, password_hash: str, role: str = "viewer", full_name: str | None = None) -> User:
        """Create a new user."""
        user = User(email=email, password_hash=password_hash, role=role, full_name=full_name)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_user_count(self) -> int:
        """Get total number of users (for first-user detection)."""
        return self.db.query(User).count()
    
    def update_user(self, user: User) -> User:
        """Update user."""
        self.db.commit()
        self.db.refresh(user)
        return user


class RefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create_token(self, user_id: Union[str, uuid.UUID], token: str, expires_at: datetime) -> RefreshToken:
        """Create a new refresh token."""
        user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id
        refresh_token = RefreshToken(
            user_id=user_id_str,
            token=token,
            expires_at=expires_at
        )
        self.db.add(refresh_token)
        self.db.commit()
        self.db.refresh(refresh_token)
        return refresh_token
    
    def get_valid_token(self, token: str) -> Optional[RefreshToken]:
        """Get a valid (non-revoked, non-expired) refresh token."""
        now = datetime.utcnow()
        return self.db.query(RefreshToken).filter(
            and_(
                RefreshToken.token == token,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > now
            )
        ).first()
    
    def revoke_token(self, token: str) -> bool:
        """Revoke a refresh token."""
        refresh_token = self.db.query(RefreshToken).filter(RefreshToken.token == token).first()
        if refresh_token:
            refresh_token.revoked = True
            self.db.commit()
            return True
        return False
    
    def revoke_all_user_tokens(self, user_id: Union[str, uuid.UUID]):
        """Revoke all refresh tokens for a user."""
        user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id
        self.db.query(RefreshToken).filter(
            and_(
                RefreshToken.user_id == user_id_str,
                RefreshToken.revoked == False
            )
        ).update({"revoked": True})
        self.db.commit()
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens (maintenance task)."""
        now = datetime.utcnow()
        self.db.query(RefreshToken).filter(RefreshToken.expires_at < now).delete()
        self.db.commit()


class GmailConnectionRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_user_id(self, user_id: Union[str, uuid.UUID]) -> Optional[GmailConnection]:
        """Get Gmail connection for a user."""
        user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id
        return self.db.query(GmailConnection).filter(
            and_(
                GmailConnection.user_id == user_id_str,
                GmailConnection.is_active == True
            )
        ).first()
    
    def create_or_update_connection(
        self, 
        user_id: Union[str, uuid.UUID], 
        tokens_json: str, 
        gmail_email: str
    ) -> GmailConnection:
        """Create or update Gmail connection for a user."""
        user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id
        
        # Check if connection exists
        connection = self.db.query(GmailConnection).filter(
            GmailConnection.user_id == user_id_str
        ).first()
        
        if connection:
            # Update existing connection
            connection.tokens = tokens_json
            connection.gmail_email = gmail_email
            connection.is_active = True
            connection.connected_at = datetime.utcnow()
            connection.revoked_at = None
        else:
            # Create new connection
            connection = GmailConnection(
                user_id=user_id_str,
                tokens=tokens_json,
                gmail_email=gmail_email,
                is_active=True
            )
            self.db.add(connection)
        
        self.db.commit()
        self.db.refresh(connection)
        return connection
    
    def revoke_connection(self, user_id: Union[str, uuid.UUID]) -> bool:
        """Revoke (disconnect) Gmail connection for a user."""
        user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id
        connection = self.db.query(GmailConnection).filter(
            GmailConnection.user_id == user_id_str
        ).first()
        
        if connection:
            connection.is_active = False
            connection.revoked_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
    
    def get_connection_tokens(self, user_id: Union[str, uuid.UUID]) -> Optional[dict]:
        """Get OAuth tokens for a user's Gmail connection."""
        connection = self.get_by_user_id(user_id)
        if connection:
            try:
                return json.loads(connection.tokens)
            except json.JSONDecodeError:
                return None
        return None
