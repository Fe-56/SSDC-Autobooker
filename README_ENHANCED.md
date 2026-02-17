# SSDC Autobooker - Enhanced with Cloudflare Bypass

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Initial Setup (Save Credentials)
```bash
python script.py --setup
```
- Enter your email (optional, for booking confirmations)
- Enter your NRIC (username)
- Enter your password

Credentials are saved to `~/.ssdc_autobooker.cfg` with restricted permissions (mode 0600).

### 3. Run the Autobooker
```bash
python script.py
```
- Script will prompt for:
  - Booking date (e.g., "01 Feb 2026")
  - 7-day range preference (y/n)
  - Location (Woodlands/Ang Mo Kio)
  - Session numbers (1-6, space-separated)

---

## Command-Line Options

### `--setup`
Set up credentials for the first time:
```bash
python script.py --setup
```

### `--dry-run`
Load and display config without running Selenium:
```bash
python script.py --dry-run
```
Output shows (masked):
```
Dry-run: loaded configuration:
  email_pref: y
  email_address: your@email.com
  email_password: ***
  username: S1234567A
  password: ***
```

### `--config <path>`
Use a custom config file location:
```bash
python script.py --config /path/to/custom_config.cfg
```

---

## Cloudflare Bypass Features

### Automatic CAPTCHA Solving
The script automatically detects and solves:
- ✅ reCAPTCHA v2 (Checkbox)
- ✅ reCAPTCHA v3 (Invisible)
- ✅ hCaptcha
- ✅ Cloudflare Turnstile

### Undetected Browser Mode
- Uses `undetected-chromedriver` to bypass bot detection
- Automatically rotates user agents
- Incognito mode to avoid tracking

### Multi-Point Challenge Handling
Cloudflare challenges are intercepted at:
1. **Login page** - After initial navigation
2. **Booking page** - After clicking "New Booking"
3. **Availability check** - Before searching for slots
4. **Slot booking** - During availability refresh
5. **Page refresh** - On retry after exceptions

---

## Configuration File

Default location: `~/.ssdc_autobooker.cfg`

### Format
```ini
[credentials]
email_pref = y
email_address = your@gmail.com
email_password = your_app_password
username = S1234567A
password = your_ssdc_password
```

### Security
- File permissions set to `0o600` (user read/write only)
- Never commit to version control
- Use [Gmail App Passwords](https://myaccount.google.com/apppasswords) for email

---

## Troubleshooting

### Issue: Cloudflare Challenge Still Blocking
**Solution 1**: Increase retry attempts
```python
# In script.py, line ~310
handle_cloudflare_challenge(driver, max_retries=5)
```

**Solution 2**: Ensure undetected-chromedriver is enabled
```bash
pip install --upgrade undetected-chromedriver
```

### Issue: CAPTCHA Solving Fails
**Solution**: Ensure good internet connection and longer timeout
```python
driver.sleep(5)  # Increase wait before CAPTCHA
driver.solve_captcha()
```

### Issue: Login Fails with "Username or password incorrect"
- Verify credentials are correct with `--dry-run`
- Check if SSDC website requires additional MFA
- Try manual login at https://www.ssdcl.com.sg/User/Login

### Issue: Slots Not Appearing
- Ensure availability window is correct
- Check if slots are already fully booked
- Increase max attempts in booking loop:
  ```python
  max_attempts = 100  # Default: 50
  ```

---

## How It Works: Technical Flow

```
┌─────────────────────────────────────────┐
│  1. Load/Setup Credentials              │
│     (~/.ssdc_autobooker.cfg)            │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  2. Start SeleniumBase (uc=True)        │
│     Undetected ChromeDriver             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  3. Navigate to SSDCL Login             │
│     Handle Cloudflare Challenge #1      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  4. Login with Credentials              │
│     Click "Proceed"                     │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  5. Navigate to Booking Page            │
│     Handle Cloudflare Challenge #2      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  6. Fill Booking Form                   │
│     Date, Location, Session Numbers     │
│     Solve CAPTCHA                       │
│     Handle Cloudflare Challenge #3      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  7. Check Availability Loop             │
│     Find matching slots                 │
│     Handle Cloudflare Challenge #4      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  8. Click Slot & Confirm                │
│     Send Email Notification             │
│     Refresh & Retry for More Slots      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  9. Success: All Slots Booked!          │
└─────────────────────────────────────────┘
```

---

## Environment Variables (Optional)

No environment variables required, but you can set:
```bash
export SSDCL_EMAIL="your@gmail.com"
export SSDCL_USERNAME="S1234567A"
```

(Script will still prompt if not set)

---

## Logging & Debugging

### View logs from last run
```bash
tail -f ~/Documents/GitHub/SSDC-Autobooker/latest_logs/script.line_*/basic_test_info.txt
```

### Enable verbose output
Modify script to add:
```python
driver.debug(True)
```

---

## Best Practices

1. **Use App Passwords for Gmail**
   - Go to https://myaccount.google.com/apppasswords
   - Create a 16-character app-specific password
   - Use this in the script, not your main Gmail password

2. **Set Realistic Booking Parameters**
   - Don't book too far in advance (>90 days)
   - Check SSDCL website for real availability windows
   - Use 7-day range for better matching

3. **Test Before Booking**
   - Run with `--dry-run` to verify config
   - Test with a single session number first
   - Check email is working with manual test

4. **Handle Failures Gracefully**
   - Script retries on exceptions automatically
   - Monitor console output for issues
   - Don't force-quit mid-booking

---

## Advanced Options

### Custom Chrome Options
Modify line ~145 in script.py:
```python
with SB(uc=True, locale="en", incognito=True, 
        disable_gpu=True, headless=True) as driver:  # Add headless=True
```

### Use Proxy
(Not yet implemented, but can add)
```python
with SB(uc=True, proxy="socks5://proxy:port") as driver:
```

### Timeout Adjustments
```python
driver.wait_for_element(element, timeout=10)  # Increase timeout
```

---

## Known Limitations

- ⚠️ Only supports single booking type (PL - Practical Lessons)
- ⚠️ No support for PT, SL, TT yet (can be added)
- ⚠️ Requires active Chrome/Chromium binary
- ⚠️ Cannot bypass Cloudflare on 100% of pages (rate limits may apply)

---

## Support & Issues

For issues or feature requests:
1. Check `CLOUDFLARE_BYPASS.md` for technical details
2. Test with `--dry-run` to isolate problems
3. Check browser console for JS errors: `F12` → Console tab
4. Verify SSDCL website is accessible manually

---

## License & Disclaimer

Use responsibly. This script is intended for personal booking convenience only.

⚠️ **Disclaimer**: Automating web interactions may violate SSDCL's terms of service. Use at your own risk.

