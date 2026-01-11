import bcrypt
import hashlib
import logging

logger = logging.getLogger(__name__)

# Bcrypt has a 72-byte limit, so we pre-hash longer passwords with SHA256
BCRYPT_MAX_PASSWORD_LENGTH = 72


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    Automatically handles passwords longer than 72 bytes by pre-hashing with SHA256.
    
    This ensures passwords of any length can be securely hashed while respecting
    bcrypt's 72-byte limitation.
    """
    password_bytes = password.encode('utf-8')
    
    # Always pre-hash passwords >= 72 bytes to avoid bcrypt's 72-byte limit
    if len(password_bytes) >= BCRYPT_MAX_PASSWORD_LENGTH:
        # SHA256 produces a 32-byte hash, hex representation is 64 chars (always < 72 bytes)
        sha256_hash = hashlib.sha256(password_bytes).hexdigest()
        logger.debug(f"Password length {len(password_bytes)} bytes meets/exceeds bcrypt limit, using SHA256 pre-hash")
        # Hash the SHA256 hex digest with bcrypt directly
        password_to_hash = sha256_hash.encode('utf-8')
    else:
        # Password fits within bcrypt's limit, hash directly
        password_to_hash = password_bytes
    
    # Use bcrypt directly to avoid passlib's initialization issues
    try:
        # Generate salt and hash password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_to_hash, salt)
        # Return as string (bcrypt hash format)
        return hashed.decode('utf-8')
    except ValueError as e:
        if "password cannot be longer than 72 bytes" in str(e):
            # Final fallback: if somehow still too long, use SHA256 and try again
            logger.warning(f"Password still too long after preprocessing, using SHA256: {e}")
            sha256_hash = hashlib.sha256(password_bytes).hexdigest()
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(sha256_hash.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    Handles both direct bcrypt hashes and pre-hashed passwords (SHA256 + bcrypt).
    
    Strategy:
    1. Try direct verification first (works for passwords < 72 bytes registered directly)
    2. Try SHA256 pre-hash verification (works for passwords >= 72 bytes registered with pre-hash)
    3. This ensures compatibility regardless of password length during registration
    """
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        
        # Strategy 1: Try direct verification (for passwords that were hashed directly)
        if len(password_bytes) < BCRYPT_MAX_PASSWORD_LENGTH:
            try:
                if bcrypt.checkpw(password_bytes, hashed_bytes):
                    return True
            except (ValueError, Exception) as e:
                logger.debug(f"Direct verification failed: {e}")
                pass
        
        # Strategy 2: Try with SHA256 pre-hash (for passwords that were pre-hashed during registration)
        # This handles the case where password >= 72 bytes was registered
        sha256_hash = hashlib.sha256(password_bytes).hexdigest()
        try:
            if bcrypt.checkpw(sha256_hash.encode('utf-8'), hashed_bytes):
                return True
        except Exception as e:
            logger.debug(f"SHA256 pre-hash verification failed: {e}")
            pass
        
        # Also try direct verification as fallback (in case password was registered as short but is now long)
        try:
            if bcrypt.checkpw(password_bytes, hashed_bytes):
                return True
        except ValueError:
            # Password too long for direct verification, already tried SHA256
            pass
        except Exception as e:
            logger.debug(f"Fallback direct verification failed: {e}")
            pass
        
        return False
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False
