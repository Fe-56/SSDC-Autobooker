import smtplib
import argparse
import configparser
from getpass import getpass
from pathlib import Path
from email.message import EmailMessage
from datetime import datetime, timedelta
from seleniumbase import SB

msg = EmailMessage()


def run_setup(path: Path):
    """One-time setup to save credentials securely."""
    cfg = configparser.ConfigParser()
    cfg['credentials'] = {}

    # Email preference and credentials
    while True:
        email_pref = input(
            "Do you want to enable Email notifications (y/n)?: ")
        if email_pref in ('y', 'n'):
            break
        print("Invalid input, enter y/n")

    cfg['credentials']['email_pref'] = email_pref
    if email_pref == 'y':
        while True:
            EMAIL_ADDRESS = input("Enter your gmail: ")
            EMAIL_PASSWORD = getpass("Enter your password: ")
            try:
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                    smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                cfg['credentials']['email_address'] = EMAIL_ADDRESS
                cfg['credentials']['email_password'] = EMAIL_PASSWORD
                break
            except smtplib.SMTPAuthenticationError:
                print("Username or password incorrect please try again.")
                continue

    # Site login credentials
    username = input("Enter your Student ID: ")
    password = getpass("Enter your password: ")
    name = input("Enter your name (for verification purposes): ")
    cfg['credentials']['username'] = username
    cfg['credentials']['password'] = password
    cfg['credentials']['name'] = name

    # Write config file with restricted permissions
    with path.open('w') as f:
        cfg.write(f)
    try:
        path.chmod(0o600)
    except Exception:
        pass
    print(f"Saved config to {path}")


def load_creds(path: Path):
    """Load credentials from config file."""
    cfg = configparser.ConfigParser()
    cfg.read(path)
    return cfg['credentials'] if 'credentials' in cfg else {}


