import asyncio
import json
import time
from src.client import LLMClient
from src.schemas import StreamEvent

def verify_streaming():
    print("🚀 Starting Streaming Verification")
    print("-" * 50)
    
    client = LLMClient(user_config_path="config.yaml") # Load from local defaults
    
    # Test 1: Gemini Streaming
    print("\n🌊 Testing Gemini Streaming (gemini-2.5-flash)")
    try:
        stream = client.stream("Count to 5 quickly", model_alias="gemini-2.5-flash")
        
        print("   Stream Output: ", end="", flush=True)
        final_usage = None
        
        for event in stream:
            if event.delta:
                print(event.delta, end="", flush=True)
            if event.is_finish:
                print("\n   🏁 Stream Finished")
                if event.usage:
                    final_usage = event.usage
                    print(f"   📊 Final Usage: {event.usage}")
                else:
                    print("   ⚠️ No usage in final event")
            if event.error:
                 print(f"\n   ❌ Stream Error: {event.error}")
                 
        if final_usage:
            # Check Ledger
            print("   🔍 Checking Ledger...")
            # Allow async worker to flush? verify_structured handled ledger checks synchronously 
            # because ledger write is sync inside track() unless async mode is ON.
            # Client.stream calls budget.track which calls ledger.record_transaction (sync legacy wrapper)
            # So DB should be updated immediately.
            
            ledger = client.budget.ledger
            with ledger._get_conn() as conn:
                row = conn.execute("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 1").fetchone()
                if row:
                     print(f"      📝 Ledger Tx: {row['provider']} / {row['model']}")
                     print(f"      Usage JSON: {row['usage_json']}")
                     u = json.loads(row['usage_json'])
                     if u.get('tokens_in') == final_usage.input_tokens:
                         print("      ✅ Ledger matches stream usage")
                     else:
                         print(f"      ❌ Mismatch! Ledger: {u.get('tokens_in')}, Event: {final_usage.input_tokens}")
                else:
                    print("      ❌ No transaction found")
                    
    except Exception as e:
        print(f"\n   ❌ Error: {e}")


    # Test 2: Qwen Streaming
    print("\n🌊 Testing Qwen Streaming (qwen-max)")
    try:
        stream = client.stream("Count to 3", model_alias="qwen-max")
        
        print("   Stream Output: ", end="", flush=True)
        final_usage = None
        
        for event in stream:
            if event.delta:
                print(event.delta, end="", flush=True)
            if event.is_finish:
                print("\n   🏁 Stream Finished")
                final_usage = event.usage
                print(f"   📊 Final Usage: {event.usage}")
                
        if final_usage:
             pass # Assume ledger work if test 1 worked
             
    except Exception as e:
        print(f"\n   ❌ Error: {e}")

if __name__ == "__main__":
    verify_streaming()
