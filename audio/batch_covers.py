import sqlite3
import os
import yaml
import sys
import logging

# Add scanner to path to import LLMClient
sys.path.append(os.path.join(os.getcwd(), "scanner"))
from llm_client import LLMClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_path="scanner/config.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def batch_generate():
    config = load_config()
    media_root = config.get("media_root")
    db_path = config.get("db_path", "backend/app/data/books.db")

    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    # Init LLM
    llm = LLMClient()
    if not llm.enabled:
        print("❌ LLM not enabled. Check API Key.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get 5 books
    print("📚 Fetching first 5 books...")
    cursor.execute("SELECT title, summary, folder_path, isbn FROM books LIMIT 5")
    rows = cursor.fetchall()
    
    if not rows:
        print("No books found in DB.")
        return

    for i, row in enumerate(rows):
        title = row[0] or "Unknown"
        summary = row[1] or "A children's story."
        folder_path = row[2]
        isbn = row[3] or ""
        
        print(f"\n[{i+1}/5] Processing: {title}")
        
        # Check folder exists
        full_folder_path = os.path.join(media_root, folder_path)
        if not os.path.exists(full_folder_path):
            print(f"  ⚠️ Folder not found: {full_folder_path}")
            continue

        target_file = os.path.join(full_folder_path, "cover_ai.png")
        
        # Build Prompt
        prompt = f"A book cover for children's audio story: {title}. Style: Nano Baanana, cute, vibrant, high quality illustration. Context: {summary[:200]}."
        if isbn:
            prompt += f" Reference ID: {isbn}."
        
        print(f"  🎨 Generating cover...")
        try:
            success = llm.generate_cover_image(prompt, target_file)
            if success:
                print(f"  ✅ Saved to: {target_file}")
            else:
                print(f"  ❌ Generation failed.")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    conn.close()
    print("\n✨ Batch generation complete!")

if __name__ == "__main__":
    batch_generate()
