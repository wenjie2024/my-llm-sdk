import httpx
import logging

logger = logging.getLogger(__name__)

def can_connect_to_google(timeout: float = 1.0) -> bool:
    """
    Check if Google is accessible to determine network environment.
    """
    try:
        # Use a HEAD request to be lightweight
        httpx.head("https://www.google.com", timeout=timeout)
        return True
    except Exception:
        return False
