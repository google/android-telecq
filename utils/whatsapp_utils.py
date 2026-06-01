"""Utility functions for WhatsApp interactions."""

import datetime
import enum
import re
import time

from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb

from utils import telecom_ui_utils
from utils import telecom_utils

_DIALER_PKG = 'com.google.android.dialer'
_DIALER_ACTIVITY = (
    'com.google.android.dialer.extensions.GoogleDialtactsActivity'
)
_WHATSAPP_PKG = 'com.whatsapp'
_SNIPPET_PKG = 'com.google.snippet.telecom'

_WHATSAPP_ACTIVE_CALL_REGEX = re.compile(
    r'\[Call id=[\w@]+, state=ACTIVE,.*com\.whatsapp', re.IGNORECASE
)


@enum.unique
class CallLogKeyword(enum.StrEnum):
  """Keywords for verifying call log entries."""
  OUTGOING = 'Outgoing'
  INCOMING = 'Incoming'
  MISSED = 'Missed'
  DECLINED = 'Declined'
  VIDEO_CALL = 'video call'
  AUDIO_CALL = 'audio call'


def _get_feature_digits(phone_number: str) -> str:
  """Returns the last 10 digits of a phone number.

  Args:
    phone_number: The phone number to get the feature digits for.

  Returns:
    The last 10 digits of the phone number.
  """
  digits = ''.join(filter(str.isdigit, phone_number))
  return digits[-10:]


def restart_whatsapp_app(ad: android_device.AndroidDevice) -> None:
  """Restarts the WhatsApp app."""
  ad.log.info('Restarting WhatsApp...')
  ad.adb.shell(f'am force-stop {_WHATSAPP_PKG}')
  time.sleep(telecom_utils.UI_WAIT_TIME.total_seconds())
  ad.adb.shell(
      f'monkey -p {_WHATSAPP_PKG} -c android.intent.category.LAUNCHER 1'
  )
  ad.log.info('Waiting for WhatsApp app to load...')
  if not ad.ui(textMatches=r'(?i)Chats', packageName=_WHATSAPP_PKG).wait.exists(
      timeout=5000
  ):
    ad.log.warning('WhatsApp app did not load in time.')


def make_whatsapp_audio_call(
    ad: android_device.AndroidDevice, target_phone_number: str
) -> bool:
  """Makes a WhatsApp audio call to the specified phone number.

  Args:
    ad: The Android device to make the call on.
    target_phone_number: The phone number to make the call to.

  Returns:
    True if the call was made successfully, False otherwise.
  """
  ad.log.info('Starting WhatsApp audio call to %s...', target_phone_number)
  restart_whatsapp_app(ad)
  ad.log.info('Looking for WhatsApp Audio Call button...')
  calls_tab = ad.ui(textMatches=r'(?i)Calls', packageName=_WHATSAPP_PKG)
  if calls_tab.wait.exists(timeout=5000):
    ad.log.info('Found "Calls" tab, clicking...')
    calls_tab.click()
  else:
    ad.log.error(
        'Failed to find "Calls" tab, please check if it is on the main screen.'
    )
    return False
  new_call_btn = ad.ui(
      descriptionMatches=r'(?i)(Start a call|New call)',
      packageName=_WHATSAPP_PKG,
  )
  if new_call_btn.wait.exists(timeout=5000):
    ad.log.info('Clicking "New call" button...')
    new_call_btn.click()
  search_bar = ad.ui(
      resourceId='com.whatsapp:id/search_src_text', packageName=_WHATSAPP_PKG
  )
  if search_bar.wait.exists(timeout=5000):
    ad.log.info('Clicking search bar...')
    search_bar.click.wait(telecom_utils.UI_WAIT_TIME)
    clean_number = target_phone_number.replace(' ', '')
    ad.log.info('Entering number: %s', clean_number)
    ad.adb.shell(f'input text "{clean_number}"')
    time.sleep(telecom_utils.UI_WAIT_TIME.total_seconds())
  telecom_ui_utils.close_popup_windows(ad)
  clean_num = ''.join(filter(str.isdigit, target_phone_number))
  num_fuzzy_regex = f'.*{"{0,2}".join(list(clean_num))}.*'
  ad.log.info('Looking for contact item with regex: %s', num_fuzzy_regex)
  contact_item = ad.ui(
      resourceId='com.whatsapp:id/chat_able_contacts_row_name',
      textMatches=num_fuzzy_regex,
      packageName=_WHATSAPP_PKG,
  )
  ad.log.info('Hiding keyboard to ensure results are visible...')
  ad.adb.shell('input keyevent KEYCODE_BACK')
  time.sleep(telecom_utils.UI_WAIT_TIME.total_seconds())

  if contact_item.wait.exists(timeout=5000):
    ad.log.info('Found contact item container, clicking...')
    contact_item.click.wait(telecom_utils.UI_WAIT_TIME)
  else:
    ad.log.error(
        f'Failed to find contact item container for {target_phone_number}'
    )

  voice_call_btn = ad.ui(
      descriptionMatches='(?i)Voice call', packageName=_WHATSAPP_PKG
  )
  if voice_call_btn.wait.exists(timeout=5000):
    ad.log.info('Clicking "Voice call" button...')
    voice_call_btn.click.wait(telecom_utils.UI_WAIT_TIME)
    return True
  else:
    ad.log.error('Failed to find "Voice call" button.')
    return False


