"""Utility functions for Telecom UI interactions."""

import datetime
import time
from typing import Any

from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb
from snippet_uiautomator import errors

from android_beat import telecom_timeout_constants as timeout_constants

_UI_SHORT_BREATHING_TIMEOUT = datetime.timedelta(seconds=1)

_DIALER_PKG = "com.google.android.dialer"
_DIALER_ACTIVITY = (
    "com.google.android.dialer.extensions.GoogleDialtactsActivity"
)
_GEMINI_PKG = "com.google.android.apps.bard"
_QUICKSEARCHBOX_PKG = "com.google.android.googlequicksearchbox"
_GEMINI_ACTIVITY = (
    "com.google.android.apps.bard.shellapp.BardEntryPointActivity"
)


class UIElementError(Exception):
  """Raised when UI element fails."""


def ui_exists(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=15),
    **kwargs: Any,
) -> bool:
  """Checks if UI exists in page.

  Args:
    ad: The AndroidDevice be operated on.
    timeout: The timeout waiting for ui element appearing.
    **kwargs: Key/value pairs to match in a XML node's attributes.

  Returns:
    True for exist, False for non-existent.
  """
  ad.log.info("Checking exists: %s", kwargs)
  result = ad.ui(**kwargs).wait.exists(timeout=timeout)
  time.sleep(_UI_SHORT_BREATHING_TIMEOUT.total_seconds())
  return result


def click_ui_element(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=15),
    click_timeout: datetime.timedelta = datetime.timedelta(seconds=5),
    wait_for_window: bool = True,
    **kwargs: Any,
) -> None:
  """Click UI in the page.

  Args:
    ad: The AndroidDevice be operated on.
    timeout: The timeout waiting for ui element appearing.
    click_timeout: The timeout waiting for the click action to complete.
    wait_for_window: Whether to wait for a new window event after clicking.
    **kwargs: Key/value pairs to match in a XML node's attributes.

  Raises:
    UIElementError: cannot find UI element, raise exception.
  """
  if ui_exists(ad, timeout, **kwargs):
    ad.log.info("Click: %s" % kwargs)

    if wait_for_window:
      try:
        # Performs clickObjAndWait (Expects window change)
        ad.ui(**kwargs).click.wait(timeout=click_timeout)
      except (UIElementError, errors.UiAutomatorError) as e:
        ad.log.warning(
            "Click sent, but wait for new window timed out or failed: %s" % e
        )
    else:
      # Performs standard clickObj (No wait condition)
      ad.ui(**kwargs).click()

    time.sleep(_UI_SHORT_BREATHING_TIMEOUT.total_seconds())
  else:
    raise UIElementError(f"UI element cannot be found {kwargs} !")


def click_ui_element_if_exists(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=15),
    required: bool = False,
    **kwargs: Any,
) -> bool:
  """Clicks a UI element if it exists."""

  actual_timeout = timeout if required else datetime.timedelta(seconds=5)

  if ui_exists(ad, timeout=actual_timeout, **kwargs):
    ad.log.info("Clicking: %s", kwargs)
    try:
      ad.ui(**kwargs).click()
      # Wait for UI to settle after click to avoid race conditions.
      time.sleep(_UI_SHORT_BREATHING_TIMEOUT.total_seconds())
      return True
    except errors.UiAutomatorError as e:
      ad.log.warning("Click failed: %s", e)
      if required:
        raise UIElementError(f"Failed to click {kwargs}") from e
      return False
  else:
    if required:
      raise UIElementError(f"Critical UI element not found: {kwargs}")
    ad.log.info("Optional UI element %s not found, skipping...", kwargs)
    return False


