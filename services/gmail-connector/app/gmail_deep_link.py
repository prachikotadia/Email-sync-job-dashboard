"""
Gmail Deep Link Builder - Single Source of Truth
Generates permanent, cross-device Gmail deep links using message ID.
"""


def build_gmail_deep_link(message_id: str) -> str:
    """
    Build a permanent Gmail deep link using message ID.
    
    Format: https://mail.google.com/mail/u/0/#all/{message_id}
    
    This format is more robust than #inbox as it works even if:
    - Message is archived
    - Message is in a different label
    - User switches accounts
    
    Rules:
    - message_id MUST come from Gmail API (message.id field)
    - Link is deterministic and reproducible
    - Works cross-device, cross-browser
    - Does NOT require session state
    
    Args:
        message_id: Gmail message ID from API (e.g., "18c1234567890abcdef")
    
    Returns:
        Permanent Gmail deep link URL
    
    Raises:
        ValueError: If message_id is empty or None
    """
    if not message_id or not isinstance(message_id, str) or not message_id.strip():
        raise ValueError("message_id is required and cannot be empty")
    
    # Use #all format (more robust than #inbox)
    # This works even if message is archived or in different label
    return f"https://mail.google.com/mail/u/0/#all/{message_id.strip()}"


def is_valid_gmail_message_id(message_id: str) -> bool:
    """
    Validate that message_id looks like a valid Gmail message ID.
    
    Gmail message IDs are typically alphanumeric strings.
    This is a basic validation - the real validation is that it comes from Gmail API.
    
    Args:
        message_id: Message ID to validate
    
    Returns:
        True if message_id appears valid, False otherwise
    """
    if not message_id or not isinstance(message_id, str):
        return False
    
    # Gmail message IDs are typically alphanumeric (may include some special chars)
    # Basic check: non-empty, reasonable length
    trimmed = message_id.strip()
    if not trimmed or len(trimmed) < 5 or len(trimmed) > 200:
        return False
    
    return True
