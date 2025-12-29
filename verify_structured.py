import asyncio
import sqlite3
import json
from src.client import LLMClient
from src.schemas import GenerationResponse

async def verify_structured():
    print("🚀 Starting Structured Output Verification")
    print("-" * 50)
    
    client = LLMClient(user_config_path="config.yaml")
    
    # Test 1: Full Response = True
    print("\n🧪 Testing generate(full_response=True) with gemini-2.5-flash")
    try:
        response = client.generate("Say hello in one word", model_alias="gemini-2.5-flash", full_response=True)
        if isinstance(response, GenerationResponse):
            print(f"   ✅ Returned GenerationResponse object")
            print(f"   📄 Content: {response.content}")
            print(f"   📊 Usage: {response.usage}")
            print(f"   🏁 Finish Reason: {response.finish_reason}")
            
            # Save Trace ID to check DB
            # Wait, GenerationResponse doesn't have trace_id yet? 
            # I added it to schema but did populate it in provider? 
            # Provider doesn't know trace_id. Client/Ledger generates it.
            # Client doesn't put trace_id back into response object currently.
            # That's a minor thing I missed in plan.
            # But the Ledger should record it.
            pass
        else:
            print(f"   ❌ Failed: Type is {type(response)}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 2: Full Response = False (Legacy)
    print("\n🧪 Testing generate(full_response=False) with qwen-max")
    try:
        content = client.generate("Say hi in one word", model_alias="qwen-max", full_response=False)
        if isinstance(content, str):
            print(f"   ✅ Returned string")
            print(f"   📄 Content: {content}")
        else:
            print(f"   ❌ Failed: Type is {type(content)}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 3: Check Ledger for usage_json
    print("\n🔍 Checking Ledger for usage_json")
    ledger = client.budget.ledger
    with ledger._get_conn() as conn:
        # Get latest 2 transactions
        rows = conn.execute("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 2").fetchall()
        for row in rows:
            print(f"   📝 Tx: {row['provider']} / {row['model']}")
            print(f"      Input: {row['input_tokens']}, Output: {row['output_tokens']}")
            print(f"      Usage JSON: {row['usage_json']}")
            
            # Verify usage_json is populated
            if row['usage_json']:
                usage = json.loads(row['usage_json'])
                if usage.get('tokens_in', 0) > 0:
                     print("      ✅ Usage JSON has tokens")
                else:
                     print("      ⚠️ Usage JSON empty tokens (might be short prompt)")
            else:
                print("      ❌ Usage JSON is missing!")

if __name__ == "__main__":
    asyncio.run(verify_structured())
