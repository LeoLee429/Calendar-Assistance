# Voice-Driven Calendar Assistant

A voice-controlled scheduling assistant that automates Google Calendar operations using browser automation. Users can speak natural language commands to create calendar events, with automatic conflict detection and voice feedback.

## Features

- Voice input via OpenAI Whisper speech-to-text
- Natural language parsing for dates, times, and event titles
- Google Calendar automation via Playwright (no API required)
- Automatic conflict detection with voice feedback
- Multi-language support (English, Simplified Chinese, Traditional Chinese (input only))
- Persistent login state to avoid repeated authentication
- Multi-turn conversation support for incomplete requests

## Tech Stack

- Backend: FastAPI (Python)
- Frontend: React with TypeScript
- Browser Automation: Playwright
- Speech-to-Text: OpenAI Whisper API
- Text-to-Speech: Google TTS (gTTS)
- NLP Parsing: OpenAI GPT-4o

## Project Structure

```
voice-calendar/
├── backend/
│   ├── main.py                 # FastAPI application entry point
│   ├── ai_service.py           # OpenAI integration for parsing and conflict detection
│   ├── calendar_automation.py  # Playwright Google Calendar automation
│   ├── voice_handler.py        # Whisper STT and gTTS TTS
│   ├── conversation_context.py # Multi-turn conversation state
│   ├── messages.json           # Localized response messages
│   ├── prompts/
│   │   ├── schedule_parser.txt    # Prompt for parsing schedule requests
│   │   └── conflict_checker.txt   # Prompt for conflict detection
│   ├── .env                    # API keys (not committed)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   └── VoiceButton.tsx
│   │   ├── hooks/
│   │   │   └── useVoiceRecognition.ts
│   │   └── services/
│   │       └── api.ts
│   └── package.json
└── README.md
```

## Prerequisites

- Python 3.12.2
- Node.js 10.2.5
- Google account
- OpenAI API key

## Installation

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn python-dotenv openai gtts playwright

# Install Playwright browsers
playwright install chromium

# Create .env file
echo "OPENAI_API_KEY=your_api_key_here" > .env
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

## Running the Application

### 1. Start the Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

First time starting the backend, it will create a .env file. Please enter your OpenAI API key there.

### 2. Start the Frontend

```bash
cd frontend
npm start
```

Open http://localhost:3000 in your browser.

### 3. Using the Assistant

1. Click "Start Voice Conversation"
2. Allow microphone access when prompted
3. First-Time Google Login

On first run, the system will open a browser window for Google Calendar login:

   a. The backend will detect no saved login state
   b. A Chromium browser window will open automatically
   c. Navigate to Google Calendar and complete login manually
   d. Complete any multi-factor authentication (MFA) if prompted
   e. Once logged in, the system saves your session to `google_auth.json`
   f. Subsequent runs will reuse this saved state

If login state expires, delete `google_auth.json` and restart the backend.

4. Wait for the greeting: "Hello, I am your scheduling assistant. How may I help you?"
5. Speak your request, for example:
   - "Schedule a meeting with the CEO tomorrow at 10am"
   - "Add lunch with John on Friday at noon for 2 hours"
6. The assistant will:
   - Parse your request
   - Check for conflicts
   - Create the event or ask for a different time

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /health | GET | Health check and login status |
| /start-conversation | GET | Get greeting and reset context |
| /schedule | POST | Process voice audio and schedule event |
| /login-status | GET | Check login, trigger manual login if needed |
| /check-login | GET | Poll login completion status |

## Voice Command Examples

English:
- "Add a meeting tomorrow at 2pm"
- "Schedule lunch with Mary on Monday at noon for 1 hour"
- "Create an event called team standup on December 5th at 9am"
#
Chinese:
- "明天下午两点开会"
- "后天早上九点和老板吃饭"
- "下周一晚上六点约朋友吃饭，两小时"

## Multi-Turn Conversation

The assistant supports incomplete requests across multiple turns:

```
User: "Add a meeting with John"
Assistant: "What date and time?"
User: "Tomorrow at 3pm"
Assistant: "Done! Added 'meeting with John' to your calendar for December 02 at 03:00 PM."
```

## Conflict Handling

When a time conflict is detected:

```
User: "Schedule a call at 10am tomorrow"
Assistant: "You have a conflict at December 02 at 10:00 AM with 'Team Standup'. What time works better?"
User: "How about 11am"
Assistant: "Done! Added 'call' to your calendar for December 02 at 11:00 AM."
```

## Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```
OPENAI_API_KEY=sk-your-api-key-here
```

### Customizing Messages

Edit `messages.json` to customize response messages for each language.

### Customizing Prompts

Edit files in `prompts/` directory to adjust parsing behavior.
