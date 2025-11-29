"""
Calendar Assistance - Fast API main
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from voice_handler import VoiceHandler

# Global instances
voice_handler: VoiceHandler = None

# Global variables
staticFolder: str = "static/audio"
greeting: str = "Hello, I am your scheduling assistance. How may I help you?"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup events."""
    global voice_handler

    # Create directory if not exist
    os.makedirs(staticFolder, exist_ok=True)

    # Service init
    voice_handler = VoiceHandler(output_dir=staticFolder)

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