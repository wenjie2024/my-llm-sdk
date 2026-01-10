import os
import sys
import dashscope
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration Constants ---
DEFAULT_DASHSCOPE_INTL_URL = "https://dashscope-intl.aliyuncs.com/api/v1"
# For OpenAI-compatible client
DEFAULT_DASHSCOPE_COMPATIBLE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

class HostConfig:
    @staticmethod
    def get_dashscope_api_key():
        return os.getenv("DASHSCOPE_API_KEY")

    @staticmethod
    def get_gemini_api_key():
        return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    @staticmethod
    def init_dashscope():
        """
        Initialize DashScope SDK with correct Region configuration.
        Should be called at the start of any script using dashscope.
        """
        api_key = HostConfig.get_dashscope_api_key()
        if not api_key:
            logger.warning("DASHSCOPE_API_KEY not found in environment.")
            return

        dashscope.api_key = api_key
        
        # Heuristic: Assume International config is preferred based on recent debugging
        # In a more complex setup, we might toggle this based on a separate env var.
        dashscope.base_http_api_url = DEFAULT_DASHSCOPE_INTL_URL
        
        logger.debug(f"DashScope initialized (URL: {dashscope.base_http_api_url})")

    @staticmethod
    def get_openai_base_url():
        """
        Returns the OpenAI-compatible base URL for Qwen/DashScope.
        """
        # Currently hardcoded to International as per fix
        return DEFAULT_DASHSCOPE_COMPATIBLE_URL

# Auto-initialize on import? 
# Better to be explicit in scripts, but for 'host' package convenience, maybe valid?
# Let's keep it explicit: users call host.config.init_dashscope() or similar.