def close_popup_windows(
    device: android_device.AndroidDevice,
    popup_timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> None:
  """Closes popup windows iteratively until none are found or timeout occurs."""
  overall_timeout_sec = 90
  start_time = time.monotonic()

  # Regex to match any of the pop-up buttons we need to dismiss.
  # Case-insensitive match for "Allow", "OK", "Close", or "Skip".
  popup_button_texts = (
      r"(?i)\s*(OK|Close|Skip|Got it|Save|Keep Google|Dismiss|TRY"
      r" AGAIN|Cancel|Done|Try again)\s*"
  )

  # Keep clicking any button that matches the regex until no more are found
  # or until the overall timeout of 90 seconds is reached.
  while time.monotonic() - start_time < overall_timeout_sec:
    if not click_ui_element_if_exists(
        device, timeout=popup_timeout, textMatches=popup_button_texts
    ):
      device.log.info("All popups cleared.")
      break
    device.log.info("Popup clicked, checking for more...")

  time.sleep(_UI_SHORT_BREATHING_TIMEOUT.total_seconds())


def dial_number_via_ui(
    ad: android_device.AndroidDevice, phone_number: str
) -> bool:
  """Dials a number via UI in Google Dialer.

  Args:
    ad: The AndroidDevice be operated on.
    phone_number: The phone number to dial.

  Returns:
    True if the call button was successfully clicked, False otherwise.
  """

  ad.log.info("Preparing to dial number via UI: %s", phone_number)
  ad.adb.shell(f"am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}")

  keypad_btn = ad.ui(
      descriptionMatches=r"(?i)key\s*pad", packageName=_DIALER_PKG
  )
  if keypad_btn.wait.exists(timeout=3000):
    ad.log.info('Clicking "Keypad" button...')
    keypad_btn.click()

  digits_field = ad.ui(resourceId="com.google.android.dialer:id/digits")
  if digits_field.wait.exists(timeout=2000):
    ad.log.info("Entering number: %s", phone_number)
    digits_field.set_text(phone_number)
  else:
    ad.adb.shell(f"input text {phone_number}")

  call_btn = ad.ui(textMatches="(?i)Call", packageName=_DIALER_PKG)
  if call_btn.wait.exists(timeout=3000):
    ad.log.info('Clicking "Call" button...')
    return call_btn.click()

  ad.log.error('Failed to find "Call" button, dialing failed')
  return False


def answer_call_via_ui(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Answers the call via UI in Google Dialer.

  Args:
    ad: The AndroidDevice be operated on.
    timeout: The timeout waiting for the answer button to appear.

  Returns:
    True if the answer button was successfully clicked, False otherwise.
  """

  ad.log.info("Waiting for call UI and trying to answer...")

  answer_regex = r"(?i)\b(Answer|accept)\b"

  answer_btn = ad.ui(descriptionMatches=answer_regex)

  if answer_btn.wait.exists(timeout=timeout):
    ad.log.info("Answer button detected, clicking...")
    return answer_btn.click()

  ad.log.error(
      "Answer button not detected within %s seconds" % timeout.total_seconds()
  )
  return False


def end_call_via_ui(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Ends the call via UI.

  Args:
    ad: The AndroidDevice be operated on.
    timeout: The timeout waiting for the end call button to appear.

  Returns:
    True if the end call button was successfully clicked, False otherwise.
  """
  ad.log.info("Ending call via UI...")
  end_btn = ad.ui(description="End call")

  if end_btn.wait.exists(timeout=timeout):
    ad.log.info("End call button found, clicking...")
    return end_btn.click()

  ad.log.error(
      "End call button not detected within %s seconds" % timeout.total_seconds()
  )
  return False


def verify_voicemail_via_ui(
    ad: android_device.AndroidDevice, phone_number: str
) -> bool:
  """Verifies voicemail via UI in Google Dialer.

  Args:
    ad: The Android device to verify voicemail on.
    phone_number: The phone number to verify voicemail for.

  Returns:
    True if voicemail is found and play is clicked, False otherwise.
  """
  ad.log.info("Verifying voicemail via UI...")
  try:
    ad.log.info("Preparing to dial number via UI: %s", phone_number)
    ad.adb.shell(f"am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}")

    voicemail_tab = ad.ui(descriptionMatches="(?i)Voicemail")
    if voicemail_tab.wait.exists(timeout=5000):
      ad.log.info("Clicking Voicemail tab...")
      voicemail_tab.click()
    else:
      ad.ui(text="Voicemail").click()
    digits = "".join(filter(str.isdigit, phone_number))
    num_pattern = ".*".join(list(digits[-10:]))
    target_row = ad.ui(textMatches=f"(?i).*{num_pattern}.*")

    if not target_row.wait.exists(timeout=5000):
      ad.log.error("Could not find number in voicemail list")
      return False

    ad.log.info("Found number in voicemail list")
    play_btn = target_row.sibling(descriptionMatches="(?i)play.*")
    if not play_btn.exists:
      play_btn = ad.ui(descriptionMatches="(?i)play.*")

    if not play_btn.exists:
      ad.log.warning("Found number in voicemail list but no play button")
      return False

    play_btn.click()
    time.sleep(_UI_SHORT_BREATHING_TIMEOUT.total_seconds())
    delete_btn = ad.ui(descriptionMatches="(?i)delete.*")
    if not delete_btn.exists:
      delete_btn = target_row.sibling(descriptionMatches="(?i)delete.*")

    if not delete_btn.exists:
      ad.log.error("Delete button not found, clearing failed.")
      return False

    ad.log.info("Playback verified, clicking delete button...")
    delete_btn.click()
    time.sleep(2)
    ad.log.info("Voicemail successfully played and cleared.")
    return True

  except (adb.AdbError, errors.UiAutomatorError):
    ad.log.exception("Failed to verify voicemail via UI")
    return False


def clear_all_notifications_via_ui(ad: android_device.AndroidDevice) -> bool:
  """Clears all notifications via UI.

  Args:
    ad: The Android device to clear notifications on.

  Returns:
    True if successful, False otherwise.
  """
  ad.log.info("Clearing all notifications via UI...")
  try:
    # 1. Expand notifications
    ad.adb.shell("cmd statusbar expand-notifications")
    time.sleep(_UI_SHORT_BREATHING_TIMEOUT.total_seconds())

    # 2. Check if there are any notifications.
    # If "Clear all" or "Clear" exists, we click it.
    # Usually "Clear all" is at the bottom, so we may need to scroll.
    clear_all_btn = ad.ui(textMatches="(?i)Clear all")

    if not clear_all_btn.exists:
      ad.log.info("Clear all button not visible, scrolling to find it...")
      try:
        ad.ui(resourceId="android:id/list", scrollable=True).swipe.up(
            percent=70, speed=1500
        )
      except (adb.AdbError, errors.UiAutomatorError) as e:
        ad.log.warning("Failed to swipe up: %s", e)

    if clear_all_btn.wait.exists(timeout=5000):
      ad.log.info("Clicking Clear all button...")
      clear_all_btn.click()
      time.sleep(2)
      return True
    else:
      # If "Clear all" doesn't exist, maybe there are no notifications.
      # But the user wants to fail if not found.
      # Check if "No notifications" is visible.
      if ad.ui(textMatches="(?i)No notifications").exists:
        ad.log.info("No notifications to clear.")
        return True

      ad.log.error("Clear all button not found and notifications might exist!")
      ad.log.debug("UI Dump: %s", ad.ui.dump())
      return False

  except (adb.AdbError, errors.UiAutomatorError):
    ad.log.exception("Failed to clear notifications.")
    ad.log.debug("UI Dump: %s", ad.ui.dump())
    return False
  finally:
    ad.adb.shell("cmd statusbar collapse")


def open_gemini_app(ad: android_device.AndroidDevice):
  """Opens Gemini App."""
  ad.log.info("Opening Gemini App...")

  # Force stop and cold start to ensure a clean launch
  ad.adb.shell(f"am start -S -W -n {_GEMINI_PKG}/{_GEMINI_ACTIVITY}")

  # Simple verification: check if Gemini related text or logo exists on screen
  btn = ad.ui(textMatches="(?i)Use Gemini")
  if btn.wait.exists(timeout=5000):
    ad.log.info("Clicking 'Use Gemini' button...")
    btn.click()
    # Click transition buffer
    time.sleep(_UI_SHORT_BREATHING_TIMEOUT.total_seconds())
  else:
    ad.log.warning("Use Gemini button not found, skipping...")


def close_gemini_app(ad: android_device.AndroidDevice):
  """Force stops the Gemini App to ensure a clean state."""
  ad.log.info("Closing Gemini App...")

  ad.adb.shell(f"am force-stop {_GEMINI_PKG}")
  ad.adb.shell(f"am force-stop {_QUICKSEARCHBOX_PKG}")
  # Give the system a moment to clean up resources.
  time.sleep(timeout_constants.UI_WAIT_TIME.total_seconds())
  ad.log.info("Gemini App closed.")


def gemini_app_call_number(
    ad: android_device.AndroidDevice, phone_number: str
) -> bool:
  """Calls a number via Gemini App.

  Args:
    ad: The Android device to operate on.
    phone_number: The phone number to dial.

  Returns:
    True if the call was successful, False otherwise.
  """
  ad.log.info("Preparing to call number via Gemini App: %s", phone_number)
  input_field = ad.ui(textMatches="(?i)Type.*|Enter.*|Ask.*")
  if input_field.wait.exists(timeout=5000):
    ad.log.info("Input field found, entering number...")
    input_field.click()
    formatted_cmd = f"Call {phone_number.replace(' ', '')}"
    ad.adb.shell(f"input text '{formatted_cmd}'")
    send_btn = ad.ui(descriptionMatches="(?i)Send.*")
    if send_btn.exists:
      send_btn.click()
    else:
      ad.adb.shell("input keyevent KEYCODE_ENTER")

    ad.log.info("Waiting for Gemini to respond...")
  else:
    ad.log.error("Input field not found, call failed.")
    return False

  continue_btn = ad.ui(textMatches="(?i)Continue")
  if continue_btn.wait.exists(timeout=5000):
    ad.log.info("Clicking 'Continue' to confirm dialing...")
    continue_btn.click()
    return True
  else:
    ad.log.error("No 'Continue' button found, call failed.")
    return False


def unhold_call_via_ui(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Unholds the PSTN call via UI in Google Dialer.

  Args:
    ad: The AndroidDevice be operated on.
    timeout: The timeout waiting for the unhold button to appear.

  Returns:
    True if the unhold button was successfully clicked, False otherwise.
  """
  ad.log.info("Unholding call via UI...")
  # Bring dialer to front if not already there.
  ad.adb.shell(f"am start -n {_DIALER_PKG}/{_DIALER_ACTIVITY}")
  time.sleep(_UI_SHORT_BREATHING_TIMEOUT.total_seconds())

  # Common descriptions/texts for the hold/unhold button.
  unhold_regex = r"(?i)Unhold|Hold"
  unhold_btn = ad.ui(descriptionMatches=unhold_regex, packageName=_DIALER_PKG)

  if unhold_btn.wait.exists(timeout=timeout):
    ad.log.info("Unhold/Hold button found, clicking...")
    return unhold_btn.click()

  # Try text if description fails.
  unhold_btn = ad.ui(textMatches=unhold_regex, packageName=_DIALER_PKG)
  if unhold_btn.wait.exists(timeout=timeout):
    ad.log.info("Unhold/Hold button found via text, clicking...")
    return unhold_btn.click()

  ad.log.error(
      "Unhold button not detected within %s seconds" % timeout.total_seconds()
  )
  return False
