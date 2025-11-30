"""
AI Service - OpenAI-powered schedule parsing and conflict checking.
"""
import os
import json
from datetime import datetime
from pathlib import Path
from openai import OpenAI, APIError, AuthenticationError, RateLimitError
from typing import Optional


class ScheduleParseError(Exception):
    def __init__(self, message: str, field: str = None, partial_data: dict = None):
        self.message = message
        self.field = field
        self.partial_data = partial_data or {}
        super().__init__(self.message)


class AIService:
    """Handles all OpenAI interactions for schedule parsing and conflict checking."""
    
    MODEL = "gpt-4o-mini"
    PROMPTS_DIR = Path(__file__).parent / "prompt"
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.client = OpenAI(api_key=api_key)
        self._prompts = {}
        self._load_prompts()
        print("AIService initialized.")
    
    def _load_prompts(self):
        """Load prompt templates from files."""
        for prompt_file in self.PROMPTS_DIR.glob("*.txt"):
            self._prompts[prompt_file.stem] = prompt_file.read_text()
    
    def _get_prompt(self, name: str) -> str:
        """Get a prompt template by name."""
        if name not in self._prompts:
            raise ValueError(f"Prompt '{name}' not found")
        return self._prompts[name]
    
    def _call_openai(self, system_prompt: str, user_prompt: str, max_tokens: int = 256) -> dict:
        """Make an OpenAI API call and return parsed JSON response."""
        try:
            response = self.client.chat.completions.create(
                model=self.MODEL,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return json.loads(response.choices[0].message.content)
        
        except AuthenticationError as e:
            print(f"OpenAI AuthenticationError: {e}")
            raise ScheduleParseError("Service temporarily unavailable.", field="api_error")
        except RateLimitError as e:
            print(f"OpenAI RateLimitError: {e}")
            raise ScheduleParseError("Service is busy. Please try again.", field="api_error")
        except APIError as e:
            print(f"OpenAI APIError: {e}")
            raise ScheduleParseError("Service temporarily unavailable.", field="api_error")
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            raise ScheduleParseError("Could not understand response.", field="general")
    
    def parse_schedule(self, text: str, context: str = "") -> dict:
        """
        Parse a schedule request from natural language.
        
        Args:
            text: User's natural language input
            context: Optional context from previous conversation turns
            
        Returns:
            dict with keys: title, date, start_time, end_time
            
        Raises:
            ScheduleParseError: If parsing fails or input is incomplete
        """
        if not text or not text.strip():
            raise ScheduleParseError("No input provided", field="general")
        
        # Build system prompt with current date/time
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M")
        current_weekday = datetime.now().strftime("%A")
        
        context_section = ""
        if context:
            context_section = f"""
CONVERSATION CONTEXT:
{context}

Use this context to understand follow-up responses. For example:
- If user previously said "meeting with John" and now says "make it 2pm", combine them.
- If user had a conflict and says "how about 3pm instead", use the same event title.
"""
        
        system_prompt = self._get_prompt("schedule_parser").format(
            current_date=current_date,
            current_time=current_time,
            current_weekday=current_weekday,
            context_section=context_section
        )
        
        result = self._call_openai(system_prompt, text.strip())
        print(f"LLM response: {result}")  # Debug
        
        if result.get("partial") or "error" in result:
            partial_data = self._extract_partial_data(result)
            field = self._normalize_field(result.get("field", "general"))
            message = result.get("error", "Please provide more details")
            raise ScheduleParseError(message, field=field, partial_data=partial_data)
        
        return self._parse_result_to_event(result)
    
    def _extract_partial_data(self, result: dict) -> dict:
        """Extract any partial data from an incomplete parse result."""
        partial = {}
        if result.get('title'):
            partial['title'] = result['title']
        if result.get('date'):
            try:
                partial['date'] = datetime.strptime(result['date'], "%Y-%m-%d")
            except ValueError:
                pass
        if result.get('start_time') and result.get('date'):
            try:
                partial['start_time'] = datetime.strptime(
                    f"{result['date']} {result['start_time']}", "%Y-%m-%d %H:%M"
                )
            except ValueError:
                pass
        if result.get('end_time') and result.get('date'):
            try:
                partial['end_time'] = datetime.strptime(
                    f"{result['date']} {result['end_time']}", "%Y-%m-%d %H:%M"
                )
            except ValueError:
                pass
        return partial
    
    def _normalize_field(self, field: str) -> str:
        """Normalize field name from LLM response."""
        field = field.lower().strip()
        if "|" in field:
            fields = [f.strip() for f in field.split("|")]
            fields = [f for f in fields if f in ["title", "date", "time"]]
            return fields[0] if fields else "general"
        return field if field in ["title", "date", "time"] else "general"
    
    def _parse_result_to_event(self, result: dict) -> dict:
        """Convert parsed result to event dict with datetime objects."""
        # Check required fields first
        required = ['title', 'date', 'start_time', 'end_time']
        missing = [f for f in required if not result.get(f)]
        
        if missing:
            print(f"Missing fields in LLM response: {missing}")
            print(f"Got: {result}")
            raise ScheduleParseError(
                f"Please provide {', '.join(missing)}",
                field=missing[0] if missing[0] in ['title', 'date'] else 'time'
            )
        
        try:
            date = datetime.strptime(result["date"], "%Y-%m-%d")
            start_time = datetime.strptime(
                f"{result['date']} {result['start_time']}", "%Y-%m-%d %H:%M"
            )
            end_time = datetime.strptime(
                f"{result['date']} {result['end_time']}", "%Y-%m-%d %H:%M"
            )
        except ValueError as e:
            print(f"Date parse error: {e}")
            raise ScheduleParseError("Could not understand the date or time.", field="time")
        
        return {
            'title': result['title'],
            'date': date,
            'start_time': start_time,
            'end_time': end_time
        }
    
    def check_conflict(
        self,
        events: list[str],
        proposed_start: datetime,
        proposed_end: datetime
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a proposed time slot conflicts with existing events.
        
        Args:
            events: List of event description strings from the calendar
            proposed_start: Proposed event start time
            proposed_end: Proposed event end time
            
        Returns:
            (is_available, conflicting_event_title)
            - (True, None) if slot is available
            - (False, "Event Title") if there's a conflict
        """
        if not events:
            return True, None
        
        events_text = "\n".join(f"- {event}" for event in events)
        print(f"Checking conflict for {proposed_start.strftime('%I:%M %p')} - {proposed_end.strftime('%I:%M %p')}")
        print(f"Against events:\n{events_text}")
        
        system_prompt = self._get_prompt("conflict_checker").format(
            date=proposed_start.strftime('%Y-%m-%d'),
            events=events_text
        )
        
        user_prompt = f"{proposed_start.strftime('%I:%M %p')} to {proposed_end.strftime('%I:%M %p')}"
        
        try:
            result = self._call_openai(system_prompt, user_prompt, max_tokens=100)
            
            if result.get("conflict"):
                return False, result.get("event_title", "an existing event")
            return True, None
            
        except ScheduleParseError:
            # On API error, assume no conflict to avoid blocking
            return True, None


# Global instance
_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


__all__ = ['AIService', 'ScheduleParseError', 'get_ai_service']