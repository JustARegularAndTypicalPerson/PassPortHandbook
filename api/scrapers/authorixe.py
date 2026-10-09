import os
from playwright.sync_api import sync_playwright, Page, expect, Locator
import re # For regex in button names

# --- Configuration ---
LOGIN_TEXT = os.environ.get("YANDEX_LOGIN", "")
PASSWORD_TEXT = os.environ.get("YANDEX_PASSWORD", "")
HEADLESS_MODE = True # Set to True for no browser UI, False for manual CAPTCHA
MAX_CAPTCHA_RETRIES = 3

# --- URLs ---
INITIAL_AUTH_URL = "https://passport.yandex.ru/auth"
LOGIN_FORM_URL = "https://passport.yandex.ru/auth/add/login" # Target after CAPTCHA
ACCOUNT_LIST_URL_FRAGMENT = "https://passport.yandex.ru/auth/list"
AUTH_ADD_FLOW_URL_FRAGMENT = "https://passport.yandex.ru/auth/add" # Intermediate page
SUCCESS_URL_INDICATOR = "https://passport.yandex.ru/profile"
FALLBACK_SUCCESS_URL_INDICATOR = "https://yandex.ru"

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_persistent_context_dir = os.path.abspath(
    os.path.join(_project_root, "organizations_files", "playwright_yandex_context")
)

def check_and_handle_captcha(page: Page) -> bool:
    """
    Checks for CAPTCHA. If present, prompts user to solve it, 
    then attempts to navigate to LOGIN_FORM_URL.
    Returns True if not on CAPTCHA page after handling, False otherwise.
    """
    retries = 0
    initial_url_before_captcha_check = page.url

    while "showcaptcha" in page.url.lower() and retries < MAX_CAPTCHA_RETRIES:
        retries += 1
        print(f"CAPTCHA detected at {page.url} (Attempt {retries}/{MAX_CAPTCHA_RETRIES}).")
        print("Please solve the CAPTCHA in the browser.")
        input("Press Enter after solving the CAPTCHA to continue...")
        
        print(f"After CAPTCHA, attempting to navigate to: {LOGIN_FORM_URL}")
        try:
            page.goto(LOGIN_FORM_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000) # Give page a moment to settle
        except Exception as e:
            print(f"Error navigating to {LOGIN_FORM_URL} after CAPTCHA: {e}")
            # Continue to check if still on CAPTCHA

        if "showcaptcha" not in page.url.lower():
            print(f"Successfully navigated away from CAPTCHA. Current URL: {page.url}")
            return True # CAPTCHA handled
    
    if "showcaptcha" in page.url.lower():
        print(f"Failed to resolve CAPTCHA after {retries} attempts. Still at {page.url}")
        return False # CAPTCHA still present
    
    # If no CAPTCHA was present from the start of this function call
    if initial_url_before_captcha_check == page.url and "showcaptcha" not in initial_url_before_captcha_check.lower():
        return True 

    return True

def click_button(page: Page, locator: Locator, description: str):
    print(f"Clicking '{description}'...")
    expect(locator).to_be_visible(timeout=10000)
    expect(locator).to_be_enabled(timeout=5000)
    locator.click()
    page.wait_for_timeout(1500) # Allow for navigation/JS execution
    if not check_and_handle_captcha(page): # Check CAPTCHA after click
        raise Exception(f"Unhandled CAPTCHA after clicking '{description}'. Current URL: {page.url}")

def fill_input(page: Page, locator: Locator, value: str, description: str):
    print(f"Filling '{description}' with '{value if description !='password' else '********'}'.")
    expect(locator).to_be_visible(timeout=10000)
    expect(locator).to_be_enabled(timeout=5000)
    locator.fill(value)

