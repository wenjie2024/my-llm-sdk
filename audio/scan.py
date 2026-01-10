import argparse
import yaml
import os
import sys
import uuid
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from host.llm import LLMClient
from host.config import HostConfig
from .cover_fetcher import CoverFetcher
from host.transcription.asr_client import ASRClient
import click
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s') # Changed to WARNING
# Suppress noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Add backend to path to import models
# host/scanner/main.py -> host/scanner -> host -> root
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend"))
from app.models import Base, LibraryBase, Book, Track, AudioRendition

def load_config(config_path="config.yaml"):
    # Resolve relative to script dir if not absolute
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.path.dirname(__file__), config_path)
        
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_db_session(db_path):
    url = f"sqlite:///{db_path}"
    print(f"Connecting to DB: {url}")
    engine = create_engine(url)
    LibraryBase.metadata.create_all(engine) # Ensure Library tables exist
    
    # Simple Migration: Add grade column if not exists
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE books ADD COLUMN grade VARCHAR"))
            print("✅ Added 'grade' column to books table.")
        except Exception:
            pass # Column likely exists

    Session = sessionmaker(bind=engine)
    return Session()

# ... (Keep existing imports)

# Classification Rules (Hardcoded for v1)
CLASS_A = [
    "test_book_1", "豆蔻镇的居民和强盗", "吹小号的天鹅", "尼瑙克山探险", "马小跳", 
    "小老鼠漂流记", "了不起的狐狸爸爸", "五毛钱的愿望", "电话里的童话", "淘气包埃米尔",
    "小贝流浪记", "夏日历险", "一百条裙子", "查理和巧克力工厂", "绿拇指男孩", 
    "幸福来临时", "屋顶上的小孩", "魔法师的帽子", "一只会开枪的狮子", "苹果树上的外婆",
    "小女巫", "狗来了", "长袜子皮皮", "动物大逃亡"
]
CLASS_B = [
    "夏洛的网", "外公是棵樱桃树", "桥下一家人", "人鸦", "木偶的森林", "马提和祖父", 
    "傻狗温迪克", "塔克坡地森林", "波普先生的企鹅", "浪漫鼠德佩罗", "鲁宾逊漂流记", 
    "埃米尔捕盗记", "格列佛游记", "杜立德医生航海记", "柳林风声", "我和小姐姐克拉拉", 
    "校舍上的车轮", "小铁哥们", "小王子", "洋葱头历险记", "女巫", "列那狐的故事", 
    "捣蛋鬼日记", "帅狗杜明尼克"
]
CLASS_C = [
    "风之王", "蓝色海豚岛", "山居岁月", "少年维特"
]

def classify_grade(title):
    if not title: return None
    for k in CLASS_A:
        if k in title: return 'A'
    for k in CLASS_B:
        if k in title: return 'B'
    for k in CLASS_C:
        if k in title: return 'C'
    return None # Return None if not in hardcoded lists

@click.group()
def cli():
    pass

