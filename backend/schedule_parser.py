"""
Schedule Parser using OpenAI GPT
"""
import os
import json
from datetime import datetime
from openai import OpenAI, APIError, AuthenticationError, RateLimitError


class ScheduleParseError(Exception):
    """Raised when schedule parsing fails."""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field  # "title", "date", "time", "general", or "api_error"
        super().__init__(self.message)


class ScheduleParser:
    """AI-powered schedule parser using OpenAI."""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.client = OpenAI(api_key=api_key)
        print("ScheduleParser initialized.")
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for schedule extraction."""
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M")
        current_weekday = datetime.now().strftime("%A")
        
        return f"""
            You are a schedule parsing assistant. Extract scheduling information from user input.

            Current date: {current_date} ({current_weekday})
            Current time: {current_time}

            Extract the following fields from the user's request:
            1. title: The name/description of the event
            2. date: The date of the event (YYYY-MM-DD format)
            3. start_time: Start time (HH:MM in 24-hour format)
            4. end_time: End time (HH:MM in 24-hour format)

            Time format rules - ALL of these are valid times:
            - "10am", "10 am", "10 a.m.", "10AM" → 10:00
            - "2:30pm", "2:30 pm", "2:30 p.m." → 14:30
            - "noon" → 12:00
            - "midnight" → 00:00

            Rules:
            - "today" = {current_date}
            - "tomorrow" = the day after {current_date}
            - "next Monday/Tuesday/etc" = the upcoming weekday after today
            - If no end time is specified but duration is given (e.g., "for 2 hours"), calculate end_time
            - If neither end time nor duration is given, assume 1 hour duration
            - Handle both English and Chinese input

            Respond ONLY with valid JSON (no markdown, no explanation):
            {{"title": "event title", "date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM"}}

            If you cannot extract required information, respond with:
            {{"error": "description of what's missing", "field": "title|date|time"}}
        """

    def parse_schedule_request(self, text: str) -> dict:
        """
        Parse natural language into structured schedule data using OpenAI.
        """
        if not text or not text.strip():
            raise ScheduleParseError("No input provided", field="general")
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=256,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": text.strip()}
                ]
            )
        except AuthenticationError:
            raise ScheduleParseError("Invalid API key", field="api_error")
        except RateLimitError:
            raise ScheduleParseError("Rate limit exceeded. Please try again later.", field="api_error")
        except APIError as e:
            raise ScheduleParseError(f"OpenAI API error: {e}", field="api_error")

        try:
            result = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            raise ScheduleParseError("Could not understand the request.", field="general")
        
        if "error" in result:
            field = result.get("field", "general")
            print(f"GPT error field: '{field}'")
            
            # Parse multiple fields
            if "|" in field:
                fields = [f.strip() for f in field.split("|")]
                fields = [f for f in fields if f in ["title", "date", "time"]]
            else:
                fields = [field] if field in ["title", "date", "time"] else []
            
            # All 3 missing = generic error
            if len(fields) == 0 or len(fields) == 3:
                raise ScheduleParseError("I couldn't understand that", field="general")
            
            field_messages = {
                "title": "what the event is about",
                "date": "the date",
                "time": "the time"
            }
            missing = [field_messages[f] for f in fields]
            message = "Please provide " + " and ".join(missing)
            
            raise ScheduleParseError(message, field=fields[0])
        
        try:
            date = datetime.strptime(result["date"], "%Y-%m-%d")
            start_time = datetime.strptime(f"{result['date']} {result['start_time']}", "%Y-%m-%d %H:%M")
            end_time = datetime.strptime(f"{result['date']} {result['end_time']}", "%Y-%m-%d %H:%M")
        except (ValueError, KeyError) as e:
            raise ScheduleParseError("Could not parse the date/time.", field="time")
        
        return {
            'date': date,
            'start_time': start_time,
            'end_time': end_time,
            'title': result['title']
        }


__all__ = ['ScheduleParser', 'ScheduleParseError']