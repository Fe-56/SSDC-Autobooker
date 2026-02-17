import smtplib
import argparse
from getpass import getpass
from pathlib import Path
from datetime import datetime, timedelta
from seleniumbase import SB

from ssdc_core import (
    run_setup,
    load_creds,
    load_preferences,
    save_preferences,
    handle_cloudflare_challenge,
    parse_and_book_availability,
)


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

                # Delegate parsing & booking to helper to keep main concise
                try:
                    booked_count = parse_and_book_availability(
                        driver,
                        desired_dates,
                        preferred_sessions,
                        email_pref,
                        EMAIL_ADDRESS,
                        EMAIL_PASSWORD,
                        max_bookings=20,
                    )

                    if booked_count > 0:
                        print(
                            f"\n[Success] Successfully booked {booked_count} slot(s)!")
                    else:
                        print(
                            "[Booking] No suitable slots found matching your preferences.")
                except Exception as e:
                    print(
                        f"[Booking] Error during availability parsing/booking: {e}")

            except Exception as e:
                print(f"[Booking] Error during availability check: {e}")


if __name__ == "__main__":
    main()