@cli.command()
@click.option("--dry-run", is_flag=True, help="Don't write to DB")
@click.option("--profile", default="kids_zh_7", help="Content profile to use")
@click.option("--llm", is_flag=True, help="Enable LLM metadata generation")
@click.option("--provider", type=click.Choice(['auto', 'qwen', 'gemini']), default='auto', help="LLM Provider to use (default: auto)")
@click.option("--force", is_flag=True, help="Force update existing books")
@click.option("--limit", default=0, help="Limit number of books to process (0 for all)")
@click.option("--offset", default=0, help="Skip first N books (useful for resuming)")
@click.option("--asr", is_flag=True, help="Enable ASR subtitle generation")
@click.option("--name", default=None, help="Filter by book name (substring)")
def scan(dry_run, profile, llm, provider, force, limit, offset, asr, name):
    """Scan media directory and update database."""
    config = load_config()
    session = get_db_session(config["db_path"])
    
    # Load profile config
    profile_path = os.path.join(os.path.dirname(__file__), "profiles", f"{profile}.yaml")
    if not os.path.exists(profile_path):
        click.echo(f"Profile {profile} not found.")
        return
        
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_cfg = yaml.safe_load(f)

    # Init LLM Client, Cover Fetcher, and ASR Client
    llm_client = LLMClient(provider=provider) if llm else None
    cover_fetcher = CoverFetcher()
    asr_client = ASRClient() if asr else None
    
    prompt_template = ""
    prompt_grading = ""
    if llm and llm_client.enabled:
        prompt_path = os.path.join(os.path.dirname(__file__), profile_cfg.get("prompt_template", ""))
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
            
            # Load Prompt B (Expert Grading)
            base, ext = os.path.splitext(prompt_path)
            grading_path = f"{base}_grading_expert{ext}"
            if os.path.exists(grading_path):
                with open(grading_path, "r", encoding="utf-8") as f:
                    prompt_grading = f.read()
            else:
                 click.echo(f"Warning: Grading prompt not found at {grading_path}")

        else:
            click.echo(f"Warning: Prompt template not found at {prompt_path}")

    click.echo(f"Scanning {config['media_root']} with profile {profile}...")
    
    # 1. File Walker
    found_books = []
    for root, dirs, files in os.walk(config["media_root"]):
        if root == config["media_root"]:
            continue
            
        rel_path = os.path.relpath(root, config["media_root"])
        # Only process top-level folders as books for now
        if os.path.dirname(rel_path) != "":
            continue
            
        raw_folder_name = os.path.basename(root)
        
        audio_files = [f for f in files if f.lower().endswith(('.mp3', '.m4a', '.wav'))]
        audio_files.sort()
        
        if not audio_files:
            continue
            
        if name and name not in raw_folder_name:
            continue

        book_data = {
            "media_root_id": "main",
            "folder_path": rel_path,
            "raw_name": raw_folder_name,
            "title": raw_folder_name, # Default title
            "content_type": profile_cfg.get("default_content_type"),
            "target_audience": profile_cfg.get("default_target_audience"),
            "language": profile_cfg.get("language"),
            "total_tracks": len(audio_files),
            "tracks": []
        }
        
        # Sort tracks
        for idx, f in enumerate(audio_files):
            book_data["tracks"].append({
                "index": idx,
                "filename": f,
                "title": os.path.splitext(f)[0]
            })
            
        found_books.append(book_data)

    # 2. DB Sync
    # Sort books by raw_name to ensure deterministic order for offset resume
    found_books.sort(key=lambda x: x["raw_name"])
    
    if offset > 0:
        click.echo(f"Skipping first {offset} books as requested...")
        found_books = found_books[offset:]

    click.echo(f"Found {len(found_books)} books on disk (after offset).")
    
    # Use tqdm for progress bar
    pbar = tqdm(found_books, desc="Processing Books", unit="book")
    processed_count = 0
    
    for book_data in pbar:
        if limit > 0 and processed_count >= limit:
            tqdm.write(f"Limit of {limit} books reached. Stopping.")
            break
            
        pbar.set_description(f"Processing: {book_data['raw_name'][:20]}...") # Truncate for display
        processed_count += 1
        
        existing = session.query(Book).filter_by(folder_path=book_data["folder_path"]).first()
        
        if existing and not force:
             # Just skip silently or log verbose
            # tqdm.write(f"Skipping existing book: {book_data['raw_name']}")
            pbar.update(1)
            continue
        
        # Resume Logic for Force Update:
        # If forcing (trying to switch LLM), check if already updated by target provider to avoid redo.
        # We assume if extra_meta has 'age_source' containing the provider name, it's done.
        # This is a heuristic.
        if existing and force:
             # Check if we should resume (skip if already looked capable)
             # If using Gemini, and age_source says Gemini, skip.
             if provider == 'gemini' and existing.extra_meta and 'Gemini' in str(existing.extra_meta.get('age_source', '')):
                 pbar.update(1)
                 continue
             
             # Also if provider is Qwen and source says Qwen...
             if provider == 'qwen' and existing.extra_meta and 'Qwen' in str(existing.extra_meta.get('age_source', '')):
                 pbar.update(1)
                 continue

        if existing:
            # click.echo(f"UPDATE: {book_data['raw_name']}") 
            pass
        else:
            # click.echo(f"NEW: {book_data['raw_name']}")
            pass
        
        # 0. Check for Local Manual Cover FIRST (Highest Priority)
        local_cover_path = None
        manual_cover_files = [f for f in os.listdir(os.path.join(config["media_root"], book_data["folder_path"])) if f.lower() in ('cover.jpg', 'cover.png', 'folder.jpg', 'folder.png')]
        
        if manual_cover_files:
            # Found manual cover
            local_cover_path = os.path.join(book_data["folder_path"], manual_cover_files[0]).replace("\\", "/")
            book_data["cover_path"] = local_cover_path
        else:
            # 0.5 Check for Existing AI Cover (Lower Priority than manual)
            ai_cover_files = [f for f in os.listdir(os.path.join(config["media_root"], book_data["folder_path"])) if f.lower() in ('cover_ai.png', 'cover_ai.jpg')]
            if ai_cover_files:
                local_cover_path = os.path.join(book_data["folder_path"], ai_cover_files[0]).replace("\\", "/")
                # We set it, but we might arguably want to allow Google Books to override it?
                # User said: "Only when current folder has NO cover [manual], then use cover_ai".
                # It accepts cover_ai if manual is missing. 
                book_data["cover_path"] = local_cover_path

        # LLM Enrichment
        if llm_client and llm_client.enabled and prompt_template:
            meta = llm_client.generate_metadata(
                prompt_template, 
                book_data["raw_name"], 
                [t["filename"] for t in book_data["tracks"][:10]] # Send first 10 tracks
            )
            if meta:
                book_data.update({
                    "title": meta.get("title", book_data["title"]),
                    "summary": meta.get("summary"),
                    "author": meta.get("author"),
                    "tags": meta.get("tags", []),
                    "isbn": meta.get("isbn")
                })
                
                # Step 2: Expert Grading
                if prompt_grading:
                    grading_meta = llm_client.generate_grading(prompt_grading, book_data, child_age=7)
                    if grading_meta:
                        book_data.update({
                            "min_age": grading_meta.get("min_age"),
                            "grade": grading_meta.get("grade"),
                            "age_source": f"{grading_meta.get('age_source', 'AI')} ({grading_meta.get('provider', 'mixed')})",
                        })
                        # Store extra info for DB
                        book_data["extra_meta"] = {
                            "reason": grading_meta.get("reason"),
                            "age_source": f"{grading_meta.get('age_source', 'AI')} ({grading_meta.get('provider', 'mixed')})",
                            "sensitive_flags": grading_meta.get("sensitive_flags")
                        }
                        tqdm.write(f"  🧠 Graded: {book_data['grade']} (Age {book_data['min_age']}+) - {grading_meta.get('reason')[:30]}...")
                else:
                    # Legcay / Fallback
                    book_data.update({
                        "min_age": meta.get("min_age"),
                        "grade": meta.get("grade"),
                        "age_source": meta.get("age_source"),
                    })

                # Only fetch external cover if local one is missing
                if not local_cover_path:
                    # Fetch Cover from Google Books
                    cover_filename = cover_fetcher.fetch_cover(
                        title=meta.get("title"),
                        author=meta.get("author"),
                        isbn=meta.get("isbn"),
                        save_dir=os.path.join(config["media_root"], book_data["folder_path"])
                    )
                    if cover_filename:
                        book_data["cover_path"] = os.path.join(book_data["folder_path"], cover_filename).replace("\\", "/")
                    elif llm_client:
                         # AI Cover Fallback (Qwen-Image)
                         logger.info(f"Generating AI cover for {book_data['title']}...")
                         cover_filename = "cover_ai.png"
                         save_path = os.path.join(config["media_root"], book_data["folder_path"], cover_filename)
                         
                         ai_prompt = f"A book cover for children's audio story: {meta.get('title')}. Style: Nano Baanana, cute, vibrant, high quality illustration. Context: {meta.get('summary')[:100]}"
                         
                         if llm_client.generate_cover_image(ai_prompt, save_path):
                             book_data["cover_path"] = os.path.join(book_data["folder_path"], cover_filename).replace("\\", "/")

    # Classification rules moved to global scope


    # Pre-calculate grades for summary (Approximate, based on hardcoded only)
    grade_counts = {'A': 0, 'B': 0, 'C': 0}
    for b in found_books:
        # Note: at this pre-calc stage, LLM hasn't run yet, so we only count hardcoded.
        g = classify_grade(b.get("title", b["raw_name"])) or 'B' # Default B for stats if unknown
        if g in grade_counts:
            grade_counts[g] += 1
    
    click.echo(f"📊 Statistics (from manual list): Total {len(found_books)} books.")
    click.echo(f"   - Grade A: {grade_counts['A']}")
    click.echo(f"   - Grade B/C: {grade_counts['B'] + grade_counts['C']}")
    
    pbar = tqdm(found_books, desc="Processing")
    for book_data in pbar:
        # Update progress bar description
        pbar.set_description(f"Processing: {book_data.get('title', book_data['raw_name'])[:15]}...")
        
        # 1. Hardcoded Grade
        manual_grade = classify_grade(book_data.get("title", ""))
        
        # 2. LLM Grade (if available from previous loop)
        llm_grade = book_data.get("grade")
        
        # 3. Final Decision: Manual > LLM > Default B
        if manual_grade:
             current_grade = manual_grade
        elif llm_grade and llm_grade in ['A', 'B', 'C']:
             current_grade = llm_grade
        else:
             current_grade = 'B'
        
        # Check if exists in DB
        existing = session.query(Book).filter_by(media_root_id=book_data["media_root_id"], folder_path=book_data["folder_path"]).first()
        
        if existing and not force:
             tqdm.write(f"Skipping existing book: {book_data['title']}")
             continue
        
        # Match Metadata (LLM) if enabled... logic...
        # ... (lines 185-210 unchanged, omitted here for brevity)

        if not dry_run:
            if existing:
                # Update existing book (Upsert Logic: Only update if new value is valid)
                existing.title = book_data["title"] # Title always updates (it's the key usually)
                if book_data.get("summary"):
                    existing.summary = book_data.get("summary")
                if book_data.get("author"):
                    existing.author = book_data.get("author")
                if book_data.get("tags"):
                    existing.tags = book_data.get("tags")
                
                # Grade/Age might come from separate step, handled below or via Grade logic above
                # But if we got a new explicit min_age from prompt A, update it
                if book_data.get("min_age"):
                    existing.min_age = book_data.get("min_age")
                
                existing.grade = current_grade
                
                # Update extra_meta with age_source or full grading info
                if book_data.get("extra_meta"):
                    extra = dict(existing.extra_meta or {})
                    extra.update(book_data["extra_meta"])
                    existing.extra_meta = extra
                elif book_data.get("age_source"):
                    extra = dict(existing.extra_meta or {})
                    extra["age_source"] = book_data["age_source"]
                    existing.extra_meta = extra

                if book_data.get("cover_path"):
                    existing.cover_path = book_data["cover_path"]
                session.commit()
                
                # ASR Subtitle Generation for existing books
                if asr_client and asr_client.enabled:
                    # Check Grade
                    if existing.grade == 'A':
                        pass # Proceed
                    else:
                        tqdm.write(f"  ⏭️ Skipping ASR for non-Class-A book (Grade {existing.grade}): {existing.title}")
                        continue # Skip loop

                    subtitles_dir = os.path.join(config.get("data_root", config["db_path"].rsplit("/", 1)[0]), "subtitles", existing.id)
                    os.makedirs(subtitles_dir, exist_ok=True)
                    
                    # Get existing tracks
                    existing_tracks = session.query(Track).filter_by(book_id=existing.id).all()
                    
                    for track in existing_tracks:
                        audio_path = os.path.join(config["media_root"], book_data["folder_path"], track.filename)
                        vtt_path = os.path.join(subtitles_dir, f"{track.index}.vtt")

                        # Skip if already has subtitle in DB
                        if track.has_subtitle:
                            continue
                        
                        # Check if VTT file exists on disk (save API cost)
                        if os.path.exists(vtt_path):
                            tqdm.write(f"  ⏭️ Subtitle file exists for track {track.index}, skipping ASR.")
                            track.subtitle_path = f"subtitles/{existing.id}/{track.index}.vtt"
                            track.has_subtitle = True
                            continue
                        
                        tqdm.write(f"  🎙️ Generating subtitle for track {track.index}...")
                        
                        if asr_client.transcribe_to_vtt(audio_path, vtt_path):
                            track.subtitle_path = f"subtitles/{existing.id}/{track.index}.vtt"
                            track.has_subtitle = True
                    
                    session.commit()
            else:
                # Create Book
                new_book = Book(
                    id=str(uuid.uuid4()),
                    media_root_id=book_data["media_root_id"],
                    folder_path=book_data["folder_path"],
                    raw_name=book_data["raw_name"],
                    title=book_data["title"],
                    summary=book_data.get("summary"),
                    author=book_data.get("author"),
                    content_type=book_data["content_type"],
                    target_audience=book_data["target_audience"],
                    language=book_data["language"],
                    total_tracks=book_data["total_tracks"],
                    tags=book_data.get("tags"),
                    min_age=book_data.get("min_age"),
                    grade=current_grade,
                    extra_meta=book_data.get("extra_meta") if book_data.get("extra_meta") else ({"age_source": book_data.get("age_source")} if book_data.get("age_source") else None),
                    cover_path=book_data.get("cover_path")
                )
                session.add(new_book)
                session.flush() # Get ID
                
                # Check for cover image if not already set
                if not new_book.cover_path:
                    cover_files = [f for f in os.listdir(os.path.join(config["media_root"], book_data["folder_path"])) if f.lower() in ('cover.jpg', 'cover.png', 'folder.jpg', 'folder.png')]
                    if cover_files:
                        new_book.cover_path = os.path.join(book_data["folder_path"], cover_files[0])
                
                # Create Tracks
                for t in book_data["tracks"]:
                    new_track = Track(
                        id=str(uuid.uuid4()),
                        book_id=new_book.id,
                        index=t["index"],
                        filename=t["filename"],
                        title=t["title"]
                    )
                    session.add(new_track)
                    
                    # Create default rendition
                    rendition = AudioRendition(
                        id=str(uuid.uuid4()),
                        book_id=new_book.id,
                        track_id=new_track.id,
                        source_type="original",
                        media_root_id=book_data["media_root_id"],
                        relative_path=os.path.join(book_data["folder_path"], t["filename"]),
                        is_default_for_kids=True
                    )
                    session.add(rendition)
                
                session.commit()
                
                # ASR Subtitle Generation for new books
                if asr_client and asr_client.enabled:
                    # Check Grade
                    if new_book.grade == 'A':
                        subtitles_dir = os.path.join(config.get("data_root", config["db_path"].rsplit("/", 1)[0]), "subtitles", new_book.id)
                        os.makedirs(subtitles_dir, exist_ok=True)
                        
                        for t in book_data["tracks"]:
                            audio_path = os.path.join(config["media_root"], book_data["folder_path"], t["filename"])
                            vtt_path = os.path.join(subtitles_dir, f"{t['index']}.vtt")
                            
                            # Check if VTT file exists on disk
                            if os.path.exists(vtt_path):
                                tqdm.write(f"  ⏭️ Subtitle file exists for track {t['index']}, skipping ASR.")
                                track = session.query(Track).filter_by(book_id=new_book.id, index=t['index']).first()
                                if track:
                                    track.subtitle_path = f"subtitles/{new_book.id}/{t['index']}.vtt"
                                    track.has_subtitle = True
                                continue
                            
                            tqdm.write(f"  🎙️ Generating subtitle for track {t['index']}...")
                            
                            if asr_client.transcribe_to_vtt(audio_path, vtt_path):
                                # Update track in DB
                                track = session.query(Track).filter_by(book_id=new_book.id, index=t['index']).first()
                                if track:
                                    track.subtitle_path = f"subtitles/{new_book.id}/{t['index']}.vtt"
                                    track.has_subtitle = True
                    else:
                         tqdm.write(f"  ⏭️ Skipping ASR for non-Class-A book (Grade {new_book.grade}): {new_book.title}")
                    
                    session.commit()

    click.echo("Scan complete.")

if __name__ == "__main__":
    cli()
