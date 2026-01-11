from typing import Literal
from app.schemas.user import UserRole

Role = Literal["viewer", "editor"]


def has_permission(role: UserRole, method: str) -> bool:
    """
    Check if a role has permission for an HTTP method.
    - viewer: GET only
    - editor: GET, POST, PATCH, PUT, DELETE
    """
    if role == "editor":
        return True
    
    if role == "viewer":
        return method.upper() == "GET"
    
    return False
