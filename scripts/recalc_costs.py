import os
import sys
from datetime import datetime, timezone
from my_llm_sdk.config.loader import load_config
from my_llm_sdk.budget.ledger import Ledger
from my_llm_sdk.budget.pricing import calculate_actual_cost
from my_llm_sdk.schemas import TokenUsage

def recalc_today():
    print("=== Recalculating Today's Spend based on New Pricing ===")
    
    # 1. Load Config (to get new prices)
    # We need to find the project root or specify path. Assuming run from root.
    config = load_config(project_path="llm.project.yaml")
    
    ledger = Ledger()
    
    # 2. Define "Today" (UTC or Local? Ledger.get_daily_spend uses UTC day)
    # Let's align with Ledger.get_daily_spend logic:
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    
    print(f"Time range: >= {datetime.fromtimestamp(start_of_day, timezone.utc)}")

    with ledger._get_conn() as conn:
        # 3. Fetch Transactions
        rows = conn.execute("""
            SELECT id, model, input_tokens, output_tokens, cost, provider 
            FROM transactions 
            WHERE timestamp >= ?
        """, (start_of_day,)).fetchall()
        
        if not rows:
            print("No transactions found for today.")
            return

        total_old = 0.0
        total_new = 0.0
        updates = []

        print(f"\nFound {len(rows)} transactions. Processing...")
        print(f"{'Model':<25} | {'Old Cost':<10} | {'New Cost':<10} | {'Diff':<10}")
        print("-" * 65)

        for row in rows:
            tx_id = row['id']
            model_id = row['model']
            old_cost = row['cost']
            
            usage = TokenUsage(
                input_tokens=row['input_tokens'], 
                output_tokens=row['output_tokens'],
                total_tokens=row['input_tokens'] + row['output_tokens']
            )
            
            # Recalculate using helper (which looks up config)
            new_cost = calculate_actual_cost(model_id, usage, config)
            
            total_old += old_cost
            total_new += new_cost
            
            if abs(new_cost - old_cost) > 0.000001:
                updates.append((new_cost, tx_id))
                print(f"{model_id:<25} | ${old_cost:<9.4f} | ${new_cost:<9.4f} | {new_cost-old_cost:+.4f}")
        
        print("-" * 65)
        print(f"Total Old: ${total_old:.4f}")
        print(f"Total New: ${total_new:.4f}")
        print(f"Change:    ${total_new - total_old:+.4f}")

        # 4. Commit Updates
        if updates:
            print(f"\nUpdating {len(updates)} transactions in DB...")
            conn.executemany("UPDATE transactions SET cost=? WHERE id=?", updates)
            conn.commit()
            print("✅ Transactions updated.")
            
            # 5. Rebuild Reports
            print("Rebuilding request_facts...")
            # We can call rebuild_facts on ledger instance, but we need to close our conn first 
            # or use the instance method if it manages its own conn?
            # Ledger.rebuild_facts() opens its own connection. 
            # Since we are in `with ledger._get_conn()`, we hold a connection.
            # SQLite WAL handles concurrency, but same thread re-entry might be tricky if not careful.
            # Better to close this conn then call rebuild.
    
    # Verify outside the block (conn closed)
    if updates:
        ledger.rebuild_facts()
        print("✅ Reports rebuilt.")

if __name__ == "__main__":
    recalc_today()
