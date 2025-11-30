"""
Google Calendar Automation using Playwright.
"""
import asyncio
import os
import urllib.parse
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from typing import Optional


class CalendarAutomation:
    
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

    async def get_events_for_date(self, target_date: datetime) -> list[str]:
        """
        Fetch all event descriptions from the calendar for a given date.
        Returns a list of raw event text strings (for AI processing).
        """
        if not self._is_logged_in:
            return []
        
        # Multiple selectors for event elements (fallback chain)
        event_selectors = [
            '[data-eventid]',
            '[role="button"][data-eventchip]',
            '[data-eventchip="true"]',
        ]
        
        for attempt in range(2):
            try:
                await self._ensure_browser()
                await self.navigate_to_date(target_date)
                await asyncio.sleep(0.5)  # Allow events to render
                
                # Try each selector until we find events
                event_elements = []
                for selector in event_selectors:
                    try:
                        event_elements = await self.page.query_selector_all(selector)
                        if event_elements:
                            print(f"Found {len(event_elements)} events using selector: {selector}")
                            break
                    except Exception:
                        continue
                
                events = []
                for element in event_elements:
                    try:
                        text = await element.get_attribute('aria-label')
                        if not text:
                            text = await element.inner_text()
                        if text and text.strip():
                            events.append(text.strip())
                    except Exception as e:
                        print(f"Error extracting event text: {e}")
                        continue
                
                print(f"Extracted {len(events)} events for {target_date.strftime('%Y-%m-%d')}")
                return events
                
            except Exception as e:
                print(f"Error fetching events (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    await self._reconnect(headless=self._is_headless)
        
        return []

    async def show_calendar_date(self, target_date: datetime) -> bool:
        """Switch to visible mode and navigate to a date (for user review)."""
        try:
            await self._switch_to_visible()
            await self.navigate_to_date(target_date)
            return True
        except Exception as e:
            print(f"Error showing calendar: {e}")
            return False

    async def create_event(self, title: str, start_time: datetime, end_time: datetime) -> tuple[bool, str]:
        if not self._is_logged_in:
            return False
        
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
                
                return True
                
            except Exception as e:
                print(f"Error creating event (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    await self._reconnect(headless=self._is_headless)
                else:
                    try:
                        await self._switch_to_visible()
                    except:
                        pass
                    return False
        
        return False
    
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
        await self.page.bring_to_front()

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
    

    def _has_saved_state(self) -> bool:
        return os.path.exists(self.STORAGE_STATE_PATH)

_calendar_instance: Optional[CalendarAutomation] = None


def get_calendar_automation() -> CalendarAutomation:
    global _calendar_instance
    if _calendar_instance is None:
        _calendar_instance = CalendarAutomation()
    return _calendar_instance