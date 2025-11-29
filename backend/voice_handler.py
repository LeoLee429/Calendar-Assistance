"""
Voice Handler - OpenAI Whisper STT and TTS
"""
import os
from pathlib import Path
from datetime import datetime
from openai import OpenAI

class VoiceHandler:
    """Handles STT and TTS"""
    def __init__(self, output_dir: str = 'audio', voice: str = "nova"):
        env_file = Path(".env")
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=env_file)
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in .env")
        elif not env_file.exists():
            # Create .env
            env_file.write_text("OPENAI_API_KEY=\n")
            raise FileNotFoundError(".env not found. Created .env file. Please enter your API key.")
        
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

__all__ = ['VoiceHandler']