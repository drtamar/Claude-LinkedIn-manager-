import json
import asyncio
from cryptography.fernet import Fernet
from app.config import get_settings

settings = get_settings()

_fernet: Fernet | None = None


def get_fernet() -> Fernet | None:
    global _fernet
    if not settings.linkedin_cookie_secret:
        return None
    if _fernet is None:
        key = settings.linkedin_cookie_secret
        if isinstance(key, str):
            key = key.encode()
        _fernet = Fernet(key)
    return _fernet


def encrypt_cookies(cookies: list[dict]) -> str:
    fernet = get_fernet()
    raw = json.dumps(cookies).encode()
    if fernet:
        return fernet.encrypt(raw).decode()
    return raw.decode()  # plaintext fallback for dev


def decrypt_cookies(encrypted: str) -> list[dict]:
    fernet = get_fernet()
    if fernet:
        try:
            raw = fernet.decrypt(encrypted.encode())
            return json.loads(raw)
        except Exception:
            pass
    try:
        return json.loads(encrypted)
    except Exception:
        return []


async def create_browser_context(cookies: list[dict]):
    """Create a Playwright browser context loaded with user cookies."""
    from playwright.async_api import async_playwright
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            if cookies:
                await context.add_cookies(cookies)
            return playwright, browser, context
        except Exception:
            await browser.close()
            raise
    except Exception:
        await playwright.stop()
        raise


async def check_session_valid(cookies: list[dict]) -> bool:
    playwright, browser, context = await create_browser_context(cookies)
    try:
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(2)
        url = page.url
        return "login" not in url and "authwall" not in url
    except Exception:
        return False
    finally:
        await browser.close()
        await playwright.stop()
