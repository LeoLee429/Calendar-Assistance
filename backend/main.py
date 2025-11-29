"""
Calendar Assistance - Fast API main
"""
import os
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import asynccontextmanager

from voice_handler import VoiceHandler
from schedule_parser import ScheduleParser, ScheduleParseError

# Global instances
voice_handler: VoiceHandler = None
schedule_parser: ScheduleParser = None

# Global variables
staticFolder: str = "static/audio"
greeting: str = "Hello, I am your scheduling assistance. How may I help you?"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup events."""
    global voice_handler, schedule_parser

    # Create directory if not exist
    os.makedirs(staticFolder, exist_ok=True)

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

    # Service init
    voice_handler = VoiceHandler(output_dir=staticFolder)
    schedule_parser = ScheduleParser()

    greeting_file_name: str = "greeting.mp3"
    # Generate greeting audio if not exist
    greeting_path = staticFolder + '/' + greeting_file_name
    if not os.path.exists(greeting_path):
        voice_handler.text_to_speech(greeting, filename = greeting_file_name)
    
    yield

app = FastAPI(
    title="Voice Calendar Assistant",
    description="Voice-driven calendar scheduling with Google Calendar automation",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static
app.mount("/audio", StaticFiles(directory="static/audio"), name="audio")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy"
    }

@app.get("/start-conversation")
async def start_conversation():
    return {
        "audio_url": "/audio/greeting.mp3",
        "message": greeting
    }

@app.post("/schedule")
async def schedule(audio: UploadFile = File(...)):
    """Transcribe audio and process the schedule request."""
    
    # Transcribe
    audio_data = await audio.read()
    user_text = voice_handler.transcribe(audio_data, audio.filename)
    
    if not user_text:
        return _error_response("I didn't catch that. Could you please try again?")
    
    # Parse
    event, error = _parse_schedule(user_text)
    
    if error:
        return _error_response(error, transcript=user_text)
    
    # Success
    event_text = f"{event['date']} {event['start_time']}-{event['end_time']}: {event['title']}"
    return {
        "transcript": user_text,
        "message": event_text,
        "success": True,
        "audio_url": voice_handler.text_to_speech(event_text)
    }


def _parse_schedule(text: str) -> tuple[dict | None, str | None]:
    """
    Parse schedule from text.
    Returns (event, None) on success, (None, error_message) on failure.
    """
    try:
        event = schedule_parser.parse_schedule_request(text)
        return event, None
    
    except ScheduleParseError as spe:
        if spe.field == "api_error":
            return None, f"Service error: {spe.message}"
        elif spe.field in ["title", "date", "time"]:
            return None, f"Could you please provide more details? {spe.message}"
        else:
            return None, "I couldn't understand that. Could you please try again?"
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None, "Sorry, there was an unexpected error."


def _error_response(message: str, transcript: str = ""):
    """Build error response with TTS."""
    return {
        "transcript": transcript,
        "message": message,
        "success": False,
        "audio_url": voice_handler.text_to_speech(message)
    }