def handle_cloudflare_challenge(driver, max_retries=3):
    """
    Handle Cloudflare challenge with seleniumbase.
    Attempts to solve CAPTCHA and wait for CF verification to complete.
    """
    print("[CF Bypass] Checking for Cloudflare challenge...")
    current_url = driver.get_current_url()
    print(f"[CF Bypass] Current URL: {current_url}")

    # Check multiple indicators of Cloudflare challenge
    is_cf_challenge = "challenge" in current_url
    has_cf_iframe = False
    has_cf_container = False

    try:
        has_cf_iframe = driver.is_element_present(
            "iframe[src*='challenges.cloudflare.com']")
    except Exception as e:
        print(f"[CF Bypass] Error checking CF iframe: {e}")

    try:
        has_cf_container = driver.is_element_present(
            "div#challenge-form, div[id*='cf_'], body.no-js")
    except Exception as e:
        print(f"[CF Bypass] Error checking CF container: {e}")

    if not is_cf_challenge and not has_cf_iframe and not has_cf_container:
        print("[CF Bypass] No Cloudflare challenge detected")
        return True

    print(
        f"[CF Bypass] Cloudflare challenge detected (URL 'challenge': {is_cf_challenge}, CF iframe: {has_cf_iframe}, CF container: {has_cf_container})")

    for attempt in range(max_retries):
        try:
            # Wait longer for any CF JS to execute and render
            driver.sleep(3)

            # Try to solve CAPTCHA if present
            try:
                print(
                    f"[CF Bypass] Attempting to solve CAPTCHA (attempt {attempt + 1}/{max_retries})")
                driver.solve_captcha()
                print("[CF Bypass] CAPTCHA solved successfully")
            except Exception as e:
                print(
                    f"[CF Bypass] No CAPTCHA to solve or already solved: {e}")

            # Wait longer for CF verification to complete
            driver.sleep(5)

            # Check if challenge is gone
            current_url = driver.get_current_url()
            is_cf_challenge = "challenge" in current_url
            has_cf_iframe = False
            has_cf_container = False

            try:
                has_cf_iframe = driver.is_element_present(
                    "iframe[src*='challenges.cloudflare.com']")
            except Exception:
                pass

            try:
                has_cf_container = driver.is_element_present(
                    "div#challenge-form, div[id*='cf_'], body.no-js")
            except Exception:
                pass

            if not is_cf_challenge and not has_cf_iframe and not has_cf_container:
                print("[CF Bypass] Cloudflare challenge passed")
                return True
            else:
                print(
                    f"[CF Bypass] Challenge still present after attempt {attempt + 1}. Retrying...")

        except Exception as e:
            print(f"[CF Bypass] Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                driver.sleep(2)

    print("[CF Bypass] Failed to bypass Cloudflare after max retries")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--setup', action='store_true',
                        help='Run one-time setup to save credentials')
    parser.add_argument('--dry-run', action='store_true',
                        help='Load config and exit (no Selenium)')
    parser.add_argument('--config', type=str,
                        help='Path to config file (default ~/.ssdc_autobooker.cfg)')
    args = parser.parse_args()

    cfg_path = Path(args.config) if args.config else Path.home() / \
        '.ssdc_autobooker.cfg'

    # If doing a dry-run and config doesn't exist, report and exit
    if args.dry_run and not cfg_path.exists():
        print(f"Config file not found at {cfg_path}")
        raise SystemExit(1)

    # Run setup if requested or if config missing
    if args.setup or (not cfg_path.exists() and not args.dry_run):
        run_setup(cfg_path)

    creds = load_creds(cfg_path)

    # Handle dry-run: show loaded config (mask passwords) and exit
    if args.dry_run:
        def mask(s):
            return '***' if s else ''

        print("Dry-run: loaded configuration:")
        print(f"  email_pref: {creds.get('email_pref', 'n')}")
        print(f"  email_address: {creds.get('email_address', '')}")
        print(f"  email_password: {mask(creds.get('email_password', ''))}")
        print(f"  username: {creds.get('username', '')}")
        print(f"  password: {mask(creds.get('password', ''))}")
        return

    # Initialize seleniumbase with undetected-chromedriver for CF bypass
    with SB(uc=True, locale="en", incognito=True, ) as driver:
        print("[Init] Starting SSDC Autobooker with Cloudflare bypass enabled")

        # Navigate to login page with CF handling
        driver.activate_cdp_mode("https://www.ssdcl.com.sg/User/Login")
        driver.sleep(3)

        # Handle initial Cloudflare challenge on login page
        handle_cloudflare_challenge(driver)
        driver.sleep(1)

        # Extract credentials
        email_pref = creds.get('email_pref', 'n')
        EMAIL_ADDRESS = creds.get('email_address', '')
        EMAIL_PASSWORD = creds.get('email_password', '')

        if email_pref == 'y' and EMAIL_ADDRESS:
            msg['Subject'] = 'Car lesson booked'
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = EMAIL_ADDRESS

        # Get login credentials
        username = creds.get('username', None)
        password = creds.get('password', None)
        if username is None or password is None:
            username = input("Enter your Student ID: ")
            password = getpass("Enter your password: ")

        # Perform login with CF handling (modern: check for name, no error modal)
        print("[Login] Attempting to log in...")
        login_success = False
        max_login_retries = 3
        name = creds.get('name')
        for login_retry_count in range(max_login_retries):
            # Prompt for credentials if not present
            if not username or not password:
                username = input("Enter your Student ID: ")
                password = getpass("Enter your password: ")

            # Enter credentials using SeleniumBase
            driver.type("#UserName", username)
            driver.type("#Password", password)
            driver.uc_click("button[type='submit']")

            # # Wait for potential Cloudflare challenge after login attempt
            # handle_cloudflare_challenge(driver)

            # Wait for login to process
            driver.sleep(2)

            # Check for successful login by presence of name using assert_text
            if name:
                try:
                    driver.assert_text(name.upper(), timeout=5)
                    print(
                        f"[Login] Login successful. Name '{name.upper()}' found on page.")
                    login_success = True
                    break
                except Exception:
                    print(
                        f"[Login] Name '{name.upper()}' not found on page. Retrying login...")
                    continue
            else:
                print(
                    "[Login] No name provided in credentials for verification. Assuming login failed.")
                continue

        if not login_success:
            print("[Error] Login failed after max retries")
            return

        # Re-activate CDP mode for the new page to ensure undetected-chromedriver is active
        current_url = driver.get_current_url()
        print(f"[Navigation] New URL after Proceed: {current_url}")
        driver.activate_cdp_mode(current_url)

        # handle_cloudflare_challenge(driver)
        # driver.sleep(1)

        # Navigate to booking page
        print("[Navigation] Navigating to booking page...")
        driver.uc_click("//a[@href='/User/Booking/BookingList']")
        driver.sleep(2)
        # handle_cloudflare_challenge(driver)
        # driver.sleep(1)

        print("[Navigation] Navigating to new booking form...")
        driver.uc_click("a:contains('New Booking')")
        driver.sleep(2)
        # handle_cloudflare_challenge(driver)
        # driver.sleep(1)

        print("[Navigation] Accepting terms and conditions...")
        driver.uc_click("#chkProceed")
        # handle_cloudflare_challenge(driver)
        # driver.sleep(1)

        print("[Navigation] Proceeding to booking form...")
        driver.uc_click("a:contains('Proceed')")
        driver.sleep(2)

        # # Re-activate CDP mode for the new page to ensure undetected-chromedriver is active
        # current_url = driver.get_current_url()
        # print(f"[Navigation] New URL after Proceed: {current_url}")
        # driver.activate_cdp_mode(current_url)
        # driver.sleep(2)

        # # Handle Cloudflare challenge on booking form page
        # handle_cloudflare_challenge(driver)
        # driver.sleep(2)

        # Booking conditions - date selection
        print("[Booking] Gathering booking preferences...")
        while True:
            input_date = input("Enter date (eg. 01 Jan 2020): ")
            date_pref = input("Do you want to enable 7 day range (y/n): ")
            present = datetime.now()
            date_list_actual = []

            if date_pref == "y":
                try:
                    test_date = datetime.strptime(input_date, '%d %b %Y')
                    date_list = [test_date +
                                 timedelta(days=x) for x in range(7)]
                    for d in date_list:
                        if d.date() < present.date():
                            print("Invalid date please try again")
                            continue
                        else:
                            base_date = d.strftime('%#d/%#m/%Y')
                            date_list_actual.append(base_date)
                    break
                except ValueError:
                    print("Wrong date format")
                    continue

            elif date_pref == "n":
                try:
                    test_date = datetime.strptime(input_date, '%d %b %Y')
                    if test_date < present:
                        print("Invalid date please try again")
                        continue
                except ValueError:
                    print("Wrong date format")
                    continue
                else:
                    id_date = test_date.strftime('%#d/%#m/%Y')
                    break
            else:
                print("Invalid input please enter y/n")
                continue

        # Session number selection
        id_list = []
        while True:
            try:
                x = [int(x) for x in input(
                    "Enter your session number (1-6 separated by whitespace): ").split()]
                for a in x:
                    if a < 1 or a > 6:
                        print("Enter valid numbers")
                        continue
                    elif date_pref == "n":
                        id = str(a) + "_" + id_date
                        id_list.append(id)
                    elif date_pref == "y":
                        for id_date in date_list_actual:
                            id = str(a) + "_" + id_date
                            id_list.append(id)
                break
            except ValueError:
                print("Enter valid numbers")
                continue

        # Solve CAPTCHA before form submission
        print("[Booking] Solving CAPTCHA for booking form...")
        try:
            driver.solve_captcha()
            print("[Booking] CAPTCHA solved")
        except Exception as e:
            print(
                f"[Booking] CAPTCHA solve skipped or failed (may not be present): {e}")

        driver.sleep(1)

        # Fill in date and location
        location = "Woodlands"
        print("[Booking] Filling in booking form...")
        driver.type("#SelectedDate", input_date)
        driver.select_option_by_value("#SelectedLocation", location)
        driver.sleep(1)

        # Click "Check for Availability" button
        print("[Booking] Checking for availability...")
        driver.uc_click("#btn_checkforava")
        driver.sleep(3)

        # Handle Cloudflare challenge on availability check
        handle_cloudflare_challenge(driver)
        driver.sleep(2)

        # Booking loop - find and book available slots
        print("[Booking] Starting slot booking loop...")
        booking_attempt_count = 0
        max_attempts = 50

        while len(id_list) != 0 and booking_attempt_count < max_attempts:
            booking_attempt_count += 1
            print(
                f"[Booking] Attempt {booking_attempt_count}: Looking for {len(id_list)} slots")

            try:
                driver.scroll_to(0, 800)

                # Build XPath for available slots
                booking_conditions = " or ".join(
                    [f"contains(@id, '{keyword}')" for keyword in id_list]
                )
                expression = f"//*[{booking_conditions}]"

                # Find the booking slot
                driver.wait_for_element(expression, timeout=5)
                slot_id = driver.get_attribute(expression, "id")

                # Remove booked slot from list
                for id in id_list[:]:
                    if id in slot_id:
                        id_list.remove(id)
                        print(f"[Booking] Found slot: {slot_id}")

                # Click on the slot
                driver.uc_click(expression)
                driver.sleep(1)

                # Wait for confirmation modal and close it
                driver.wait_for_element(
                    "//div[@class='modal-footer']/button[1]", timeout=10)
                driver.click("//div[@class='modal-footer']/button[1]")

                # Send confirmation email if enabled
                msg.set_content(
                    f'A class of id {slot_id} has been booked, please login to confirm your booking within 40 mins'
                )
                if email_pref == "y" and EMAIL_ADDRESS:
                    try:
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                            smtp.send_message(msg)
                        print(f"[Email] Confirmation sent to {EMAIL_ADDRESS}")
                    except Exception as e:
                        print(f"[Email] Failed to send email: {e}")

                # If more slots to book, refresh and continue
                if len(id_list) != 0:
                    driver.uc_click("#btn_checkforava")
                    driver.sleep(2)
                    handle_cloudflare_challenge(driver)
                    driver.sleep(1)

            except Exception as e:
                print(
                    f"[Booking] Exception on attempt {booking_attempt_count}: {e}")
                # Refresh page and retry
                driver.refresh()
                driver.sleep(2)
                handle_cloudflare_challenge(driver)
                driver.sleep(1)

        if len(id_list) == 0:
            print("[Success] All sessions booked successfully!")
        else:
            print(
                f"[Warning] Booking loop ended with {len(id_list)} slots still remaining")


if __name__ == "__main__":
    main()
