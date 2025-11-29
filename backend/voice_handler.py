"""
Voice Handler - OpenAI Whisper STT and TTS
"""
import os
import io
from pathlib import Path
from datetime import datetime
from openai import OpenAI

class VoiceHandler:
    """Handles STT and TTS"""
    def __init__(self, output_dir: str = 'audio', voice: str = "nova"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in .env")
        
        self.client = OpenAI(api_key=api_key)
        self.voice = voice;
        self.output_dir = output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        print(f"VoiceHandler initialized.")
    
    def text_to_speech(self, text: str, filename: str | None = None) -> str:
        """
        Convert text to speech using OpenAI TTS.
        
        Args:
            text: Text to convert
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
            filename (Optional): Output filename. Mainly for greeting.
            
        Returns:
            URL path to audio file
        """
        try:
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f')[:-3]
                filename = f"tts_{timestamp}.mp3"
            filepath = os.path.join(self.output_dir, filename)
            
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=text
            )
            
            response.stream_to_file(filepath)
            print(f"TTS saved: {filepath}")
            
            return f"/audio/{filename}"
            
        except Exception as e:
            print(f"TTS error: {e}")
            return None
    
    def transcribe(self, audio_data: bytes, filename: str = "audio.webm") -> str:
        """
        Transcribe audio using OpenAI Whisper.
        
        Args:
            audio_data: Raw audio bytes
            filename: Original filename (for format detection)
            
        Returns:
            Transcribed text
        """
        try:
            audio_file = io.BytesIO(audio_data)
            audio_file.name = filename
            
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
            
            return transcript.strip()
            
        except Exception as e:
            print(f"Transcription error: {e}")
            raise

__all__ = ['VoiceHandler']