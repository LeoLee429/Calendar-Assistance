"""
Voice Handler - OpenAI Whisper STT and gTTS
"""
import os
import io
from pathlib import Path
from datetime import datetime
from openai import OpenAI
from gtts import gTTS


class VoiceHandler:
    
    def __init__(self, output_dir: str = 'audio'):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in .env")
        
        self.client = OpenAI(api_key=api_key)
        self.output_dir = output_dir
        self.language = 'en'
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        print(f"VoiceHandler initialized.")
    
    def set_language(self, lang: str):
        if lang in ['en', 'zh-CN', 'zh-TW', 'yue']:
            self.language = lang
    
    def text_to_speech(self, text: str, filename: str = None, lang: str = None) -> str:
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f')[:-3]
            filename = filename or f"tts_{timestamp}.mp3"
            filepath = os.path.join(self.output_dir, filename)
            
            lang = lang or self.language
            
            tts = gTTS(text=text, lang=lang)
            tts.save(filepath)
            
            print(f"TTS saved: {filepath}")
            return f"/audio/{filename}"
            
        except Exception as e:
            print(f"TTS error: {e}")
            return None
    
    def transcribe(self, audio_data: bytes, filename: str = "audio.webm") -> tuple[str, str]:
        try:
            audio_file = io.BytesIO(audio_data)
            audio_file.name = filename
            
            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json"
            )
            
            text = response.text.strip()
            detected_lang = response.language or 'en'
            
            # Map Whisper lang codes to gTTS codes
            lang_map = {
                'en': 'en',
                'english': 'en',
                'zh': 'zh-CN',
                'chinese': 'zh-CN',
            }
            lang = lang_map.get(detected_lang, 'en')
            self.set_language(lang)
            
            print(f"Transcribed: {text} (detected: {detected_lang} → {lang})")
            return text
            
        except Exception as e:
            print(f"Transcription error: {e}")
            raise