def make_whatsapp_video_call(
    ad: android_device.AndroidDevice, target_phone_number: str
) -> bool:
  """Makes a WhatsApp video call to the specified phone number.

  Args:
    ad: The Android device to make the call on.
    target_phone_number: The phone number to make the call to.

  Returns:
    True if the call was made successfully, False otherwise.
  """
  ad.log.info('Starting WhatsApp video call to %s...', target_phone_number)
  restart_whatsapp_app(ad)
  ad.log.info('Looking for WhatsApp "Calls" tab...')
  calls_tab = ad.ui(textMatches=r'(?i)Calls', packageName=_WHATSAPP_PKG)
  if calls_tab.wait.exists(timeout=5000):
    ad.log.info('Found "Calls" tab, clicking...')
    calls_tab.click()
  else:
    ad.log.error(
        'Failed to find "Calls" tab, please check if it is on the main screen.'
    )
    return False
  new_call_btn = ad.ui(
      descriptionMatches=r'(?i)(Start a call|New call)',
      packageName=_WHATSAPP_PKG,
  )
  if new_call_btn.wait.exists(timeout=5000):
    ad.log.info('Clicking "New call" button...')
    new_call_btn.click()
  search_bar = ad.ui(
      resourceId='com.whatsapp:id/search_src_text', packageName=_WHATSAPP_PKG
  )
  if search_bar.wait.exists(timeout=5000):
    ad.log.info('Clicking search bar...')
    search_bar.click.wait(telecom_utils.UI_WAIT_TIME)
    clean_number = target_phone_number.replace(' ', '')
    ad.log.info('Entering number: %s', clean_number)
    ad.adb.shell(f'input text "{clean_number}"')
    time.sleep(telecom_utils.UI_WAIT_TIME.total_seconds())
  telecom_ui_utils.close_popup_windows(ad)
  clean_num = ''.join(filter(str.isdigit, target_phone_number))
  num_fuzzy_regex = f'.*{"{0,2}".join(list(clean_num))}.*'
  ad.log.info('Looking for contact item with regex: %s', num_fuzzy_regex)
  contact_item = ad.ui(
      resourceId='com.whatsapp:id/chat_able_contacts_row_name',
      textMatches=num_fuzzy_regex,
      packageName=_WHATSAPP_PKG,
  )
  ad.log.info('Hiding keyboard to ensure results are visible...')
  ad.adb.shell('input keyevent KEYCODE_BACK')
  time.sleep(telecom_utils.UI_WAIT_TIME.total_seconds())

  if contact_item.wait.exists(timeout=5000):
    ad.log.info('Found contact item container, clicking...')
    contact_item.click.wait(telecom_utils.UI_WAIT_TIME)
  else:
    ad.log.error(
        f'Failed to find contact item container for {target_phone_number}'
    )

  video_call_btn = ad.ui(
      descriptionMatches='(?i)Video call', packageName=_WHATSAPP_PKG
  )
  if video_call_btn.wait.exists(timeout=5000):
    ad.log.info('Clicking "Video call" button...')
    video_call_btn.click.wait(telecom_utils.UI_WAIT_TIME)
    return True
  else:
    ad.log.error('Failed to find "Video call" button.')
    return False


