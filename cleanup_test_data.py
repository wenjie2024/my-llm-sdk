from my_llm_sdk.budget.ledger import Ledger
from pathlib import Path

def cleanup():
    print("=== Cleaning up Test Data ===")
    ledger = Ledger() # Uses ~/.llm-sdk/ledger.db by default
    
    with ledger._get_conn() as conn:
        # 1. Count items to delete
        rows = conn.execute("SELECT COUNT(*), SUM(cost) FROM transactions WHERE model='test-model'").fetchone()
        count = rows[0]
        cost = rows[1] or 0.0
        
        print(f"Found {count} test transactions totaling ${cost:.4f}")
        
        if count == 0:
            print("No test data found. Everything looks clean.")
            return

        # 2. Delete from Transactions
        print("Deleting from transactions...")
        conn.execute("DELETE FROM transactions WHERE model='test-model'")
        
        # 3. Delete from Request Facts
        print("Deleting from request_facts...")
        conn.execute("DELETE FROM request_facts WHERE model='test-model'")
        
        conn.commit()
        
    print(f"✅ Cleanup Complete. Removed ${cost:.4f} of test spending.")
    print("Current budget status should be normal now.")

if __name__ == "__main__":
    cleanup()
