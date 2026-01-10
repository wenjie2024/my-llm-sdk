"""
VTT Post-Processor

Converts coarse VTT files (2-3 minute chunks) into fine-grained sentence-level VTT.
Allocates time proportionally based on character count.

Usage:
    python vtt_postprocess.py                    # Process all VTT files
    python vtt_postprocess.py <book_id>          # Process specific book
    python vtt_postprocess.py <book_id> <track>  # Process specific track
"""
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class SubtitleCue:
    start_ms: int
    end_ms: int
    text: str


def parse_vtt(vtt_path: str) -> List[SubtitleCue]:
    """Parse VTT file into cues."""
    cues = []
    
    with open(vtt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    i = 0
    
    # Skip header
    while i < len(lines) and '-->' not in lines[i]:
        i += 1
    
    while i < len(lines):
        line = lines[i].strip()
        
        if '-->' in line:
            parts = line.split('-->')
            start_ms = parse_vtt_time(parts[0].strip())
            end_ms = parse_vtt_time(parts[1].strip())
            
            # Collect text
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                if not lines[i].strip().isdigit():
                    text_lines.append(lines[i].strip())
                i += 1
            
            if text_lines:
                cues.append(SubtitleCue(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=' '.join(text_lines)
                ))
        else:
            i += 1
    
    return cues


def parse_vtt_time(time_str: str) -> int:
    """Parse VTT timestamp to milliseconds."""
    parts = time_str.split(':')
    
    if len(parts) == 3:
        hours, minutes, seconds = parts
        sec_parts = seconds.split('.')
        secs = int(sec_parts[0])
        ms = int(sec_parts[1]) if len(sec_parts) > 1 else 0
        return int(hours) * 3600000 + int(minutes) * 60000 + secs * 1000 + ms
    elif len(parts) == 2:
        minutes, seconds = parts
        sec_parts = seconds.split('.')
        secs = int(sec_parts[0])
        ms = int(sec_parts[1]) if len(sec_parts) > 1 else 0
        return int(minutes) * 60000 + secs * 1000 + ms
    
    return 0


def format_vtt_time(ms: int) -> str:
    """Format milliseconds as VTT timestamp."""
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences.
    Target: ~10-30 Chinese characters per sentence.
    """
    # First pass: split on sentence-ending punctuation
    sentences = re.split(r'(?<=[。！？])', text)
    
    result = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        
        # If too long (>40 chars), split on comma/semicolon
        if len(s) > 40:
            sub_parts = re.split(r'(?<=[，；、：])', s)
            current = ""
            for part in sub_parts:
                if len(current) + len(part) <= 35:
                    current += part
                else:
                    if current.strip():
                        result.append(current.strip())
                    current = part
            if current.strip():
                result.append(current.strip())
        else:
            result.append(s)
    
    return result


def process_vtt(input_cues: List[SubtitleCue]) -> List[SubtitleCue]:
    """Split coarse cues into fine-grained sentence-level cues."""
    fine_cues = []
    
    for cue in input_cues:
        sentences = split_into_sentences(cue.text)
        if not sentences:
            continue
        
        total_chars = sum(len(s) for s in sentences)
        if total_chars == 0:
            continue
        
        duration_ms = cue.end_ms - cue.start_ms
        current_start = cue.start_ms
        
        for sentence in sentences:
            char_ratio = len(sentence) / total_chars
            sentence_duration = int(duration_ms * char_ratio)
            sentence_end = current_start + sentence_duration
            
            fine_cues.append(SubtitleCue(
                start_ms=current_start,
                end_ms=sentence_end,
                text=sentence
            ))
            
            current_start = sentence_end
    
    return fine_cues


def write_vtt(cues: List[SubtitleCue], output_path: str):
    """Write cues to VTT file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("WEBVTT\n\n")
        
        for i, cue in enumerate(cues):
            f.write(f"{i+1}\n")
            f.write(f"{format_vtt_time(cue.start_ms)} --> {format_vtt_time(cue.end_ms)}\n")
            f.write(f"{cue.text}\n\n")


def process_file(vtt_path: str, backup: bool = True) -> bool:
    """Process a single VTT file."""
    print(f"  Processing: {vtt_path}")
    
    try:
        # Parse existing
        cues = parse_vtt(vtt_path)
        if not cues:
            print(f"    ⚠️ No cues found")
            return False
        
        original_count = len(cues)
        
        # Check if already fine-grained (avg duration < 10s)
        avg_duration = sum(c.end_ms - c.start_ms for c in cues) / len(cues)
        if avg_duration < 10000:  # < 10 seconds average
            print(f"    ✓ Already fine-grained ({original_count} cues, avg {avg_duration/1000:.1f}s)")
            return True
        
        # Backup original
        if backup:
            backup_path = vtt_path + '.bak'
            if not os.path.exists(backup_path):
                import shutil
                shutil.copy(vtt_path, backup_path)
        
        # Process
        fine_cues = process_vtt(cues)
        
        # Write
        write_vtt(fine_cues, vtt_path)
        
        print(f"    ✅ {original_count} chunks → {len(fine_cues)} sentences")
        return True
        
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return False


def main():
    # Determine subtitles directory
    script_dir = Path(__file__).parent
    subtitles_dir = script_dir / "backend" / "app" / "data" / "subtitles"
    
    if not subtitles_dir.exists():
        # Try relative to scanner
        subtitles_dir = script_dir.parent / "backend" / "app" / "data" / "subtitles"
    
    if not subtitles_dir.exists():
        print(f"❌ Subtitles directory not found: {subtitles_dir}")
        sys.exit(1)
    
    print(f"📁 Subtitles directory: {subtitles_dir}")
    
    # Parse arguments
    book_id = sys.argv[1] if len(sys.argv) > 1 else None
    track_index = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    # Find VTT files to process
    if book_id and track_index is not None:
        # Specific track
        vtt_files = [subtitles_dir / book_id / f"{track_index}.vtt"]
    elif book_id:
        # All tracks for a book
        book_dir = subtitles_dir / book_id
        if book_dir.exists():
            vtt_files = list(book_dir.glob("*.vtt"))
        else:
            print(f"❌ Book not found: {book_id}")
            sys.exit(1)
    else:
        # All VTT files
        vtt_files = list(subtitles_dir.glob("*/*.vtt"))
    
    # Filter out .bak files
    vtt_files = [f for f in vtt_files if not str(f).endswith('.bak')]
    
    if not vtt_files:
        print("ℹ️ No VTT files to process")
        return
    
    print(f"\n🔄 Processing {len(vtt_files)} VTT file(s)...\n")
    
    success = 0
    for vtt_file in sorted(vtt_files):
        if process_file(str(vtt_file)):
            success += 1
    
    print(f"\n✅ Done: {success}/{len(vtt_files)} files processed successfully")


if __name__ == "__main__":
    main()
