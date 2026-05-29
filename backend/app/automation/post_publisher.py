import asyncio
from app.automation.browser_manager import create_browser_context, decrypt_cookies
from app.automation.safety_limiter import can_perform, record_action, wait_between_actions, human_type_delay, human_pause


async def publish_post(user_linkedin_cookies_encrypted: str, content: str, user_id: int) -> dict:
    """Publish a post to LinkedIn using Playwright automation."""
    can, reason = can_perform(user_id, "post_publish")
    if not can:
        return {"success": False, "error": reason}

    await wait_between_actions(user_id)

    cookies = decrypt_cookies(user_linkedin_cookies_encrypted)
    if not cookies:
        return {"success": False, "error": "No valid LinkedIn session"}

    playwright, browser, context = await create_browser_context(cookies)
    try:
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=20000)

        # Check if logged in
        if "login" in page.url or "authwall" in page.url:
            return {"success": False, "error": "LinkedIn session expired"}

        # Click "Start a post" button
        start_post_selectors = [
            "[data-control-name='share.sharebox_text']",
            ".share-box-feed-entry__trigger",
            "button[aria-label='Start a post']",
            ".artdeco-button--muted",
        ]
        clicked = False
        for selector in start_post_selectors:
            try:
                btn = await page.wait_for_selector(selector, timeout=5000)
                if btn:
                    await btn.click()
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            return {"success": False, "error": "Could not find post button"}

        await asyncio.sleep(1.5)

        # Type content
        editor_selectors = [
            ".ql-editor",
            "[data-placeholder='What do you want to talk about?']",
            ".share-creation-state__text-editor",
            "div[contenteditable='true']",
        ]
        editor = None
        for selector in editor_selectors:
            try:
                editor = await page.wait_for_selector(selector, timeout=5000)
                if editor:
                    break
            except Exception:
                continue

        if not editor:
            return {"success": False, "error": "Could not find text editor"}

        await editor.click()
        # Type character by character with human delays
        for char in content:
            await page.keyboard.type(char)
            await human_type_delay()

        await human_pause()

        # Click Post button
        post_btn_selectors = [
            "button.share-actions__primary-action",
            "[data-control-name='share.post']",
            "button[aria-label='Post']",
            ".share-box_actions button.artdeco-button--primary",
        ]
        posted = False
        for selector in post_btn_selectors:
            try:
                btn = await page.wait_for_selector(selector, timeout=5000)
                if btn:
                    await btn.click()
                    posted = True
                    break
            except Exception:
                continue

        if not posted:
            return {"success": False, "error": "Could not click Post button"}

        await asyncio.sleep(3)  # Wait for post to publish

        record_action(user_id, "post_publish")
        return {"success": True, "message": "Post published successfully"}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await browser.close()
        await playwright.stop()


async def send_connection_request(
    user_linkedin_cookies_encrypted: str,
    prospect_url: str,
    connection_note: str,
    user_id: int,
) -> dict:
    """Send a LinkedIn connection request to a prospect."""
    can, reason = can_perform(user_id, "connection_send")
    if not can:
        return {"success": False, "error": reason}

    await wait_between_actions(user_id)

    cookies = decrypt_cookies(user_linkedin_cookies_encrypted)
    if not cookies:
        return {"success": False, "error": "No valid LinkedIn session"}

    playwright, browser, context = await create_browser_context(cookies)
    try:
        page = await context.new_page()
        await page.goto(prospect_url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)

        if "login" in page.url:
            return {"success": False, "error": "LinkedIn session expired"}

        # Find Connect button
        connect_selectors = [
            "button[aria-label*='Connect']",
            "button.pv-s-profile-actions__overflow-action",
        ]
        connect_btn = None
        for selector in connect_selectors:
            try:
                connect_btn = await page.wait_for_selector(selector, timeout=5000)
                if connect_btn:
                    break
            except Exception:
                continue

        if not connect_btn:
            # Try "More" dropdown
            try:
                more_btn = await page.wait_for_selector("button[aria-label='More actions']", timeout=3000)
                await more_btn.click()
                await asyncio.sleep(0.5)
                connect_btn = await page.wait_for_selector("div[aria-label*='Connect']", timeout=3000)
            except Exception:
                return {"success": False, "error": "Connect button not found — may be Follow-only profile"}

        await connect_btn.click()
        await asyncio.sleep(1)

        # Add note if dialog appeared
        if connection_note:
            try:
                add_note_btn = await page.wait_for_selector("button[aria-label='Add a note']", timeout=3000)
                await add_note_btn.click()
                await asyncio.sleep(0.5)

                note_input = await page.wait_for_selector("textarea#custom-message", timeout=3000)
                for char in connection_note[:299]:
                    await page.keyboard.type(char)
                    await human_type_delay()
            except Exception:
                pass  # Note dialog may not always appear

        await human_pause()

        # Click Send
        send_selectors = [
            "button[aria-label='Send now']",
            "button[aria-label='Send invitation']",
            "button.ml1",
        ]
        for selector in send_selectors:
            try:
                send_btn = await page.wait_for_selector(selector, timeout=3000)
                if send_btn:
                    await send_btn.click()
                    break
            except Exception:
                continue

        await asyncio.sleep(2)
        record_action(user_id, "connection_send")
        return {"success": True, "message": "Connection request sent"}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await browser.close()
        await playwright.stop()
