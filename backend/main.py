"""
Calendar Assistance - FastAPI main
"""
import os
import json
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import asynccontextmanager

from voice_handler import VoiceHandler
from ai_service import AIService, ScheduleParseError, get_ai_service
from calendar_automation import CalendarAutomation, get_calendar_automation
from conversation_context import get_context

# Global instances
voice_handler: VoiceHandler = None
ai_service: AIService = None
calendar_automation: CalendarAutomation = None

# Constants
STATIC_FOLDER = "static/audio"
GREETING = "Hello, I am your scheduling assistance. How may I help you?"
MESSAGES: dict = None


os.makedirs(STATIC_FOLDER, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global voice_handler, ai_service, calendar_automation
    print("Voice Calendar Assistant initiating...")
    
    _load_env()
    _load_messages()

    voice_handler = VoiceHandler(output_dir=STATIC_FOLDER)
    ai_service = get_ai_service()
    calendar_automation = get_calendar_automation()

    logged_in = await calendar_automation.initialize(headless=True)
    if logged_in:
        print("Google Calendar connected with saved login")
    else:
        print("Please login to Google Calendar when prompted")

    greeting_file_name: str = "greeting.mp3"
    greeting_path = STATIC_FOLDER + '/' + greeting_file_name
    if not os.path.exists(greeting_path):
        voice_handler.text_to_speech(GREETING, filename=greeting_file_name)
    
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
app.mount("/audio", StaticFiles(directory=STATIC_FOLDER), name="audio")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "logged_in": calendar_automation.is_logged_in if calendar_automation else False
    }


@app.get("/start-conversation")
async def start_conversation():
    get_context().clear()
    voice_handler.set_language('en')
    return _build_response(GREETING, success=True)


@app.post("/schedule")
async def schedule(audio: UploadFile = File(...)):
    """Transcribe audio and process the schedule request."""
    
    context = get_context()
    
    # Transcribe
    audio_data = await audio.read()
    user_text = voice_handler.transcribe(audio_data, audio.filename)
    
    if not user_text:
        return _build_response(_get_message('not_heard'), success=False)
    
    # Parse with context
    event, error = _parse_schedule(user_text, context)
    if error:
        return _build_response(error, success=False, transcript=user_text)
    
    # Create event
    success, message = await _create_calendar_event(event, context)
    return _build_response(message, success=success, transcript=user_text)


@app.get("/login-status")
async def get_login_status():
    if not calendar_automation.is_logged_in:
        message = _get_message('login')
        await calendar_automation.start_manual_login()
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


def _load_env():
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / ".env"
    
    if not env_file.exists():
        env_file.write_text("OPENAI_API_KEY=\n")
        raise FileNotFoundError(f".env not found. Created at {env_file}. Please add your API key.")
    
    load_dotenv(env_file)
    
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(f"OPENAI_API_KEY is empty in {env_file}")


def _load_messages():
    global MESSAGES
    msg_file = Path(__file__).parent / "messages.json"
    with open(msg_file, 'r', encoding='utf-8') as f:
        MESSAGES = json.load(f)


def _get_message(key: str, lang: str = None, **kwargs) -> str:
    lang = lang or voice_handler.language if voice_handler else 'en'
    msgs = MESSAGES.get(lang, MESSAGES['en'])
    return msgs.get(key, MESSAGES['en'][key]).format(**kwargs)


def _format_time(dt, lang: str = None) -> str:
    lang = lang or voice_handler.language if voice_handler else 'en'
    if lang in ['zh-CN', 'zh-TW']:
        return dt.strftime('%m月%d日 %H:%M')
    return dt.strftime('%B %d at %I:%M %p')

def _parse_schedule(text: str, context=None) -> tuple[dict | None, str | None]:
    """
    Parse schedule from text, optionally using context for multi-turn.
    Returns (event, None) on success, (None, error_message) on failure.
    """
    try:
        context_str = context.get_context_for_parser() if context else ""
        parsed = ai_service.parse_schedule(text, context_str)
        
        if parsed.get('lang'):
            voice_handler.set_language(parsed['lang'])
        
        if context:
            event = context.merge(parsed)
            if event:
                event['lang'] = parsed.get('lang', 'en')
                return event, None
        
        return parsed, None
    
    except ScheduleParseError as spe:
        if spe.field == "api_error":
            return None, _get_message('error')
        
        if spe.partial_data and spe.partial_data.get('lang'):
            voice_handler.set_language(spe.partial_data['lang'])
        
        if context and spe.partial_data:
            event = context.merge(spe.partial_data)
            if event:
                return event, None
        
        return None, spe.message
    
    except Exception as e:
        import traceback
        print(f"Unexpected error type: {type(e).__name__}")
        print(f"Unexpected error: {e}")
        traceback.print_exc()
        return None, _get_message('error')


def _check_calendar_login() -> tuple[bool, str | None]:
    if not calendar_automation.is_logged_in:
        return False, _get_message('login')
    return True, None


async def _create_calendar_event(event: dict, context=None) -> tuple[bool, str | None]:
    """
    Create event in Google Calendar.
    Returns (True, success_message) on success, (False, error_message) on failure.
    """
    try:
        is_ready, error = _check_calendar_login()
        if not is_ready:
            return False, error
        
        # Fetch existing events for the date
        existing_events = await calendar_automation.get_events_for_date(event['start_time'])
        
        # Check for conflicts using AI
        is_available, conflict_info = ai_service.check_conflict(
            existing_events,
            event['start_time'],
            event['end_time']
        )
        
        if not is_available:
            if context:
                context.clear_for_reschedule()
            
            await calendar_automation.show_calendar_date(event['start_time'])
            time_str = _format_time(event['start_time'])
            return False, _get_message('conflict', time=time_str, event=conflict_info or '')
        
        # Create event
        success= await calendar_automation.create_event(
            event['title'], event['start_time'], event['end_time']
        )
        
        if success:
            if context:
                context.clear()
            time_str = _format_time(event['start_time'])
            return True, _get_message('success', title=event['title'], time=time_str)
        else:
            return False, _get_message('error')
    
    except Exception as e:
        print(f"Calendar error: {e}")
        return False, _get_message('error')


def _build_response(message: str, success: bool, transcript: str = "", with_audio: bool = True):
    response = {
        "transcript": transcript,
        "message": message,
        "success": success,
    }
    
    if with_audio:
        response["audio_url"] = voice_handler.text_to_speech(message)
    
    return response