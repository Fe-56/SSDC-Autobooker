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


def load_preferences(path: Path):
    """Load saved booking preferences from config file."""
    cfg = configparser.ConfigParser()
    cfg.read(path)

    if 'preferences' not in cfg:
        return {'desired_dates': [], 'preferred_sessions': []}

    prefs = cfg['preferences']

    # Parse saved dates (format: "01/01/2026,02/01/2026,...")
    saved_dates_str = prefs.get('desired_dates', '')
    desired_dates = []
    if saved_dates_str:
        try:
            for date_str in saved_dates_str.split(','):
                date_str = date_str.strip()
                if date_str:
                    desired_dates.append(
                        datetime.strptime(date_str, '%d/%m/%Y'))
        except ValueError as e:
            print(f"[Config] Error parsing saved dates: {e}")

    # Parse saved sessions (format: "1,2,3,4,5")
    saved_sessions_str = prefs.get('preferred_sessions', '')
    preferred_sessions = []
    if saved_sessions_str:
        try:
            preferred_sessions = [
                int(s.strip()) for s in saved_sessions_str.split(',') if s.strip()]
        except ValueError as e:
            print(f"[Config] Error parsing saved sessions: {e}")

    return {
        'desired_dates': desired_dates,
        'preferred_sessions': preferred_sessions
    }


