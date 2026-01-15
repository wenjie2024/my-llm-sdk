import httpx
import logging
import os
from contextlib import contextmanager

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


@contextmanager
def bypass_proxy():
    """
    临时清除代理环境变量，确保直连。
    用于国内 LLM Provider (Qwen/DashScope, Volcengine/Doubao 等) 绕过 VPN 代理。
    
    Usage:
        with bypass_proxy():
            response = dashscope.Generation.call(...)
    """
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
    saved = {}
    
    # 保存并清除代理环境变量
    for key in proxy_vars:
        if key in os.environ:
            saved[key] = os.environ.pop(key)
    
    try:
        yield
    finally:
        # 恢复原有代理设置
        os.environ.update(saved)
