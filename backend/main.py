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
from calendar_automation import CalendarAutomation, get_calendar_automation

# Global instances
voice_handler: VoiceHandler = None
schedule_parser: ScheduleParser = None
calendar_automation: CalendarAutomation = None

# Global variables
staticFolder: str = "static/audio"
greeting: str = "Hello, I am your scheduling assistance. How may I help you?"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup events."""
    global voice_handler, schedule_parser, calendar_automation

    print("Voice Calendar Assistant initiating...")

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
    calendar_automation = get_calendar_automation()

    logged_in = await calendar_automation.initialize(headless=False)
    if logged_in:
        print("Google Calendar connected with saved login")
    else:
        print("Please login to Google Calendar when prompted")

    greeting_file_name: str = "greeting.mp3"
    # Generate greeting audio if not exist
    greeting_path = staticFolder + '/' + greeting_file_name
    if not os.path.exists(greeting_path):
        voice_handler.text_to_speech(greeting, filename = greeting_file_name)
    
    yield

    print("Voice Calendar Assistant shutting down...")
    if calendar_automation:
        await calendar_automation.close()

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
        "status": "healthy",
        "logged_in": calendar_automation.is_logged_in if calendar_automation else False
    }


@app.get("/start-conversation")
async def start_conversation():
    return _build_response(greeting, success=True)


@app.post("/schedule")
async def schedule(audio: UploadFile = File(...)):
    """Transcribe audio and process the schedule request."""
    
    # Transcribe
    audio_data = await audio.read()
    user_text = voice_handler.transcribe(audio_data, audio.filename)
    
    if not user_text:
        return _build_response("I didn't catch that. Could you please try again?", success=False)
    
    # Parse
    event, error = _parse_schedule(user_text)
    if error:
        return _build_response(error, success=False, transcript=user_text)
    
    # Create event
    success, message = await _create_calendar_event(event)
    return _build_response(message, success=success, transcript=user_text)

@app.get("/login-status")
async def get_login_status():
    if not calendar_automation.is_logged_in:
        message = "Please login to Google Calendar first. I am opening the login page for you."
        await calendar_automation.start_manual_login()  # Open browser
        return {
            "logged_in": False,
            "message": message,
            "audio_url": voice_handler.text_to_speech(message)
        }
    
    return {
        "logged_in": True,
        "message": "Connected"
    }

@app.get("/check-login")
async def check_login():
    """Poll this to detect when user completes login. Saves auth state."""
    is_logged_in = await calendar_automation.check_login_status()
    
    return {
        "logged_in": is_logged_in,
        "message": "Connected!" if is_logged_in else "Waiting for login..."
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

def _check_calendar_login() -> tuple[bool, str | None]:
    """
    Check if calendar is ready.
    Returns (True, None) if ready, (False, error_message) if not.
    """
    if not calendar_automation.is_logged_in:
        return False, "Please login to Google Calendar first."
    
    return True, None


async def _create_calendar_event(event: dict) -> tuple[bool, str | None]:
    """
    Create event in Google Calendar.
    Returns (True, success_message) on success, (False, error_message) on failure.
    """
    try:
        is_ready, error = _check_calendar_login()
        if not is_ready:
            return False, error
        
        # Check for conflicts
        is_available, conflict_info = await calendar_automation.check_time_slot_available(
            event['start_time'], event['end_time']
        )
        
        if not is_available:
            time_str = event['start_time'].strftime('%B %d at %I:%M %p')
            conflict_detail = f": {conflict_info}" if conflict_info else ""
            return False, f"You have a conflict at {time_str}{conflict_detail}. Please choose another time."
        
        # Create event
        success, message = await calendar_automation.create_event(
            event['title'], event['start_time'], event['end_time']
        )
        
        if success:
            time_str = event['start_time'].strftime('%B %d at %I:%M %p')
            return True, f"Done! Added '{event['title']}' to your calendar for {time_str}."
        else:
            return False, f"Failed to create event: {message}"
    
    except Exception as e:
        print(f"Calendar error: {e}")
        return False, "Sorry, there was an error with Google Calendar."

def _build_response(message: str, success: bool, transcript: str = "", with_audio: bool = True):
    response = {
        "transcript": transcript,
        "message": message,
        "success": success,
    }
    
    if with_audio:
        response["audio_url"] = voice_handler.text_to_speech(message)
    
    return response