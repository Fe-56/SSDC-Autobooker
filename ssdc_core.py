import smtplib
import configparser
from getpass import getpass
from pathlib import Path
from email.message import EmailMessage
from datetime import datetime


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


def send_confirmation_email(email_address: str, email_password: str, subject: str, body: str):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = email_address
    msg['To'] = email_address
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_address, email_password)
            smtp.send_message(msg)
        print(f"[Email] Confirmation sent to {email_address}")
    except Exception as e:
        print(f"[Email] Failed to send email: {e}")


def parse_and_book_availability(driver, desired_dates, preferred_sessions, email_pref, email_address, email_password, max_bookings=20):
    """Parse the availability table and attempt to book matching slots.

    Returns the number of successful bookings.
    """
    booked_count = 0

    # Wait for the table header to be present
    driver.wait_for_element("//table//thead", timeout=5)

    # Read session numbers from the header (skip first 'Session Date' col)
    header_elems = driver.find_elements("//table//thead//th")
    session_numbers = []
    if len(header_elems) > 1:
        for he in header_elems[1:]:
            txt = he.text.strip()
            try:
                num = int(txt.split()[0])
            except Exception:
                digits = ''.join([c for c in txt if c.isdigit()])
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
            date_xpath = f"//table//tbody//tr[{r_idx}]//th//a"
            try:
                date_text = driver.find_element(date_xpath).text.strip()
            except Exception:
                continue

            try:
                row_date = datetime.strptime(date_text, '%d %b %Y')
            except Exception:
                print(f"[Booking] Could not parse row date '{date_text}'")
                continue

            # Only consider rows that match desired_dates
            if not any(row_date.date() == d.date() for d in desired_dates):
                continue

            # Iterate each session column in this row
            tds = driver.find_elements(f"//table//tbody//tr[{r_idx}]//td")
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
                        driver.click("//div[@class='modal-footer']/button[1]")
                        booked_count += 1
                        print(
                            f"[Booking] Booking confirmed! ({booked_count} total) for {date_text} session {session_num}")

                        # Send confirmation email if enabled
                        if email_pref == "y" and email_address:
                            send_confirmation_email(email_address, email_password,
                                                    'Car lesson booked',
                                                    'A car lesson slot has been booked. Please login to confirm your booking within 40 mins.')
                    except Exception as modal_e:
                        print(
                            f"[Booking] No confirmation modal or booking failed: {modal_e}")

                except Exception as click_e:
                    print(f"[Booking] Error clicking session cell: {click_e}")

                if booked_count >= max_bookings:
                    break

            if booked_count >= max_bookings:
                break

        except Exception:
            continue

    return booked_count
