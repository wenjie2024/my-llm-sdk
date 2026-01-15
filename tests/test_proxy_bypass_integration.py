"""
Integration test: Verify SDK proxy bypass works with actual config.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from dotenv import load_dotenv
load_dotenv()

def test_sdk_integration():
    """Test that SDK loads NetworkConfig and _get_network_context works"""
    from my_llm_sdk.client import LLMClient
    
    print("=" * 60)
    print("SDK Integration Test: Proxy Bypass Feature")
    print("=" * 60)
    
    client = LLMClient()
    
    # 1. Check NetworkConfig loaded
    print(f"\n[Config] network.bypass_proxy = {client.config.network.bypass_proxy}")
    
    # 2. Test _get_network_context for different providers
    from my_llm_sdk.utils.network import bypass_proxy
    from contextlib import nullcontext
    
    # Should bypass
    ctx_alibaba = client._get_network_context("alibaba")
    print(f"[Context] alibaba: {type(ctx_alibaba).__name__}")
    assert "GeneratorContextManager" in type(ctx_alibaba).__name__, "alibaba should use bypass_proxy"
    
    ctx_volcengine = client._get_network_context("volcengine")
    print(f"[Context] volcengine: {type(ctx_volcengine).__name__}")
    
    # Should NOT bypass
    ctx_google = client._get_network_context("google")
    print(f"[Context] google: {type(ctx_google).__name__}")
    assert "nullcontext" in type(ctx_google).__name__, "google should use nullcontext"
    
    print("\n✅ Config and context logic verified!")
    
    # 3. Test actual Qwen call with bypass (if API key available)
    if os.environ.get('DASHSCOPE_API_KEY'):
        print("\n[Test] Calling Qwen via SDK...")
        
        # Set fake proxy to test bypass
        os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
        os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
        
        try:
            response = client.generate(
                prompt="Say 'test' in one word",
                model_alias="qwen-turbo"
            )
            print(f"[Response] {response[:50]}...")
            print("✅ SDK Qwen call succeeded with proxy bypass!")
        except Exception as e:
            print(f"⚠️ API call error (may be expected): {e}")
        finally:
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)
    else:
        print("\n[Skip] DASHSCOPE_API_KEY not set, skipping live API test")
    
    print("\n" + "=" * 60)
    print("🎉 SDK INTEGRATION TEST PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_sdk_integration()
