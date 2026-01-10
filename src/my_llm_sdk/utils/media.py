"""
Media utilities for multimodal content persistence and metadata extraction.

This module handles:
- Downloading media from URLs
- Saving Base64/bytes to local files
- Parsing audio duration from WAV/MP3 headers
"""

import os
import io
import base64
import hashlib
import tempfile
import struct
from typing import Optional, Union, Dict, Any
from pathlib import Path
import urllib.request
import urllib.error

# Try to import optional audio parsing libraries
try:
    import wave
    HAS_WAVE = True
except ImportError:
    HAS_WAVE = False

try:
    from mutagen.mp3 import MP3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


def _generate_filename(data: bytes, mime_type: str, prefix: str = "media") -> str:
    """Generate a unique filename based on content hash."""
    sha1 = hashlib.sha1(data).hexdigest()[:12]
    ext = _mime_to_extension(mime_type)
    return f"{prefix}_{sha1}.{ext}"


def _mime_to_extension(mime_type: str) -> str:
    """Convert MIME type to file extension."""
    mapping = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/wave": "wav",
        "audio/mp3": "mp3",
        "audio/mpeg": "mp3",
        "audio/ogg": "ogg",
        "video/mp4": "mp4",
        "video/webm": "webm",
    }
    return mapping.get(mime_type.lower(), "bin")


def download_url(url: str, save_dir: str, timeout: int = 30) -> str:
    """
    Download a file from URL and save to local directory.
    
    Args:
        url: HTTP/HTTPS URL to download
        save_dir: Directory to save the file
        timeout: Request timeout in seconds
        
    Returns:
        Absolute path to the saved file
    """
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            
            # Extract base MIME type (remove charset etc.)
            mime_type = content_type.split(";")[0].strip()
            
            filename = _generate_filename(data, mime_type, "download")
            filepath = os.path.join(save_dir, filename)
            
            with open(filepath, "wb") as f:
                f.write(data)
                
            return filepath
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to download URL: {url} - {e}")


def save_artifact(
    data: Union[bytes, str],
    mime_type: str,
    save_dir: Optional[str] = None,
    filename_prefix: str = "artifact"
) -> str:
    """
    Save binary data or Base64 string to a local file.
    
    Args:
        data: Raw bytes or Base64-encoded string
        mime_type: MIME type of the content
        save_dir: Directory to save (uses temp dir if None)
        filename_prefix: Prefix for generated filename
        
    Returns:
        Absolute path to the saved file
    """
    # Decode Base64 if string
    if isinstance(data, str):
        # Handle data URI format: data:image/png;base64,xxxxx
        if data.startswith("data:"):
            # Extract base64 part
            parts = data.split(",", 1)
            if len(parts) == 2:
                data = parts[1]
        data = base64.b64decode(data)
    
    # Use temp directory if not specified
    if save_dir is None:
        save_dir = tempfile.gettempdir()
    
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    
    filename = _generate_filename(data, mime_type, filename_prefix)
    filepath = os.path.join(save_dir, filename)
    
    with open(filepath, "wb") as f:
        f.write(data)
        
    return filepath


def parse_audio_duration(filepath: str) -> Optional[float]:
    """
    Parse audio file and return duration in seconds.
    
    Supports:
    - WAV (native Python)
    - MP3 (requires mutagen)
    
    Args:
        filepath: Path to audio file
        
    Returns:
        Duration in seconds, or None if unable to parse
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext in (".wav", ".wave") and HAS_WAVE:
        return _parse_wav_duration(filepath)
    elif ext == ".mp3" and HAS_MUTAGEN:
        return _parse_mp3_duration(filepath)
    elif ext == ".mp3" and not HAS_MUTAGEN:
        # Fallback: estimate from file size (128kbps assumption)
        return _estimate_mp3_duration(filepath)
    
    return None


def _parse_wav_duration(filepath: str) -> Optional[float]:
    """Parse WAV file duration using wave module."""
    try:
        with wave.open(filepath, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return frames / float(rate)
    except Exception:
        pass
    return None


def _parse_mp3_duration(filepath: str) -> Optional[float]:
    """Parse MP3 file duration using mutagen."""
    try:
        audio = MP3(filepath)
        return audio.info.length
    except Exception:
        pass
    return None


def _estimate_mp3_duration(filepath: str) -> Optional[float]:
    """Estimate MP3 duration from file size (128kbps assumption)."""
    try:
        size_bytes = os.path.getsize(filepath)
        # 128kbps = 16000 bytes/sec
        return size_bytes / 16000.0
    except Exception:
        pass
    return None


def get_media_metadata(filepath: str, mime_type: str) -> Dict[str, Any]:
    """
    Extract metadata from a media file.
    
    Args:
        filepath: Path to the file
        mime_type: MIME type of the content
        
    Returns:
        Dictionary with metadata (duration_seconds, width, height, etc.)
    """
    metadata: Dict[str, Any] = {
        "file_size": os.path.getsize(filepath) if os.path.exists(filepath) else 0
    }
    
    # Audio metadata
    if mime_type.startswith("audio/"):
        duration = parse_audio_duration(filepath)
        if duration is not None:
            metadata["duration_seconds"] = round(duration, 2)
    
    # Image metadata (basic - could extend with PIL)
    if mime_type.startswith("image/"):
        try:
            from PIL import Image
            with Image.open(filepath) as img:
                metadata["width"] = img.width
                metadata["height"] = img.height
        except ImportError:
            pass
        except Exception:
            pass
    
    return metadata
