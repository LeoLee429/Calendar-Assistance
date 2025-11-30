"""
Google Calendar Automation using Playwright.
"""
import asyncio
import os
import re
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
        self._is_headless = True
        
        Path("auth").mkdir(exist_ok=True)
    
    async def initialize(self, headless: bool = True) -> bool:
        self.playwright = await async_playwright().start()
        
        if self._has_saved_state():
            try:
                self._is_headless = headless
                self.browser = await self.playwright.chromium.launch(
                    headless=headless,
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
                    print("Loaded saved login state")
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
        if self.browser is None:
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
        
        self._is_headless = False
        await self._close_context()
        
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800}
        )
        self.page = await self.context.new_page()
        
        await self.page.goto(self.GOOGLE_CALENDAR_URL, wait_until='domcontentloaded', timeout=30000)
        
        print("Please complete login in the browser window")
        return "Please complete login in the browser window."
    
    async def check_login_status(self) -> bool:
        if self.page is None:
            return False
        
        try:
            current_url = self.page.url
            
            if 'calendar.google.com' in current_url and 'accounts.google.com' not in current_url:
                print("Login detected, saving state...")
                await self._save_login_state()
                await self._switch_to_headless()
                self._is_logged_in = True
                return True
            
            return False
        except Exception as e:
            print(f"check_login_status error: {e}")
            return False
    
    async def navigate_to_date(self, target_date: datetime) -> bool:
        if not self._is_logged_in:
            return False
        
        for attempt in range(2):
            try:
                await self._ensure_browser()
                date_str = target_date.strftime("%Y/%m/%d")
                calendar_url = f"{self.GOOGLE_CALENDAR_URL}/r/day/{date_str}"
                
                await self.page.goto(calendar_url, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(1)
                
                print(f"Navigated to {date_str}")
                return True
            except Exception as e:
                print(f"Error navigating to date (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    await self._reconnect(headless=self._is_headless)
                else:
                    return False
        return False

    async def check_time_slot_available(self, start_time: datetime, end_time: datetime) -> tuple[bool, str]:
        if not self._is_logged_in:
            return False, "Not logged in"
        
        for attempt in range(2):
            try:
                await self._ensure_browser()
                await self.navigate_to_date(start_time)
                
                events = await self.page.query_selector_all('[data-eventid]')
                
                for event in events:
                    try:
                        event_text = await event.inner_text()
                        if not event_text:
                            continue
                        
                        print(f"Checking event: {event_text[:50]}...")
                        
                        event_start, event_end = self._parse_event_time(event_text, start_time)
                        
                        if event_start and event_end:
                            if self._times_overlap(start_time, end_time, event_start, event_end):
                                event_title = event_text.split('\n')[0] if '\n' in event_text else event_text[:30]
                                print(f"Conflict detected with: {event_title}")
                                await self._switch_to_visible()
                                await self.navigate_to_date(start_time)
                                return False, event_title
                    except Exception as e:
                        print(f"Error parsing event: {e}")
                        continue
                
                return True, ""
                
            except Exception as e:
                print(f"Error checking time slot (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    await self._reconnect(headless=self._is_headless)
                else:
                    return True, ""
        return True, ""

    async def create_event(self, title: str, start_time: datetime, end_time: datetime) -> tuple[bool, str]:
        if not self._is_logged_in:
            return False, "Please login to Google Calendar first."
        
        for attempt in range(2):
            try:
                await self._ensure_browser()
                
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
                    'button:has-text("Save")',
                    'button:has-text("儲存")',
                    'button:has-text("保存")',
                    '[aria-label="Save"]',
                    '[aria-label="儲存"]',
                    '[aria-label="保存"]',
                    '[data-mdc-dialog-action="save"]',
                ]
                
                save_button = None
                for selector in save_selectors:
                    try:
                        save_button = await self.page.wait_for_selector(selector, timeout=2000)
                        if save_button:
                            break
                    except:
                        continue
                
                if save_button:
                    await save_button.click()
                    await asyncio.sleep(2)
                    print(f"Event '{title}' created")
                else:
                    print("Save button not found, trying Ctrl+S")
                    await self.page.keyboard.press('Control+s')
                    await asyncio.sleep(2)
                
                try:
                    await self._switch_to_visible()
                    await self.navigate_to_date(start_time)
                except:
                    pass
                
                return True, f"Event '{title}' scheduled"
                
            except Exception as e:
                print(f"Error creating event (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    await self._reconnect(headless=self._is_headless)
                else:
                    try:
                        await self._switch_to_visible()
                    except:
                        pass
                    return False, "Please try again."
        
        return False, "Please try again."
    
    async def close(self):
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

    async def _close_context(self):
        if self.page:
            await self.page.close()
            self.page = None
        if self.context:
            await self.context.close()
            self.context = None
    
    async def _ensure_browser(self):
        need_reconnect = False
        
        if self.browser is None or not self.browser.is_connected():
            need_reconnect = True
        elif self.page is None:
            need_reconnect = True
        else:
            try:
                # Test if page is actually usable
                _ = self.page.url
            except:
                need_reconnect = True
        
        if need_reconnect:
            print("Browser not available, reconnecting...")
            await self._reconnect(headless=True)
    
    async def _reconnect(self, headless: bool = True):
        await self._close_context()
        if self.browser:
            try:
                await self.browser.close()
            except:
                pass
        
        if self.playwright is None:
            self.playwright = await async_playwright().start()
        
        self._is_headless = headless
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        if self._has_saved_state():
            self.context = await self.browser.new_context(
                storage_state=self.STORAGE_STATE_PATH,
                viewport={'width': 1280, 'height': 800}
            )
        else:
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 800}
            )
        
        self.page = await self.context.new_page()
        await self.page.goto(self.GOOGLE_CALENDAR_URL, wait_until='domcontentloaded', timeout=15000)

    async def _switch_to_visible(self):
        if not self._is_headless:
            return
        print("Switching to visible mode...")
        await self._reconnect(headless=False)
        self._is_headless = False

    async def _switch_to_headless(self):
        if self._is_headless:
            return
        print("Switching to headless mode...")
        await self._reconnect(headless=True)
        self._is_headless = True

    async def _save_login_state(self):
        try:
            await self.context.storage_state(path=self.STORAGE_STATE_PATH)
            print(f"Login state saved to {self.STORAGE_STATE_PATH}")
        except Exception as e:
            print(f"Error saving login state: {e}")
    
    def _times_overlap(self, start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
        return start1 < end2 and start2 < end1

    def _has_saved_state(self) -> bool:
        return os.path.exists(self.STORAGE_STATE_PATH)

    def _parse_event_time(self, time_str: str, event_date: datetime) -> tuple[datetime, datetime]:
        patterns = [
            r'(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})',
            r'(\d{1,2})\s*[–-]\s*(\d{1,2})',
        ]
        
        chinese_pattern = r'(上午|下午)(\d{1,2})點.*?(上午|下午)(\d{1,2})點'
        chinese_match = re.search(chinese_pattern, time_str)
        
        if chinese_match:
            start_period, start_h, end_period, end_h = chinese_match.groups()
            start_h = int(start_h)
            end_h = int(end_h)
            
            if start_period == '下午' and start_h != 12:
                start_h += 12
            elif start_period == '上午' and start_h == 12:
                start_h = 0
                
            if end_period == '下午' and end_h != 12:
                end_h += 12
            elif end_period == '上午' and end_h == 12:
                end_h = 0
            
            start = event_date.replace(hour=start_h, minute=0, second=0, microsecond=0)
            end = event_date.replace(hour=end_h, minute=0, second=0, microsecond=0)
            return start, end
        
        for pattern in patterns:
            match = re.search(pattern, time_str)
            if match:
                groups = match.groups()
                if len(groups) == 4:
                    start_h, start_m, end_h, end_m = map[int](int, groups)
                else:
                    start_h, end_h = map[int](int, groups)
                    start_m, end_m = 0, 0
                
                start = event_date.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                end = event_date.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
                return start, end
        
        return None, None

_calendar_instance: CalendarAutomation = None


def get_calendar_automation() -> CalendarAutomation:
    global _calendar_instance
    if _calendar_instance is None:
        _calendar_instance = CalendarAutomation()
    return _calendar_instance