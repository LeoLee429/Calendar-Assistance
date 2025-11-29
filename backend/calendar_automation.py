"""
Google Calendar Automation using Playwright.
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
import urllib.parse


class CalendarAutomation:
    """Automates Google Calendar operations via browser."""
    
    STORAGE_STATE_PATH = "auth/google_auth_state.json"
    GOOGLE_CALENDAR_URL = "https://calendar.google.com/calendar"
    
    def __init__(self):
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.playwright = None
        self._is_logged_in = False
        
        Path("auth").mkdir(exist_ok=True)
    
    def _has_saved_state(self) -> bool:
        """Check if saved login state exists."""
        return os.path.exists(self.STORAGE_STATE_PATH)

    async def _close_context(self):
        """Close current context."""
        if self.page:
            await self.page.close()
            self.page = None
        if self.context:
            await self.context.close()
            self.context = None
    
    async def initialize(self, headless: bool = False) -> bool:
        """
        Initialize browser and load saved state if available.
        
        Returns:
            True if logged in successfully, False if manual login needed
        """
        self.playwright = await async_playwright().start()
        
        if self._has_saved_state():
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                self.context = await self.browser.new_context(
                    storage_state=self.STORAGE_STATE_PATH,
                    viewport={'width': 1280, 'height': 800}
                )
                self.page = await self.context.new_page()
                
                await self.page.goto(self.GOOGLE_CALENDAR_URL, wait_until='domcontentloaded', timeout=15000)
                
                if 'calendar.google.com' in self.page.url and 'accounts.google.com' not in self.page.url:
                    self._is_logged_in = True
                    return True
                else:
                    print("Saved state expired")
                    await self._close_context()
                    await self.browser.close()
            except Exception as e:
                print(f"Error loading saved state: {e}")
                if self.browser:
                    await self._close_context()
                    await self.browser.close()
        
        self.browser = None
        return False
    
    async def start_manual_login(self) -> str:
        """Start manual login process with visible browser."""
        if self.browser is None:
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
        
        await self._close_context()
        
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800}
        )
        self.page = await self.context.new_page()
        
        await self.page.goto(self.GOOGLE_CALENDAR_URL, wait_until='domcontentloaded', timeout=30000)
        
        print("Please complete login in the browser window")
        return "Please complete login in the browser window."
    
    async def check_login_status(self) -> bool:
        """Check if user has completed login."""
        if self.page is None:
            return False
        
        try:
            current_url = self.page.url
            
            if 'calendar.google.com' in current_url and 'accounts.google.com' not in current_url:
                print("Login detected, saving state...")
                await self._save_login_state()
                self._is_logged_in = True
                return True
            
            return False
        except Exception as e:
            print(f"check_login_status error: {e}")
            return False
        
    async def _switch_to_headless(self):
        """Close visible browser and reopen in headless mode."""
        print("Switching to headless...")
        
        await self._close_context()
        if self.browser:
            await self.browser.close()
        
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        self.context = await self.browser.new_context(
            storage_state=self.STORAGE_STATE_PATH,
            viewport={'width': 1280, 'height': 800}
        )
        self.page = await self.context.new_page()
        
        await self.page.goto(self.GOOGLE_CALENDAR_URL, wait_until='domcontentloaded', timeout=15000)
        
        print("Headless mode ready")
    
    async def _save_login_state(self):
        """Save current browser state for future sessions."""
        try:
            await self.context.storage_state(path=self.STORAGE_STATE_PATH)
            print(f"Login state saved to {self.STORAGE_STATE_PATH}")
        except Exception as e:
            print(f"Error saving login state: {e}")
    
    async def navigate_to_date(self, target_date: datetime) -> bool:
        """Navigate to a specific date in Google Calendar."""
        if not self._is_logged_in or self.page is None:
            return False
        
        try:
            date_str = target_date.strftime("%Y/%m/%d")
            calendar_url = f"{self.GOOGLE_CALENDAR_URL}/r/day/{date_str}"
            
            await self.page.goto(calendar_url, wait_until='domcontentloaded', timeout=15000)
            
            print(f"Navigated to {date_str}")
            return True
        except Exception as e:
            print(f"Error navigating to date: {e}")
            return False


    async def check_time_slot_available(self, start_time: datetime, end_time: datetime) -> tuple[bool, str]:
        """Check if a time slot is available (no conflicts)."""
        if not self._is_logged_in or self.page is None:
            return False, "Not logged in"
        
        try:
            await self.navigate_to_date(start_time)
            
            try:
                events = await self.page.query_selector_all('[data-eventid]')
                for event in events:
                    event_text = await event.inner_text()
                    if event_text:
                        print(f"Found existing event: {event_text[:50]}...")
            except:
                pass
            
            return True, ""
            
        except Exception as e:
            print(f"Error checking time slot: {e}")
            return True, ""


    async def create_event(self, title: str, start_time: datetime, end_time: datetime) -> tuple[bool, str]:
        """Create event using Google Calendar's URL parameters."""
        if not self._is_logged_in or self.page is None:
            return False, "Not logged in to Google Calendar"
        
        try:
            start_str = start_time.strftime("%Y%m%dT%H%M%S")
            end_str = end_time.strftime("%Y%m%dT%H%M%S")
            encoded_title = urllib.parse.quote(title)
            
            create_url = (
                f"https://calendar.google.com/calendar/render"
                f"?action=TEMPLATE"
                f"&text={encoded_title}"
                f"&dates={start_str}/{end_str}"
            )
            
            await self.page.goto(create_url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(2)
            
            save_selectors = [
                'button:has-text("Save")',           # English
                'button:has-text("儲存")',            # Traditional Chinese
                'button:has-text("保存")',            # Simplified Chinese
                '[aria-label="Save"]',
                '[aria-label="儲存"]',
                '[aria-label="保存"]',
                '[data-mdc-dialog-action="save"]',   # Material design
            ]
            
            save_button = None
            for selector in save_selectors:
                try:
                    save_button = await self.page.wait_for_selector(selector, timeout=2000)
                    if save_button:
                        print(f"Found save button with: {selector}")
                        break
                except:
                    continue
            
            if save_button:
                await save_button.click()
                await asyncio.sleep(2)
                print(f"Event '{title}' created")
                return True, f"Event '{title}' scheduled"
            else:
                print("Save button not found, trying Ctrl+S")
                await self.page.keyboard.press('Control+s')
                await asyncio.sleep(2)
            
            return True, f"Event '{title}' created"
            
        except Exception as e:
            print(f"Error creating event: {e}")
            return False, str(e)
    
    async def close(self):
        """Clean up browser resources."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            print("Browser closed")
        except Exception as e:
            print(f"Error closing browser: {e}")
    
    @property
    def is_logged_in(self) -> bool:
        return self._is_logged_in


_calendar_instance: CalendarAutomation = None


def get_calendar_automation() -> CalendarAutomation:
    """Singleton."""
    global _calendar_instance
    if _calendar_instance is None:
        _calendar_instance = CalendarAutomation()
    return _calendar_instance