with sync_playwright() as p:
    print("Launching browser...")
    browser = p.chromium.launch_persistent_context(_persistent_context_dir, headless=HEADLESS_MODE)
    page = browser.new_page()
    page.set_default_timeout(20000)

    try:
        print(f"Navigating to initial auth page: {INITIAL_AUTH_URL}")
        page.goto(INITIAL_AUTH_URL, wait_until="domcontentloaded")
        if not check_and_handle_captcha(page): # Handles CAPTCHA and tries to go to LOGIN_FORM_URL
            raise Exception(f"Could not proceed from initial auth page due to CAPTCHA. Current URL: {page.url}")

        current_url = page.url
        print(f"Current URL after initial load & CAPTCHA check: {current_url}")

        # --- Navigate to LOGIN_FORM_URL if not already there ---
        if LOGIN_FORM_URL not in current_url:
            if ACCOUNT_LIST_URL_FRAGMENT in current_url:
                print("On account list page.")
                account_to_select_locator = page.get_by_text(LOGIN_TEXT, exact=False).first
                if account_to_select_locator.is_visible(timeout=3000):
                    print(f"Found account '{LOGIN_TEXT}' in the list. Clicking it.")
                    clickable_ancestor = account_to_select_locator.locator("xpath=ancestor-or-self::*[self::a or self::button or @role='button'][1]")
                    click_button(page, clickable_ancestor, f"account '{LOGIN_TEXT}'")
                else:
                    print(f"Account '{LOGIN_TEXT}' not found. Navigating to login form: {LOGIN_FORM_URL}")
                    page.goto(LOGIN_FORM_URL, wait_until="domcontentloaded")
                    if not check_and_handle_captcha(page): raise Exception(f"CAPTCHA on nav to {LOGIN_FORM_URL}")
            
            elif AUTH_ADD_FLOW_URL_FRAGMENT in current_url: 
                print("On 'add account' intermediate page. Clicking through to login form.")
                more_options_button = page.locator("#passp:exp-register")
                if more_options_button.is_visible(timeout=3000):
                    click_button(page, more_options_button, "Ещё (More options)")
                
                login_by_username_button = page.get_by_text("Войти по логину", exact=True)
                click_button(page, login_by_username_button, "Войти по логину")
                if LOGIN_FORM_URL not in page.url and "showcaptcha" not in page.url.lower():
                    print(f"Warning: Not on {LOGIN_FORM_URL} after 'Войти по логину'. Current: {page.url}. Attempting direct nav.")
                    page.goto(LOGIN_FORM_URL, wait_until="domcontentloaded")
                    if not check_and_handle_captcha(page): raise Exception(f"CAPTCHA on corrective nav to {LOGIN_FORM_URL}")

            elif INITIAL_AUTH_URL == current_url.split('?')[0].rstrip('/'): 
                print(f"On bare auth page. Navigating to login form: {LOGIN_FORM_URL}")
                page.goto(LOGIN_FORM_URL, wait_until="domcontentloaded")
                if not check_and_handle_captcha(page): raise Exception(f"CAPTCHA on nav to {LOGIN_FORM_URL}")
            
            else: 
                print(f"Unexpected page {current_url}. Attempting to navigate to {LOGIN_FORM_URL}")
                page.goto(LOGIN_FORM_URL, wait_until="domcontentloaded")
                if not check_and_handle_captcha(page): raise Exception(f"CAPTCHA on nav to {LOGIN_FORM_URL}")
        
        current_url = page.url 
        print(f"Ensured navigation towards login form. Current URL: {current_url}")

        # --- Perform Login ---
        login_field_locator = page.locator("#passp-field-login")
        if login_field_locator.is_visible(timeout=3000):
            fill_input(page, login_field_locator, LOGIN_TEXT, "login")
            sign_in_button_locator = page.locator("#passp\\:sign-in")
            click_button(page, sign_in_button_locator, "Sign In after login")
        else:
            print("Login field not visible, assuming password field is next.")

        password_field_locator = page.locator("#passp-field-passwd")
        expect(password_field_locator).to_be_visible(timeout=15000)
        fill_input(page, password_field_locator, PASSWORD_TEXT, "password")

        submit_password_button_locator = page.locator("#passp\\:sign-in")
        if not submit_password_button_locator.is_visible(timeout=3000):
            submit_password_button_locator = page.get_by_role("button", name=re.compile(r"^(Войти|Продолжить|Next)$", re.IGNORECASE)).first
        click_button(page, submit_password_button_locator, "Sign In after password")

        phone_code_field_locator = page.locator("#passp-field-phoneCode")
        if phone_code_field_locator.is_visible(timeout=5000):
            print("Phone code input field appeared.")
            code_from_terminal = input("Пожалуйста, введите код из SMS/приложения: ")
            fill_input(page, phone_code_field_locator, code_from_terminal, "phone code")

            next_button_after_code_locator = page.locator("#passp\\:sign-in")
            if not next_button_after_code_locator.is_visible(timeout=3000):
                 next_button_after_code_locator = page.get_by_role("button", name=re.compile(r"^(Далее|Next|Подтвердить|Confirm)$", re.IGNORECASE)).first
            click_button(page, next_button_after_code_locator, "Next after phone code")
        else:
            print("Phone code input field did not appear.")

        print(f"Checking for successful login. Current URL: {page.url}")
        try:
            page.wait_for_url(
                lambda url: SUCCESS_URL_INDICATOR in url or FALLBACK_SUCCESS_URL_INDICATOR == url.split('?')[0].rstrip('/'),
                timeout=15000
            )
            print(f"Login successful! Final URL: {page.url}")
        except Exception as e:
            print(f"Login might not have been successful or redirection took too long. Error: {e}")
            print(f"Final URL: {page.url}")
            if "showcaptcha" in page.url.lower():
                print("STILL ON CAPTCHA PAGE AT THE END.")
            check_and_handle_captcha(page) # Final attempt if stuck on CAPTCHA

    except Exception as e:
        print(f"AN ERROR OCCURRED: {e}")
        error_screenshot_path = "error_screenshot_authorixe.png"
        try:
            page.screenshot(path=error_screenshot_path)
            print(f"Screenshot saved to {error_screenshot_path}. Current URL: {page.url}")
        except Exception as se:
            print(f"Could not save screenshot: {se}")
    finally:
        print("Script finished.")
        if not HEADLESS_MODE:
            input("Press Enter to close browser...")
        browser.close()
