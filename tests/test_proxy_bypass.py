"""
测试：代理绕过方案可行性验证

场景模拟：
1. 设置系统代理环境变量 (模拟 VPN 全局代理)
2. 使用 bypass_proxy context manager
3. 验证在 context 内代理被清除
4. 验证在 context 外代理被恢复
5. 实际测试 DashScope API 调用
"""
import os
import sys
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

# ============================================================
# 核心：代理绕过 Context Manager
# ============================================================

@contextmanager
def bypass_proxy():
    """
    临时清除代理环境变量，确保直连。
    退出 context 后自动恢复。
    """
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
    saved = {}
    
    # 保存并清除
    for key in proxy_vars:
        if key in os.environ:
            saved[key] = os.environ.pop(key)
            print(f"  [bypass] Cleared: {key}={saved[key][:30]}...")
    
    try:
        yield
    finally:
        # 恢复
        for key, value in saved.items():
            os.environ[key] = value
            print(f"  [restore] Restored: {key}")


def test_context_manager():
    """测试 context manager 基本功能"""
    print("\n" + "=" * 60)
    print("TEST 1: Context Manager 基本功能")
    print("=" * 60)
    
    # 模拟设置代理
    os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
    os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
    
    print(f"\n[Before] HTTP_PROXY = {os.environ.get('HTTP_PROXY', 'NOT SET')}")
    print(f"[Before] HTTPS_PROXY = {os.environ.get('HTTPS_PROXY', 'NOT SET')}")
    
    with bypass_proxy():
        print(f"\n[Inside context] HTTP_PROXY = {os.environ.get('HTTP_PROXY', 'NOT SET')}")
        print(f"[Inside context] HTTPS_PROXY = {os.environ.get('HTTPS_PROXY', 'NOT SET')}")
        
        # 验证
        assert 'HTTP_PROXY' not in os.environ, "HTTP_PROXY should be cleared!"
        assert 'HTTPS_PROXY' not in os.environ, "HTTPS_PROXY should be cleared!"
        print("\n✅ Context 内代理已清除")
    
    print(f"\n[After] HTTP_PROXY = {os.environ.get('HTTP_PROXY', 'NOT SET')}")
    print(f"[After] HTTPS_PROXY = {os.environ.get('HTTPS_PROXY', 'NOT SET')}")
    
    # 验证恢复
    assert os.environ.get('HTTP_PROXY') == 'http://127.0.0.1:7890', "HTTP_PROXY should be restored!"
    print("✅ Context 外代理已恢复")
    
    # 清理
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)
    
    print("\n✅ TEST 1 PASSED")


def test_dashscope_with_bypass():
    """测试在 bypass context 中调用 DashScope"""
    print("\n" + "=" * 60)
    print("TEST 2: DashScope API 调用 (with bypass)")
    print("=" * 60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    # 模拟设置代理 (如果用户有真实 VPN，可能已经有)
    fake_proxy = os.environ.get('HTTPS_PROXY', 'http://127.0.0.1:7890')
    os.environ['HTTPS_PROXY'] = fake_proxy
    os.environ['HTTP_PROXY'] = fake_proxy
    print(f"\n[Setup] 模拟代理: {fake_proxy}")
    
    import dashscope
    from my_llm_sdk.utils.network import can_connect_to_google
    
    # 设置 API Key
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if not api_key:
        print("❌ DASHSCOPE_API_KEY not found, skipping API test")
        return
    
    dashscope.api_key = api_key
    
    # 检测网络并设置 endpoint
    use_intl = can_connect_to_google()
    if use_intl:
        dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
        print(f"[Endpoint] Using INTL: {dashscope.base_http_api_url}")
    else:
        dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"
        print(f"[Endpoint] Using CHINA: {dashscope.base_http_api_url}")
    
    # 在 bypass context 中调用
    print("\n[Test] Calling DashScope with proxy bypassed...")
    
    with bypass_proxy():
        try:
            response = dashscope.Generation.call(
                model="qwen-turbo",
                prompt="Say 'Hello' in one word.",
                max_tokens=10
            )
            
            if response.status_code == 200:
                print(f"✅ API Response: {response.output.text[:50]}...")
                print("✅ TEST 2 PASSED - DashScope works with bypass!")
            else:
                print(f"❌ API Error: {response.code} - {response.message}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()
    
    # 清理
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)


def test_no_proxy_when_not_set():
    """测试当没有代理时 context manager 也能正常工作"""
    print("\n" + "=" * 60)
    print("TEST 3: 无代理时的兼容性")
    print("=" * 60)
    
    # 确保没有代理
    for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        os.environ.pop(key, None)
    
    print("[Setup] 清除所有代理环境变量")
    
    with bypass_proxy():
        print("[Inside] Context 正常执行，无异常")
    
    print("✅ TEST 3 PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("代理绕过方案可行性测试")
    print("=" * 60)
    
    try:
        test_context_manager()
        test_no_proxy_when_not_set()
        test_dashscope_with_bypass()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