def answer_whatsapp_call(ad: android_device.AndroidDevice):
  """Answers the WhatsApp call on the REF device.

  This method waits up to 20 seconds for the incoming call UI to appear
  before attempting to answer the call.

  Args:
    ad: The Android device to answer the call on.
  """
  ad_ref_answer = ad.ui(descriptionMatches='(?i)Answer.*|Accept.*|Video.*')
  if ad_ref_answer.wait.exists(timeout=20000):
    ad_ref_answer.click()
    ad.log.info('Call answered on REF device.')
  else:
    ad.log.warning('Incoming call UI not detected.')


def hangup_whatsapp_call(
    ad: android_device.AndroidDevice, timeout_ms: int = 5000
) -> bool:
  """Hangs up the WhatsApp call on the REF device.

  Args:
    ad: The Android device to hang up the call on.
    timeout_ms: The timeout in milliseconds to wait for the hangup button to
      appear.

  Returns:
    True if the hangup button was found and clicked, False otherwise.
  """

  ad.log.info('Looking for WhatsApp hangup button (End call)...')
  selectors = [
      ad.ui(resourceId='com.whatsapp:id/end_call_button'),
      ad.ui(
          resourceId='com.whatsapp:id/first_button', textMatches='(?i)END CALL'
      ),
      ad.ui(descriptionMatches='(?i)(End|Leave) call'),
  ]

  for selector in selectors:
    if selector.exists:
      ad.log.info('Found hangup button, clicking...')
      selector.click()
      return True

  ad.log.info('Hangup button not visible. Attempting to wake UI...')
  width, height = ad.ui.width, ad.ui.height
  ad.adb.shell(f'input tap {width // 2} {height // 2}')

  for selector in selectors:
    if selector.wait.exists(timeout=timeout_ms // len(selectors)):
      ad.log.info('Found hangup button after waking UI, clicking...')
      selector.click()
      return True

  ui_dump_content = ad.ui.dump()
  ad.log.error('Could not find hangup button. UI Dump: %s', ui_dump_content)

  return False


def decline_whatsapp_call(
    ad: android_device.AndroidDevice, timeout_ms: int = 5000
) -> None:
  """Declines the WhatsApp call on the android device.

  Args:
    ad: The Android device to decline the call on.
    timeout_ms: The timeout in milliseconds to wait for the decline button to
      appear.
  """
  ad.log.info('Looking for WhatsApp decline button...')
  decline_btn = ad.ui(descriptionMatches='(?i)Decline')
  if decline_btn.wait.exists(timeout=timeout_ms):
    ad.log.info('Found decline button, clicking...')
    decline_btn.click()
  else:
    ad.log.error('Could not find decline button within %d ms', timeout_ms)


def is_incoming_call_present(ad: android_device.AndroidDevice) -> bool:
  """Checks if the WhatsApp incoming call UI is present.

  Args:
    ad: The Android device to check.

  Returns:
    True if incoming call UI is present, False otherwise.
  """
  return ad.ui(descriptionMatches='(?i)Decline').exists


def clear_whatsapp_call_log(ad: android_device.AndroidDevice) -> None:
  """Clears the WhatsApp call log."""

  ad.log.info('Starting preventative WhatsApp call log clearing...')
  restart_whatsapp_app(ad)

  timeout_ms = int(telecom_utils.UI_WAIT_TIME.total_seconds() * 1000)

  more_options = ad.ui(
      resourceId='com.whatsapp:id/menuitem_overflow', packageName=_WHATSAPP_PKG
  )
  calls_tab = ad.ui(textMatches=r'(?i)Calls', packageName=_WHATSAPP_PKG)
  chats_tab = ad.ui(textMatches=r'(?i)Chats', packageName=_WHATSAPP_PKG)

  if calls_tab.wait.exists(timeout=5000):
    ad.log.info('Found "Calls" tab, clicking...')
    calls_tab.click()
  ad.log.info('Checking for More options...')
  if more_options.wait.exists(timeout=2000):
    ad.log.info('More options found immediately, clicking...')
    more_options.click()
  else:
    ad.log.info('More options not found. Refreshing UI via Chats tab...')
    if chats_tab.wait.exists(timeout=2000):
      chats_tab.click()
      if calls_tab.wait.exists(timeout=2000):
        calls_tab.click()

    if more_options.wait.exists(timeout=2000):
      ad.log.info('More options found after refresh, clicking...')
      more_options.click()
    else:
      ad.log.info('More options still not found. Log is likely empty.')

  clear_log_btn = ad.ui(
      textMatches='(?i)Clear call log', packageName=_WHATSAPP_PKG
  )
  if clear_log_btn.wait.exists(timeout=2000):
    clear_log_btn.click()
    ok_btn = ad.ui(textMatches='(?i)(OK|Clear)', packageName=_WHATSAPP_PKG)
    if ok_btn.wait.exists(timeout=2000):
      ad.bt_snippet.clickObjAndWait(ok_btn.selector.to_dict(), timeout_ms)
      ad.log.info('WhatsApp call log cleared.')
  else:
    ad.log.info('Clear call log button not found. Log is likely empty.')
  ad.log.info('Preventative clearing finished.')


def verify_whatsapp_call_number_dialer(
    ad: android_device.AndroidDevice,
    target_phone_number: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
    contact_name: str | None = None,
) -> bool:
  """Verifies the target phone number exists in the Dialer's Recents tab.

  Args:
    ad: The Android device to verify the number on.
    target_phone_number: The phone number to verify.
    timeout: The timeout in seconds to wait for the number to be present.
    contact_name: The name of the contact to verify.

  Returns:
    True if the number or name is present in the Dialer's Recents tab, False
    otherwise.
  """
  feature_digits = _get_feature_digits(target_phone_number)
  fuzzy_regex = f'.*{"{0,2}".join(list(feature_digits))}.*'
  success = False
  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    telecom_utils.set_snippet_dialer(ad, _DIALER_PKG)

    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      ad.log.info('Clicking "Recents" tab')
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab')

    if contact_name:
      ad.log.info('Searching for contact name: %s', contact_name)
      contact_ui = ad.ui(textMatches=f'(?i).*{contact_name}.*')
      if contact_ui.wait.exists(timeout=timeout):
        ad.log.info('Found contact name in Recents: %s', contact_name)
        return True

    ad.log.info('Searching for number with regex: %s', fuzzy_regex)
    number_ui = ad.ui(textMatches=fuzzy_regex)

    if number_ui.wait.exists(timeout=timeout):
      actual_text = number_ui.text
      ad.log.info('Found number in Recents: %s', actual_text)
      success = True
    else:
      ad.log.error('Failed to find number/name in Recents')
      ad.log.error(
          '--- START UI DUMP ---\n%s\n--- END UI DUMP ---', ad.ui.dump()
      )
  except Exception as e:
    ad.log.error(f'Unexpected error during verification: {e}')
    raise
  finally:
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    ad.log.info('Restoring default dialer back to Snippet')
    telecom_utils.set_snippet_dialer(ad, _SNIPPET_PKG)

  return success


def verify_whatsapp_label_present(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the 'WhatsApp' label is present on the Dialer screen.

  Args:
      ad: The Android device to verify the label on.
      timeout: The timeout in seconds to wait for the label to be present.

  Returns:
      True if the 'WhatsApp' label is present on the Dialer screen, False
    otherwise.
  """
  whatsapp_regex = r'(?i)WhatsApp\s*•\s*(\d+\s*min\s*ago|Just\s*now)'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    telecom_utils.set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      ad.log.info('Clicked "Recents" tab')
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab')
      return False
    whatsapp_ui = ad.ui(textMatches=whatsapp_regex)
    ad.log.info('Verifying if the screen contains the keyword: "WhatsApp"')

    if whatsapp_ui.wait.exists(timeout=timeout):
      actual_text = whatsapp_ui.text
      ad.log.info('UI verification passed: Found %s', actual_text)
      return True
    else:
      ad.log.error('UI verification failed: Could not find WhatsApp on screen.')
      return False

  finally:
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    ad.log.info('Restoring default dialer back to Snippet')
    telecom_utils.set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_history_contact_phone_number(
    ad: android_device.AndroidDevice,
    target_phone_number: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the history contact phone number is present on the Dialer screen.

  Args:
    ad: The Android device to verify the call direction on.
    target_phone_number: The phone number of the contact to verify.
    timeout: The timeout in seconds to wait for the label to be present.

  Returns:
    True if the history contact phone number is present on the Dialer screen,
    False otherwise.
  """
  feature_digits = _get_feature_digits(target_phone_number)
  fuzzy_number_regex = f'(?i).*{"{0,2}".join(list(feature_digits))}.*'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    telecom_utils.set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    number_element = ad.ui(textMatches=fuzzy_number_regex)
    ad.log.info('Searching for and clicking contact: %s', target_phone_number)
    if number_element.wait.exists(timeout=timeout):
      number_element.click()
    else:
      ad.log.error('Could not find contact: %s', target_phone_number)
      return False

    history_btn = ad.ui(textMatches=r'(?i)History')
    ad.log.info('Clicking "History" button to enter call details...')
    if history_btn.wait.exists(timeout=timeout):
      history_btn.click()
    else:
      ad.log.error('Could not find "History" button')
      return False

    if number_element.wait.exists(timeout=timeout):
      ad.log.info(
          'UI verification passed: Found %s on screen.', target_phone_number
      )
      return True
    else:
      ad.log.error(
          'UI verification failed: Could not find %s on screen.',
          target_phone_number,
      )
      return False

  finally:
    ad.log.info(
        'Cleaning up environment: forcing stop Dialer and restoring default'
        ' dialer'
    )
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    telecom_utils.set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_whatsapp_outgoing_history_count(
    ad: android_device.AndroidDevice,
    target_phone_number: str,
    history_count: int,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the call direction is outgoing for the target email.

  Args:
    ad: The Android device to verify the call direction on.
    target_phone_number: The phone number of the contact to verify.
    history_count: The number of history calls to verify.
    timeout: The timeout in seconds to wait for the call direction to be
      outgoing.

  Returns:
    True if the call direction is outgoing for the target email, False
    otherwise.
  """
  feature_digits = _get_feature_digits(target_phone_number)
  fuzzy_number_regex = f'(?i).*{"{0,2}".join(list(feature_digits))}.*'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    telecom_utils.set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')
    time.sleep(telecom_utils.UI_WAIT_TIME.total_seconds())

    email_element = ad.ui(textMatches=fuzzy_number_regex)
    ad.log.info('Searching for and clicking contact: %s', target_phone_number)
    if email_element.wait.exists(timeout=timeout):
      email_element.click()
    else:
      ad.log.error(f'Could not find contact: {target_phone_number}')
      return False

    history_btn = ad.ui(textMatches=r'(?i)History')
    ad.log.info('Clicking "History" button to enter call details...')
    if history_btn.wait.exists(timeout=timeout):
      history_btn.click()
    else:
      ad.log.error('Could not find "History" button')
      return False
    outgoing_ui = ad.ui(textMatches=r'(?i).*Outgoing\s*(video\s+)?call.*')
    actual_count = outgoing_ui.count
    ad.log.info('Found %d "Outgoing call" records.', actual_count)
    if actual_count >= history_count:
      ad.log.info(
          'Verification passed: Found %d records, meeting the expectation.',
          actual_count,
      )
      return True
    ad.log.error(
        f'Verification failed: Not enough records (actual: {actual_count},'
        f' expected: {history_count})'
    )
    return False

  finally:
    ad.log.info(
        'Cleaning up environment: forcing stop Dialer and restoring default'
        ' dialer'
    )
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    telecom_utils.set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_call_direction(
    ad: android_device.AndroidDevice,
    target_phone_number: str,
    expected_keywords: list[CallLogKeyword],
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the WhatsApp call log details with expected keywords.

  Args:
    ad: The Android device to verify the call log on.
    target_phone_number: The phone number of the contact to verify.
    expected_keywords: A list of CallLogKeyword that should be present in the
    call log
    timeout: The timeout in seconds to wait for the verification.

  Returns:
    True if all keywords are found in a single log entry, False otherwise.
  """
  feature_digits = _get_feature_digits(target_phone_number)
  fuzzy_number_regex = f'(?i).*{"{0,2}".join(list(feature_digits))}.*'

  # Construct regex: keywords in provided order, separated by anything.
  keyword_regex = f'(?i).*{"".join([f"{k}.*" for k in expected_keywords])}'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    telecom_utils.set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')
    time.sleep(telecom_utils.UI_WAIT_TIME.total_seconds())

    number_element = ad.ui(textMatches=fuzzy_number_regex)
    ad.log.info('Searching for and clicking contact: %s', target_phone_number)
    if number_element.wait.exists(timeout=timeout):
      number_element.click()
    else:
      ad.log.error(f'Could not find contact: {target_phone_number}')
      return False

    history_btn = ad.ui(textMatches=r'(?i)History')
    ad.log.info('Clicking "History" button to enter call details...')
    if history_btn.wait.exists(timeout=timeout):
      history_btn.click()
    else:
      ad.log.error('Could not find "History" button')
      return False

    ad.log.info(
        'Verifying keywords: %s with regex: %s',
        expected_keywords,
        keyword_regex,
    )
    log_ui = ad.ui(textMatches=keyword_regex)
    if log_ui.wait.exists(timeout=timeout):
      ad.log.info(
          'UI verification passed: Found keywords %s on screen.',
          expected_keywords,
      )
      return True
    else:
      ad.log.error(
          'UI verification failed: Could not find keywords %s on screen.',
          expected_keywords,
      )
      return False

  finally:
    ad.log.info(
        'Cleaning up environment: forcing stop Dialer and restoring default'
        ' dialer'
    )
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    telecom_utils.set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_whatsapp_timestamp_present(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the WhatsApp timestamp is present on the Dialer screen.

  Args:
    ad: The Android device to verify the label on.
    timeout: The timeout in seconds to wait for the label to be present.

  Returns:
    True if the WhatsApp timestamp is present on the Dialer screen, False
    otherwise.
  """
  timestamp_regex = r'(?i)WhatsApp\s*•\s*(\d+\s*min\s*ago|Just\s*now)'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    telecom_utils.set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab')

    ad.log.info(f'Verifying for timestamp with regex: {timestamp_regex}')
    timestamp_ui = ad.ui(textMatches=timestamp_regex)
    if timestamp_ui.wait.exists(timeout=timeout):
      actual_text = timestamp_ui.text
      ad.log.info('UI verification passed: Found %s', actual_text)
      return True
    else:
      ad.log.error(
          'UI verification failed: Could not find Meet timestamp on screen.'
      )
      return False
  finally:
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    ad.log.info('Restoring default dialer back to Snippet')
    telecom_utils.set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_whatsapp_call_log_audio(
    ad: android_device.AndroidDevice,
    target_phone_number: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the WhatsApp call log is audio.

  Args:
    ad: The Android device to verify the call direction on.
    target_phone_number: The phone number of the contact to verify.
    timeout: The timeout in seconds to wait for the call direction to be
      outgoing.

  Returns:
    True if the call direction is outgoing for the target phone number, False
    otherwise.
  """

  ad.log.info(
      'Verifying WhatsApp call log is audio to target phone number: %s',
      target_phone_number,
  )
  feature_digits = _get_feature_digits(target_phone_number)
  num_fingerprint = '.*'.join(list(feature_digits))
  audio_call_regex = f'^(?i)(?!.*video)call.*{num_fingerprint}.*'
  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    telecom_utils.set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    recents_tab = ad.ui(textMatches=r'(?i)Recents?', packageName=_DIALER_PKG)
    if recents_tab.wait.exists(timeout=5000):
      ad.log.info('Clicking "Recents" tab')
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab, continuing search...')

    ad.log.info('Searching for call log with regex: %s', audio_call_regex)
    call_log_element = ad.ui(
        descriptionMatches=audio_call_regex,
        packageName=_DIALER_PKG,
    )
    if call_log_element.wait.exists(timeout=timeout.total_seconds() * 1000):
      ad.log.info('UI verification passed: Found WhatsApp audio call log.')
      return True
    else:
      ad.log.error(
          'UI verification failed: Could not find WhatsApp audio call log.'
      )

  finally:
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    ad.log.info('Restoring default dialer back to Snippet')
    telecom_utils.set_snippet_dialer(ad, _SNIPPET_PKG)

  return False


def switch_both_whatsapp_video_to_audio(
    ad_dut: android_device.AndroidDevice,
    ad_ref: android_device.AndroidDevice
) -> bool:
  """Switches both devices from WhatsApp video call to audio call and verifies.

  Args:
    ad_dut: The first Android device (DUT).
    ad_ref: The second Android device (REF).

  Returns:
    True if both devices successfully switched to audio mode, False otherwise.
  """
  devices = [ad_dut, ad_ref]
  btn_id = 'com.whatsapp:id/camera_button'
  ad_dut.log.info('Switching both devices from video to audio...')

  for ad in devices:
    video_btn = ad.ui(resourceId=btn_id, packageName=_WHATSAPP_PKG)
    if video_btn.wait.exists(timeout=5000):
      if 'off' in video_btn.info.get('contentDescription', '').lower():
        ad.log.info('Video is ON, clicking to turn OFF...')
        video_btn.click()
      else:
        ad.log.info('Video already seems to be OFF.')
    else:
      ad.log.error(f'Device {ad.serial}: Could not find camera button.')
      ad.log.debug(f'UI Dump: \n{ad.ui.dump()}')

  time.sleep(2)

  all_success = True
  for ad in devices:
    still_video_on = ad.ui(description='Turn camera off')

    if still_video_on.exists:
      ad.log.error(
          'Verification FAILED: Video is still ON (button "Turn camera off"'
          ' still exists).'
      )
      ad.log.debug(f'Final UI State: \n{ad.ui.dump()}')
      all_success = False
    else:
      ad.log.info(
          f'Verification PASSED: Device {ad.serial} is now in audio mode.'
      )
  return all_success


def verify_whatsapp_call_exists(
    ad: android_device.AndroidDevice,
    phone_number: str,
) -> bool:
  """Verifies the WhatsApp call still exists.

  Args:
    ad: The Android device to verify the call exists on.
    phone_number: The phone number of the call to verify.

  Returns:
    True if the call exists, False otherwise.
  """
  try:
    dumpsys_output = ad.adb.shell('dumpsys telecom').decode(
        'utf-8', errors='replace'
    )
    ad.log.debug('Checking WhatsApp call status for %s', phone_number)

    is_telecom_active = bool(
        _WHATSAPP_ACTIVE_CALL_REGEX.search(dumpsys_output)
    )

    if is_telecom_active:
      ad.log.info('Verified: WhatsApp call is ACTIVE.')
      return True

  except adb.AdbError:
    ad.log.exception('ADB error during WhatsApp call verification.')
  ad.log.info('No active WhatsApp call found for %s', phone_number)
  return False


def unhold_whatsapp_call_via_ui(
    ad: android_device.AndroidDevice,
) -> bool:
  """Unholds the WhatsApp call via UI.

  Args:
    ad: The Android device to unhold the call on.

  Returns:
    True if the call was successfully unheld, False otherwise.
  """
  ad.log.info('Starting unhold_whatsapp_call_via_ui procedure.')

  ad.adb.shell('monkey -p com.whatsapp -c android.intent.category.LAUNCHER 1')
  ad.log.info('Attempting to find Resume button...')

  resume_button = ad.ui(textMatches='(?i)Resume')
  if resume_button.wait.exists(timeout=5000):
    ad.log.info('Found Resume button, clicking directly.')
    resume_button.click()
    return True

  ad.log.info(
      'Resume button not found immediately, looking for tap-to-return bar...'
  )
  tap_to_return_button = ad.ui(resourceId='com.whatsapp:id/title_layout')
  if tap_to_return_button.wait.exists(timeout=5000):
    ad.log.info('Found tap-to-return bar, clicking to expand UI.')
    tap_to_return_button.click()
    time.sleep(telecom_utils.UI_WAIT_TIME.total_seconds())
    if resume_button.wait.exists(timeout=5000):
      ad.log.info('Found Resume button after expanding, clicking now.')
      resume_button.click()
      return True

  ad.log.error('Resume button could not be found.')
  ad.take_screenshot('whatsapp_resume_not_found')
  return False


def verify_whatsapp_call_held(
    ad: android_device.AndroidDevice,
) -> bool:
  """Verifies if the WhatsApp call is currently held in the UI.

  Args:
    ad: The Android device to verify the call on.

  Returns:
    True if 'On hold' text is found in the UI, False otherwise.
  """
  ad.log.info('Starting verify_whatsapp_call_held procedure.')

  ad.adb.shell('monkey -p com.whatsapp -c android.intent.category.LAUNCHER 1')
  ad.log.info('Attempting to find return to call bar...')

  tap_to_return_button = ad.ui(
      resourceId='com.whatsapp:id/title_layout'
  )
  if not tap_to_return_button.wait.exists(timeout=telecom_utils.UI_WAIT_TIME):
    ad.log.error('Return to call bar not found in current UI dump.')
    ad.take_screenshot('whatsapp_held_bar_not_found')
    return False

  ad.log.info('Return to call bar found. Clicking now to expand call UI.')
  tap_to_return_button.click()
  time.sleep(telecom_utils.UI_WAIT_TIME.total_seconds())

  if ad.ui(textMatches=r'(?i)On hold').wait.exists(
      telecom_utils.UI_WAIT_TIME
  ):
    ad.log.info('Verification passed: "On hold" found in UI.')
    return True
  else:
    ad.log.warning('Verification failed: "On hold" not found in UI.')
    return False


def is_whatsapp_call_on_hold(ad: android_device.AndroidDevice) -> bool:
  """Checks if the current WhatsApp call is in ON_HOLD state via adb dumpsys.

  Args:
    ad: The Android device object.

  Returns:
    True if a WhatsApp call exists and its state is ON_HOLD, False otherwise.
  """
  cmd = 'dumpsys telecom | grep -A 20 "mCalls:"'
  output = ad.adb.shell(cmd).decode('utf-8', errors='replace')
  for line in output.splitlines():
    if 'com.whatsapp' not in line or 'voip=true' not in line:
      continue
    ad.log.debug('Found WhatsApp call entry: %s', line.strip())
    if 'state=ON_HOLD' in line:
      ad.log.info('WhatsApp call is confirmed to be ON_HOLD.')
      return True
    ad.log.info('WhatsApp call found but is NOT ON_HOLD.')
    return False

  return False
