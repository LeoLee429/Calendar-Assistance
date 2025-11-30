"""
Conversation context for multi-turn scheduling.
"""
from datetime import datetime
from typing import Optional


class ConversationContext:
    
    def __init__(self):
        self.clear()
    
    def clear(self):
        self.title: Optional[str] = None
        self.date: Optional[datetime] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
    
    def merge(self, new_data: dict) -> Optional[dict]:
        self.title = new_data.get('title') or self.title
        self.date = new_data.get('date') or self.date
        self.start_time = new_data.get('start_time') or self.start_time
        self.end_time = new_data.get('end_time') or self.end_time
        
        if all([self.title, self.start_time, self.end_time]):
            return {
                'title': self.title,
                'date': self.date or self.start_time,
                'start_time': self.start_time,
                'end_time': self.end_time
            }
        return None
    
    def clear_for_reschedule(self):
        self.start_time = None
        self.end_time = None
    
    def get_context_for_parser(self) -> str:
        if not any([self.title, self.date, self.start_time]):
            return ""
        
        parts = []
        if self.title:
            parts.append(f"title: \"{self.title}\"")
        if self.date:
            parts.append(f"date: {self.date.strftime('%Y-%m-%d')}")
        if self.start_time:
            parts.append(f"time: {self.start_time.strftime('%H:%M')}")
        
        return f"Pending event: {', '.join(parts)}."


_context = ConversationContext()


def get_context() -> ConversationContext:
    return _context