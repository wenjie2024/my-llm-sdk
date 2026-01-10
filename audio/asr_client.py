"""
ASR Client for Qwen3-ASR-Flash

Provides audio transcription with VTT subtitle generation.
Supports automatic chunking for long audio files (>3 minutes).
"""
import os
import base64
import time
import tempfile
import logging
from typing import List, Optional
from dataclasses import dataclass
from pydub import AudioSegment
import dashscope
from host.config import HostConfig

logger = logging.getLogger(__name__)

# Configure DashScope API
# dashscope.base_http_api_url is set by HostConfig.init_dashscope() or here if we want explicit.
# But better to use the centralized init.


# Constants
MAX_DURATION_MS = 180000  # 3 minutes max for qwen3-asr-flash
CHUNK_DURATION_MS = 120000  # 2 minutes per chunk (safe margin)


@dataclass
class SubtitleSegment:
    """A single subtitle segment with timing information."""
    start_ms: int
    end_ms: int
    text: str


class ASRClient:
    """Client for Qwen3-ASR-Flash transcription with VTT generation."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or HostConfig.get_dashscope_api_key()
        
        # Ensure SDK is initialized with correct Region
        HostConfig.init_dashscope()
        
        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY not found. ASR features will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
    
    def transcribe_audio(self, audio_path: str) -> List[SubtitleSegment]:
        """
        Transcribe audio file and return list of timed segments.
        Automatically chunks long audio files.
        """
        if not self.enabled:
            logger.warning("ASR is disabled (no API key)")
            return []
        
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return []
        
        # Load audio
        logger.info(f"Loading audio: {audio_path}")
        audio = AudioSegment.from_file(audio_path)
        duration_ms = len(audio)
        
        logger.info(f"Audio duration: {duration_ms/1000:.1f}s")
        
        # Determine chunking strategy
        if duration_ms <= MAX_DURATION_MS:
            chunks = [{"audio": audio, "start_ms": 0, "end_ms": duration_ms}]
        else:
            chunks = self._split_audio(audio, duration_ms)
        
        # Transcribe chunks in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        all_segments = []
        chunk_results = [None] * len(chunks)
        
        logger.info(f"Starting parallel transcription for {len(chunks)} chunks (max_workers=3)...")
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_index = {
                executor.submit(self._transcribe_chunk, chunk['audio']): i 
                for i, chunk in enumerate(chunks)
            }
            
            for future in as_completed(future_to_index):
                i = future_to_index[future]
                try:
                    text = future.result()
                    if text:
                        logger.info(f"Chunk {i+1}/{len(chunks)} done.")
                        chunk_results[i] = SubtitleSegment(
                            start_ms=chunks[i]['start_ms'],
                            end_ms=chunks[i]['end_ms'],
                            text=text
                        )
                except Exception as e:
                    logger.error(f"Chunk {i} transcription failed: {e}")
        
        # Filter None results (failed chunks)
        all_segments = [s for s in chunk_results if s]
        
        return all_segments
    
    def _split_audio(self, audio: AudioSegment, duration_ms: int) -> list:
        """Split audio into chunks."""
        chunks = []
        start = 0
        
        while start < duration_ms:
            end = min(start + CHUNK_DURATION_MS, duration_ms)
            chunks.append({
                "audio": audio[start:end],
                "start_ms": start,
                "end_ms": end
            })
            start = end
        
        logger.info(f"Split into {len(chunks)} chunks")
        return chunks
    
    def _transcribe_chunk(self, audio_segment: AudioSegment) -> str:
        """Transcribe a single audio chunk with retries and in-memory processing."""
        import io
        import random
        
        # Optimize audio format for ASR (16kHz, mono)
        audio_mono = audio_segment.set_channels(1).set_frame_rate(16000)
        
        # Export to in-memory WAV
        # Using BytesIO avoids disk I/O and temp file/thread safety issues
        buf = io.BytesIO()
        audio_mono.export(buf, format="wav")
        buf.seek(0)
        audio_data = buf.read()
        
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        audio_uri = f"data:audio/wav;base64,{audio_base64}"
        
        messages = [
            {"role": "system", "content": [{"text": "请准确识别音频内容。"}]},
            {"role": "user", "content": [{"audio": audio_uri}]}
        ]
        
        max_retries = 3
        backoff = 1.0
        
        for attempt in range(max_retries):
            try:
                response = dashscope.MultiModalConversation.call(
                    api_key=self.api_key,
                    model="qwen3-asr-flash",
                    messages=messages,
                    result_format="message",
                    asr_options={
                        "language": "zh",
                        "enable_lid": True,
                        "enable_itn": True
                    }
                )
                
                if response.status_code == 200:
                    if response.output and response.output.choices:
                        choice = response.output.choices[0]
                        if choice.message and choice.message.content:
                            for item in choice.message.content:
                                if 'text' in item:
                                    return item['text']
                    return "" # Empty response implies no speech or silence
                
                # Handle specific API errors
                if response.code in ["429", "TooManyRequests"]:
                    logger.warning(f"ASR Rate limit (429) on attempt {attempt+1}, backing off {backoff}s")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                else:
                    logger.warning(f"ASR API error (Attempt {attempt+1}): {response.code} - {response.message}")
            
            except Exception as e:
                logger.error(f"ASR Exception (Attempt {attempt+1}): {e}")
            
            # General backoff for errors
            if attempt < max_retries - 1:
                time.sleep(backoff + random.random() * 0.5)
                backoff *= 1.5
        
        logger.error("All ASR attempts failed for chunk.")
        return ""
    
    def generate_vtt(self, segments: List[SubtitleSegment], output_path: str) -> bool:
        """
        Generate WebVTT subtitle file from segments.
        
        Post-processes ASR output: splits large chunks into sentence-level cues
        and allocates time proportionally based on character count.
        
        Args:
            segments: List of SubtitleSegment (from 2-3min ASR chunks)
            output_path: Full path to save the .vtt file
        
        Returns:
            True if successful, False otherwise
        """
        import re
        
        if not segments:
            logger.warning("No segments to generate VTT from")
            return False
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Post-process: split each chunk into sentences with proportional timing
            fine_grained_cues = []
            
            for seg in segments:
                sentences = self._split_into_sentences(seg.text)
                if not sentences:
                    continue
                
                total_chars = sum(len(s) for s in sentences)
                if total_chars == 0:
                    continue
                
                duration_ms = seg.end_ms - seg.start_ms
                current_start = seg.start_ms
                
                for sentence in sentences:
                    # Allocate time proportionally by character count
                    char_ratio = len(sentence) / total_chars
                    sentence_duration = int(duration_ms * char_ratio)
                    sentence_end = current_start + sentence_duration
                    
                    fine_grained_cues.append(SubtitleSegment(
                        start_ms=current_start,
                        end_ms=sentence_end,
                        text=sentence
                    ))
                    
                    current_start = sentence_end
            
            # Write VTT file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                
                for i, cue in enumerate(fine_grained_cues):
                    start_time = self._format_vtt_time(cue.start_ms)
                    end_time = self._format_vtt_time(cue.end_ms)
                    
                    f.write(f"{i+1}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{cue.text}\n\n")
            
            logger.info(f"VTT saved: {len(fine_grained_cues)} cues from {len(segments)} ASR chunks")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate VTT: {e}")
            return False
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences for fine-grained subtitles.
        Target: ~10-30 Chinese characters per sentence (roughly 2-6 seconds).
        """
        import re
        
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
    
    def _format_vtt_time(self, ms: int) -> str:
        """Format milliseconds as VTT timestamp (HH:MM:SS.mmm)."""
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    
    def transcribe_to_vtt(self, audio_path: str, vtt_output_path: str) -> bool:
        """
        Convenience method: Transcribe audio and save as VTT in one step.
        
        Args:
            audio_path: Path to audio file
            vtt_output_path: Path to save VTT file
        
        Returns:
            True if successful
        """
        segments = self.transcribe_audio(audio_path)
        if segments:
            return self.generate_vtt(segments, vtt_output_path)
        return False
