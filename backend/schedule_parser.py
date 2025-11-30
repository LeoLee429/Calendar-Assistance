"""
Schedule Parser using OpenAI GPT
"""
import os
import json
from datetime import datetime
from openai import OpenAI, APIError, AuthenticationError, RateLimitError


class ScheduleParseError(Exception):
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


class ScheduleParser:
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.client = OpenAI(api_key=api_key)
        print("ScheduleParser initialized.")
    
    def _get_system_prompt(self) -> str:
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M")
        current_weekday = datetime.now().strftime("%A")
        
        return f"""You are a schedule parsing assistant. Extract scheduling information from user input.

Current date: {current_date} ({current_weekday})
Current time: {current_time}

Extract the following fields:
1. title: Event name/description (REQUIRED - do NOT make up a title)
2. date: Date (YYYY-MM-DD format)
3. start_time: Start time (HH:MM in 24-hour format)
4. end_time: End time (HH:MM in 24-hour format)

Title extraction examples:
- "Schedule a call with the CEO tomorrow" → title: "call with the CEO"
- "Schedule calls the CEO in the morning" → title: "call the CEO"
- "Meeting with John at 3pm" → title: "Meeting with John"
- "Dentist appointment tomorrow" → title: "Dentist appointment"
- "Remind me to buy groceries" → title: "buy groceries"
- "Tomorrow 10am" → ERROR: no title provided

Time rules - convert vague times to specific times:
- "morning" → 09:00
- "afternoon" → 14:00
- "evening" → 18:00
- "noon" / "lunch" → 12:00
- "end of day" / "EOD" → 17:00
- "10am", "10 am", "10 a.m." → 10:00
- "2:30pm" → 14:30

Date rules:
- "today" = {current_date}
- "tomorrow" = day after {current_date}
- "day after tomorrow" = 2 days after {current_date}
- "next Monday/Tuesday/etc" = upcoming weekday

Duration rules:
- If no end time given, assume 1 hour duration

IMPORTANT:
- Extract the activity/event description as the title
- Do NOT return error if user describes an activity (call, meeting, appointment, etc.)

Respond with JSON only.

Success response:
{{"title": "...", "date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM"}}

Error response (return ONLY the missing fields):
{{"error": "Please tell me what the event is about", "field": "title"}}
{{"error": "Please specify a date", "field": "date"}}
{{"error": "Please specify a time", "field": "time"}}

The "field" value must be exactly ONE of: "title", "date", or "time"."""

    def parse_schedule_request(self, text: str) -> dict:
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
        except AuthenticationError as e:
            print(f"OpenAI AuthenticationError: {e}")
            raise ScheduleParseError("Service temporarily unavailable. Please try again.", field="api_error")
        except RateLimitError as e:
            print(f"OpenAI RateLimitError: {e}")
            raise ScheduleParseError("Service is busy. Please try again in a moment.", field="api_error")
        except APIError as e:
            print(f"OpenAI APIError: {e}")
            raise ScheduleParseError("Service temporarily unavailable. Please try again.", field="api_error")
        except Exception as e:
            print(f"OpenAI unexpected error: {e}")
            raise ScheduleParseError("Something went wrong. Please try again.", field="api_error")
        
        try:
            result = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            raise ScheduleParseError("I couldn't understand that. Please try again.", field="general")
        
        if "error" in result:
            field = result.get("field", "general").lower()
            
            if "|" in field:
                fields = [f.strip() for f in field.split("|")]
                fields = [f for f in fields if f in ["title", "date", "time"]]
            else:
                fields = [field] if field in ["title", "date", "time"] else []
            
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
            print(f"Date parse error: {e}")
            raise ScheduleParseError("I couldn't understand the date or time. Please try again.", field="time")
        
        return {
            'date': date,
            'start_time': start_time,
            'end_time': end_time,
            'title': result['title']
        }


__all__ = ['ScheduleParser', 'ScheduleParseError']