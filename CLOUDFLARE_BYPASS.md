# Cloudflare Bypass Implementation

## Overview

The refactored `script.py` now integrates **Cloudflare security bypass** using `seleniumbase` with the `undetected-chromedriver` integration. This document outlines the implementation and key mechanisms.

---

## Key Technologies

### 1. **SeleniumBase with Undetected ChromeDriver (`uc=True`)**
- **Purpose**: Prevents bot detection by using an undetected version of Chrome
- **Location**: [script.py](script.py#L135)
- **Usage**:
  ```python
  with SB(uc=True, locale="en", incognito=True, disable_gpu=True) as driver:
  ```
- **Benefits**:
  - Bypasses Cloudflare's bot fingerprinting
  - Rotates browser user agents
  - Disables WebDriver detection

### 2. **Native Cloudflare Handling**
SeleniumBase provides built-in methods for Cloudflare challenges:

#### a. **`solve_captcha()` Method**
- **Purpose**: Automatically detects and solves CAPTCHAs (hCaptcha, reCAPTCHA, etc.)
- **Implementation**:
  ```python
  try:
      driver.solve_captcha()
      print("[CF Bypass] CAPTCHA solved successfully")
  except Exception as e:
      print(f"[CF Bypass] No CAPTCHA to solve or already solved: {e}")
  ```
- **Locations in script**:
  - [After login page load](script.py#L181)
  - [On booking form page](script.py#L261)
  - [During availability checks](script.py#L277)

#### b. **`wait_for_element_absent()` Method**
- **Purpose**: Waits for Cloudflare challenge iframe to disappear (indicating successful verification)
- **Implementation**:
  ```python
  driver.wait_for_element_absent("iframe[src*='challenges.cloudflare.com']", timeout=10)
  ```
- **Ensures**: Full CF challenge completion before proceeding

### 3. **Dedicated CF Challenge Handler Function**
A custom `handle_cloudflare_challenge()` function wraps all CF bypass logic:

```python
def handle_cloudflare_challenge(driver, max_retries=3):
    for attempt in range(max_retries):
        try:
            # Check for CF challenge
            if "challenge" in driver.get_current_url() or \
               driver.is_element_present("iframe[src*='challenges.cloudflare.com']"):
                
                # Solve CAPTCHA
                driver.solve_captcha()
                
                # Wait for verification
                driver.wait_for_element_absent("iframe[src*='challenges.cloudflare.com']", timeout=10)
                
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                driver.sleep(2)
    return False
```

**Called at critical points**:
- [After initial login page load](script.py#L182)
- [After navigation to booking page](script.py#L219)
- [After availability check](script.py#L277)
- [During slot booking refresh](script.py#L316)
- [After page refresh on failure](script.py#L323)

---

## Cloudflare Challenge Points

Cloudflare challenges are intercepted at these workflow stages:

| Stage | Location | CF Handler Call | Method |
|-------|----------|-----------------|--------|
| **Initial Login** | [L182](script.py#L182) | `handle_cloudflare_challenge()` | Detects & solves CF challenge on login page |
| **Navigation to Booking** | [L219](script.py#L219) | `handle_cloudflare_challenge()` | Handles CF after clicking "New Booking" |
| **Availability Check** | [L277](script.py#L277) | `handle_cloudflare_challenge()` | Solves CF before checking slot availability |
| **Slot Booking Refresh** | [L316](script.py#L316) | `handle_cloudflare_challenge()` | Handles CF during repeated refresh checks |
| **Page Refresh on Failure** | [L323](script.py#L323) | `handle_cloudflare_challenge()` | Retry mechanism after exceptions |

---

## How It Works: Step-by-Step

### 1. **Initialization**
```python
with SB(uc=True, locale="en", incognito=True, disable_gpu=True) as driver:
    driver.activate_cdp_mode("https://www.ssdcl.com.sg/User/Login")
```
- Starts browser with undetected chromedriver
- Activates Chrome DevTools Protocol (CDP) for advanced control
- Incognito mode to avoid cached sessions

### 2. **Challenge Detection**
```python
if "challenge" in driver.get_current_url() or \
   driver.is_element_present("iframe[src*='challenges.cloudflare.com']"):
```
- Checks URL for "challenge" keyword
- Detects Cloudflare iframe presence

### 3. **CAPTCHA Solving**
```python
driver.solve_captcha()
```
- Automatically identifies CAPTCHA type (reCAPTCHA v2, hCaptcha, etc.)
- Uses built-in solving mechanism or third-party integrations

### 4. **Verification Completion**
```python
driver.wait_for_element_absent("iframe[src*='challenges.cloudflare.com']", timeout=10)
driver.sleep(3)
```
- Waits for CF to complete verification
- Ensures all JS execution finishes before proceeding

### 5. **Retry Logic**
```python
for attempt in range(max_retries):
    try:
        # CF handling
    except Exception as e:
        if attempt < max_retries - 1:
            driver.sleep(2)
```
- Retries up to 3 times on failure
- Prevents false positives from race conditions

---

## Advantages Over Manual Toggle Clicking

### ❌ **Manual Approach** (Not Recommended)
```python
# Outdated - manual toggle click
toggle = driver.find_element("//input[@type='checkbox']")
toggle.click()
driver.sleep(5)
```
- **Issues**:
  - Toggle position varies by CF version
  - Doesn't handle invisible challenges
  - Fails on reCAPTCHA v3 (no visible UI)
  - Race conditions with JS execution

### ✅ **Automated Approach** (Current Implementation)
- **Advantages**:
  - Handles all CF challenge types
  - Automatic CAPTCHA detection & solving
  - Works with reCAPTCHA v2, v3, hCaptcha, Turnstile
  - Bot fingerprinting bypass with undetected-chromedriver
  - No hardcoded element selectors

---

## Integration with SeleniumBase Methods

### CDP Mode for Advanced Control
```python
driver.activate_cdp_mode("https://www.ssdcl.com.sg/User/Login")
```
- Enables Chrome DevTools Protocol
- Allows header manipulation & request interception
- Handles JS-heavy pages like SSDCL booking

### Undetected Click (`uc_click`)
```python
driver.uc_click("button[type='submit']")  # Bypass bot detection on form submit
```
- Used instead of regular `.click()` to avoid detection
- Applied to all interactive elements

### Smart Sleep Timing
```python
driver.sleep(2)  # Wait for CF JS execution
```
- Allows Cloudflare JS to run
- Prevents race conditions

---

## Configuration

### Environment-Specific Settings
```python
with SB(uc=True, locale="en", incognito=True, disable_gpu=True) as driver:
```

| Option | Purpose |
|--------|---------|
| `uc=True` | Undetected chromedriver mode |
| `locale="en"` | Set browser language to English |
| `incognito=True` | Run in private mode (no cookies) |
| `disable_gpu=True` | Disable GPU (faster on headless systems) |

---

## Testing the Cloudflare Bypass

### Quick Test
```bash
python script.py --dry-run
```
- Tests config loading without Selenium

### Full Login Test
```bash
python script.py --setup
python script.py
```
- Walks through full booking flow with CF bypass
- Set up credentials first with `--setup` flag

### Debugging
Enable verbose logging:
```python
driver.debug(True)  # Enable debug mode
```

---

## Troubleshooting

### Challenge Still Appearing
- **Solution**: Increase `max_retries` in `handle_cloudflare_challenge()`:
  ```python
  handle_cloudflare_challenge(driver, max_retries=5)
  ```

### CAPTCHA Not Solving
- **Solution**: Check browser timeout & network latency
  ```python
  driver.sleep(5)  # Increase pre-CAPTCHA wait
  driver.solve_captcha()
  ```

### Bot Detection (403 Errors)
- **Solution**: Ensure `uc=True` is enabled:
  ```python
  with SB(uc=True, ...) as driver:  # Must be enabled
  ```

---

## Dependencies

Updated `requirements.txt`:
```
seleniumbase>=4.0.0
undetected-chromedriver>=3.5.0
```

Install with:
```bash
pip install -r requirements.txt
```

---

## Security Notes

✅ **Credentials stored securely** at `~/.ssdc_autobooker.cfg` with `0o600` permissions

✅ **No hardcoded credentials** in script

✅ **Email passwords** handled via `getpass()` (not echoed to terminal)

❌ **Never commit config file** to version control

---

## Future Enhancements

1. **Proxy Support**: Add `--proxy` flag for IP rotation
2. **Headless Mode**: Add `--headless` flag for background execution
3. **Multi-threading**: Parallel slot availability checks
4. **Custom CAPTCHA Handler**: Integration with CAPTCHA solving services

---

## References

- [SeleniumBase Documentation](https://seleniumbase.io/)
- [Undetected ChromeDriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver)
- [Cloudflare Challenge Types](https://developers.cloudflare.com/bots/get-started/bots-on-cloudflare/)