def save_preferences(path: Path, desired_dates, preferred_sessions):
    """Save booking preferences to config file."""
    cfg = configparser.ConfigParser()
    cfg.read(path)

    if 'preferences' not in cfg:
        cfg['preferences'] = {}

    # Format dates as "01/01/2026,02/01/2026,..."
    dates_str = ','.join([d.strftime('%d/%m/%Y') for d in desired_dates])
    cfg['preferences']['desired_dates'] = dates_str

    # Format sessions as "1,2,3,4,5"
    sessions_str = ','.join(str(s) for s in sorted(set(preferred_sessions)))
    cfg['preferences']['preferred_sessions'] = sessions_str

    with path.open('w') as f:
        cfg.write(f)
    try:
        path.chmod(0o600)
    except Exception:
        pass

    print("[Config] Preferences saved")


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

        # Booking conditions - collect user preferences with caching
        print("[Booking] Gathering booking preferences...")

        # Load previously saved preferences
        saved_prefs = load_preferences(cfg_path)
        saved_desired_dates = saved_prefs['desired_dates']
        saved_preferred_sessions = saved_prefs['preferred_sessions']

        desired_dates = []
        preferred_sessions = []

        # Check if we have saved preferences and ask user
        if saved_desired_dates or saved_preferred_sessions:
            print("\nPreviously saved preferences found:")
            if saved_desired_dates:
                print(
                    f"  Dates: {[d.strftime('%d %b %Y') for d in saved_desired_dates]}")
            if saved_preferred_sessions:
                print(f"  Sessions: {sorted(saved_preferred_sessions)}")

            while True:
                use_saved = input(
                    "\nDo you want to use the same preferences? (yes/no): ").lower()
                if use_saved in ('yes', 'y'):
                    desired_dates = saved_desired_dates
                    preferred_sessions = saved_preferred_sessions
                    print("[Booking] Using saved preferences")
                    break
                elif use_saved in ('no', 'n'):
                    print("[Booking] Will prompt for new preferences")
                    break
                else:
                    print("Please enter 'yes' or 'no'")

        # If not using saved preferences or none exist, prompt for new ones
        if not desired_dates:
            # Get desired dates
            while True:
                date_input = input(
                    "Enter a date you want to book (eg. 01 Jan 2026), or 'done' to finish: ")
                if date_input.lower() == 'done':
                    if not desired_dates:
                        print("Please enter at least one date")
                        continue
                    break
                try:
                    test_date = datetime.strptime(date_input, '%d %b %Y')
                    present = datetime.now()
                    if test_date.date() < present.date():
                        print("Invalid date - cannot book in the past")
                        continue
                    desired_dates.append(test_date)
                    print(f"Added date: {date_input}")
                except ValueError:
                    print("Wrong date format, please use 'dd Mon YYYY' format")
                    continue

            print(
                f"Desired dates: {[d.strftime('%d %b %Y') for d in desired_dates]}")

        if not preferred_sessions:
            # Get preferred session timings
            print("\nAvailable sessions:")
            print(
                "Weekdays (Mon-Fri): 1=8:00am, 2=9:50am, 3=12:15pm, 4=2:05pm, 5=3:55pm, 6=6:20pm, 7=8:10pm")
            print("Weekends (Sat-Sun): 1=8:00am, 2=9:50am, 3=12:15pm, 4=2:05pm, 5=3:55pm")

            while True:
                session_input = input(
                    "Enter preferred session numbers (1-7 separated by spaces), or 'done' to finish: ")
                if session_input.lower() == 'done':
                    if not preferred_sessions:
                        print("Please enter at least one session")
                        continue
                    break
                try:
                    sessions = [int(x) for x in session_input.split()]
                    valid = True
                    for s in sessions:
                        if s < 1 or s > 7:
                            print(
                                f"Invalid session number: {s}. Please enter 1-7")
                            valid = False
                            break
                    if valid:
                        preferred_sessions.extend(sessions)
                        preferred_sessions = list(set(preferred_sessions))
                        print(
                            f"Preferred sessions: {sorted(preferred_sessions)}")
                        break
                except ValueError:
                    print("Please enter valid numbers separated by spaces")
                    continue

        print(f"\n[Booking] Preferences set:")
        print(f"  Dates: {[d.strftime('%d %b %Y') for d in desired_dates]}")
        print(f"  Sessions: {sorted(preferred_sessions)}")

        # Save preferences for next time
        save_preferences(cfg_path, desired_dates, preferred_sessions)

        # Solve CAPTCHA before form submission
        print("\n[Booking] Solving CAPTCHA for booking form...")
        try:
            driver.solve_captcha()
            print("[Booking] CAPTCHA solved")
        except Exception as e:
            print(
                f"[Booking] CAPTCHA solve skipped or failed (may not be present): {e}")

        driver.sleep(1)

        # Click "Get The Earliest Date" button
        # Click "Get The Earliest Date" button with infinite retry logic for fully booked slots
        print("[Booking] Attempting to get earliest available date...")
        print("[Booking] Bot will keep retrying until an available date is found or script is stopped...")
        import random
        retry_count = 0
        earliest_date_obtained = False

        while not earliest_date_obtained:
            retry_count += 1
            print(
                f"\n[Booking] Attempt {retry_count}: Clicking 'Get The Earliest Date' button...")
            try:
                driver.uc_click("#button-searchDate")
                driver.sleep(2)

                # Check for "All the slots are Fully Booked" pop-up
                fully_booked = False
                try:
                    # Try to detect the fully booked message
                    driver.assert_text(
                        "All the slots are Fully Booked", timeout=2)
                    fully_booked = True
                except Exception:
                    # Message not found, assume table is loading or will appear
                    pass

                if fully_booked:
                    print(
                        "[Booking] Pop-up detected: All slots are fully booked. Closing pop-up...")
                    # Click on the "Close" button in the pop-up
                    try:
                        # Try multiple selectors for the close button
                        close_button_found = False
                        close_selectors = [
                            "button:contains('Close')",
                            "//button[contains(text(), 'Close')]",
                            "//div[@class='modal-footer']/button[1]",
                            "button[data-dismiss='modal']"
                        ]

                        for selector in close_selectors:
                            try:
                                driver.uc_click(selector)
                                close_button_found = True
                                print(
                                    "[Booking] Close button clicked successfully")
                                break
                            except Exception:
                                continue

                        if not close_button_found:
                            print(
                                "[Booking] Warning: Could not find close button, proceeding with wait anyway")
                    except Exception as close_e:
                        print(
                            f"[Booking] Error clicking close button: {close_e}")

                    wait_time = random.randint(15, 30)
                    print(
                        f"[Booking] Waiting {wait_time} seconds before retrying...")
                    driver.sleep(wait_time)
                    continue
                else:
                    # No fully booked message, assume we got a date
                    print("[Booking] Earliest date obtained successfully")
                    earliest_date_obtained = True
                    break

            except Exception as e:
                print(f"[Booking] Error during Get Earliest Date attempt: {e}")
                wait_time = random.randint(10, 20)
                print(f"[Booking] Retrying in {wait_time} seconds...")
                driver.sleep(wait_time)

        # Check if the dropdown date matches any of the desired dates
        print("[Booking] Checking lesson date...")
        lesson_date_found = False

        try:
            lesson_date_value = driver.get_value("#SelectedDate")
            print(
                f"[Booking] Current lesson date in dropdown: {lesson_date_value}")

            # Parse the lesson date and check if it's in desired dates
            try:
                lesson_date = datetime.strptime(lesson_date_value, '%d/%m/%Y')

                for desired_date in desired_dates:
                    if lesson_date.date() == desired_date.date():
                        lesson_date_found = True
                        print(
                            f"[Booking] Lesson date {lesson_date_value} matches desired date!")
                        break
            except ValueError as e:
                print(f"[Booking] Error parsing lesson date: {e}")
        except Exception as e:
            print(f"[Booking] Error reading lesson date: {e}")

        if not lesson_date_found:
            print(
                f"[Booking] Lesson date does not match any desired dates. Skipping availability check.")
        else:
            # Click "Check for Availability" button
            print("[Booking] Clicking 'Check for Availability' button...")
            try:
                driver.uc_click("#btn_checkforava")
                driver.sleep(2)

                # Handle Cloudflare challenge if needed
                handle_cloudflare_challenge(driver)
                driver.sleep(1)

                # Now a table should be displayed with available slots
                print(
                    "[Booking] Table loaded. Searching for available slots matching user preferences...")

                booked_count = 0
                max_bookings = 20

                # Parse the availability table in a structured way
                try:
                    # Wait for the table header to be present
                    driver.wait_for_element("//table//thead", timeout=5)

                    # Read session numbers from the header (skip first 'Session Date' col)
                    header_elems = driver.find_elements("//table//thead//th")
                    session_numbers = []
                    if len(header_elems) > 1:
                        for he in header_elems[1:]:
                            txt = he.text.strip()
                            try:
                                # header usually contains the session number (e.g. '1')
                                num = int(txt.split()[0])
                            except Exception:
                                # fallback: extract digits
                                digits = ''.join(
                                    [c for c in txt if c.isdigit()])
                                try:
                                    num = int(digits) if digits else None
                                except Exception:
                                    num = None
                            session_numbers.append(num)

                    # Iterate rows (each row is a date)
                    rows = driver.find_elements("//table//tbody//tr")
                    print(f"[Booking] Found {len(rows)} date rows in table")

                    for r_idx, _ in enumerate(rows, start=1):
                        try:
                            # Extract the date shown in the row (from the <th><a> element)
                            date_xpath = f"//table//tbody//tr[{r_idx}]//th//a"
                            try:
                                date_text = driver.find_element(
                                    date_xpath).text.strip()
                            except Exception:
                                # If not found, skip this row
                                continue

                            try:
                                row_date = datetime.strptime(
                                    date_text, '%d %b %Y')
                            except Exception:
                                print(
                                    f"[Booking] Could not parse row date '{date_text}'")
                                continue

                            # Only consider rows that match desired_dates
                            if not any(row_date.date() == d.date() for d in desired_dates):
                                continue

                            # Iterate each session column in this row
                            tds = driver.find_elements(
                                f"//table//tbody//tr[{r_idx}]//td")
                            for col_idx, td in enumerate(tds, start=1):
                                try:
                                    td_text = td.text.strip().lower()
                                except Exception:
                                    td_text = ''

                                # Skip 'n/a' or empty cells
                                if 'n/a' in td_text or td_text == '':
                                    continue

                                # Map column index to session number (if parsed from header)
                                session_num = None
                                if session_numbers and col_idx <= len(session_numbers):
                                    session_num = session_numbers[col_idx - 1]
                                else:
                                    session_num = col_idx

                                # Skip if this session number is not in preferred_sessions
                                if preferred_sessions and session_num not in preferred_sessions:
                                    print(
                                        f"[Booking] Slot available for session {session_num} on {date_text}, but not preferred")
                                    continue

                                # Build xpath for this cell and attempt to click it (prefer link inside cell)
                                cell_xpath = f"//table//tbody//tr[{r_idx}]//td[{col_idx}]"
                                try:
                                    try:
                                        driver.uc_click(cell_xpath + "//a")
                                    except Exception:
                                        driver.uc_click(cell_xpath)

                                    driver.sleep(0.5)

                                    # Handle confirmation modal if it appears
                                    try:
                                        driver.wait_for_element(
                                            "//div[@class='modal-footer']/button[1]", timeout=5)
                                        driver.click(
                                            "//div[@class='modal-footer']/button[1]")
                                        booked_count += 1
                                        print(
                                            f"[Booking] Booking confirmed! ({booked_count} total) for {date_text} session {session_num}")

                                        # Send confirmation email if enabled
                                        msg.set_content(
                                            f'A car lesson slot has been booked. Please login to confirm your booking within 40 mins.'
                                        )
                                        if email_pref == "y" and EMAIL_ADDRESS:
                                            try:
                                                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                                                    smtp.login(
                                                        EMAIL_ADDRESS, EMAIL_PASSWORD)
                                                    smtp.send_message(msg)
                                                print(
                                                    f"[Email] Confirmation sent to {EMAIL_ADDRESS}")
                                            except Exception as e:
                                                print(
                                                    f"[Email] Failed to send email: {e}")
                                    except Exception as modal_e:
                                        print(
                                            f"[Booking] No confirmation modal or booking failed: {modal_e}")

                                except Exception as click_e:
                                    print(
                                        f"[Booking] Error clicking session cell: {click_e}")

                                if booked_count >= max_bookings:
                                    break

                            if booked_count >= max_bookings:
                                break

                    if booked_count > 0:
                        print(
                            f"\n[Success] Successfully booked {booked_count} slot(s)!")
                    else:
                        print(
                            "[Booking] No suitable slots found matching your preferences.")

                except Exception as e:
                    print(f"[Booking] Error parsing availability table: {e}")

            except Exception as e:
                print(f"[Booking] Error during availability check: {e}")


if __name__ == "__main__":
    main()
