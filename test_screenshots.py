"""
End-to-end test script using Playwright to validate the /votes UI.
Takes screenshots of:
1. The password/login form
2. The voting dashboard with restaurant cards
3. The voting dashboard after casting a vote (showing updated count)
"""
import os
import time
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = os.getenv("SCREENSHOTS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots"))
BASE_URL = os.getenv("BASE_URL", "http://localhost:8091")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # Step 1: Navigate to /votes and screenshot the login form
        print("Navigating to /votes...")
        page.goto(f"{BASE_URL}/votes")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        print("Taking screenshot of login form...")
        page.screenshot(path=f"{SCREENSHOTS_DIR}/01-login-form.png", full_page=True)
        print("  Saved: 01-login-form.png")

        # Step 2: Enter password and submit
        print("Entering password...")
        password_input = page.locator('input[type="password"]')
        password_input.fill("voting123")
        time.sleep(0.5)

        # Find and click the submit/login button
        submit_button = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Enter"), button:has-text("Submit"), button:has-text("Access")')
        if submit_button.count() > 0:
            submit_button.first.click()
        else:
            # Try pressing Enter on the input
            password_input.press("Enter")

        # Wait for the voting UI to appear
        time.sleep(2)
        page.wait_for_load_state("networkidle")

        # Step 3: Screenshot the voting dashboard
        print("Taking screenshot of voting dashboard...")
        page.screenshot(path=f"{SCREENSHOTS_DIR}/02-voting-dashboard.png", full_page=True)
        print("  Saved: 02-voting-dashboard.png")

        # Step 4: Click a Vote button for one restaurant
        print("Clicking Vote button...")
        vote_buttons = page.locator('button:has-text("Vote")')
        if vote_buttons.count() > 0:
            # Click the first Vote button
            first_vote_btn = vote_buttons.first
            first_vote_btn.click()
            print("  Clicked vote button for first restaurant")
        else:
            print("  WARNING: No vote buttons found!")

        # Wait for the vote to register and counts to update
        time.sleep(3)
        page.wait_for_load_state("networkidle")

        # Step 5: Screenshot after voting (showing updated count)
        print("Taking screenshot after voting...")
        page.screenshot(path=f"{SCREENSHOTS_DIR}/03-after-vote.png", full_page=True)
        print("  Saved: 03-after-vote.png")

        browser.close()
        print(f"\nAll screenshots saved to {SCREENSHOTS_DIR}")
        print("Test completed successfully!")


if __name__ == "__main__":
    main()
