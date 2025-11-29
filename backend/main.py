"""
Calendar Assistance - Fast API main
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Voice Calendar Assistant",
    description="Voice-driven calendar scheduling with Google Calendar automation",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy"
    }

@app.get("/start-conversation")
async def start_conversation():
    return {
        "audio_url": "greeting.mp3",
        "message": "Hello!"
    }