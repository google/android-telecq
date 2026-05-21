# android_beat/utils/telecom_utils.py
# Lint as: python3
"""Utils for calling Telecom related APIs.

The source code is located at:
https://source.corp.google.com/h/googleplex-android/platform/superproject/main/+/main:packages/modules/Telecom/tests/hostsidetests/multidevices/test/telecom_utils.py
"""

from collections.abc import Callable, Iterator
import contextlib
import datetime
import enum
import logging
import re
import time
from typing import Any

from mobly import asserts
from mobly.controllers import android_device
from snippet_uiautomator import uiautomator_g3

from android_beat import call_audio_state
from android_beat import telecom_timeout_constants as timeout_constants
from android_beat.utils import telecom_ui_utils
from android_beat.bluetooth.platforms.bluetooth import tws_device

_CallAudioState = call_audio_state.CallAudioState
_CallEndpoint = call_audio_state.CallEndpoint
_DELAY_BETWEEN_ACTIONS = datetime.timedelta(seconds=1)
_DELAY_BETWEEN_CALL_STATE_CHECKS = datetime.timedelta(seconds=1)
WAIT_CALL_CONNECTED_TIMEOUT = datetime.timedelta(seconds=30)
WAIT_CALL_DISCONNECTED_TIMEOUT = datetime.timedelta(seconds=20)
WAIT_CALL_RINGING_TIMEOUT = datetime.timedelta(seconds=30)
WAIT_CALL_DAILING_TIMEOUT = datetime.timedelta(seconds=30)
WAIT_SCREEN_LOCK_TIMEOUT = datetime.timedelta(seconds=10)
WAIT_CALL_AUDIO_STATE_TIMEOUT = datetime.timedelta(seconds=15)
UI_WAIT_TIME = datetime.timedelta(seconds=3)
UI_PERMISSION_WAIT_TIME = datetime.timedelta(seconds=10)
AUDIO_CALL_BUTTON_WAIT_TIME = datetime.timedelta(seconds=5)
_DIALER_PKG = 'com.google.android.dialer'
_DIALER_ACTIVITY = (
    'com.google.android.dialer.extensions.GoogleDialtactsActivity'
)
_SNIPPET_PKG = 'com.google.snippet.telecom'
_ANSWER_RE = r'(?i)Answer.*|Accept.*|Video.*'


@enum.unique
class CallState(enum.IntEnum):
  """Represents the state of a call.

  https://developer.android.com/reference/android/telecom/Call#STATE_ACTIVE
  """

  STATE_NEW = 0
  STATE_DIALING = 1
  STATE_RINGING = 2
  STATE_HOLDING = 3
  STATE_ACTIVE = 4
  STATE_DISCONNECTED = 7
  STATE_SELECT_PHONE_ACCOUNT = 8
  STATE_CONNECTING = 9
  STATE_DISCONNECTING = 10
  STATE_PULLING_CALL = 11
  STATE_AUDIO_PROCESSING = 12
  STATE_SIMULATED_RINGING = 13


@enum.unique
class CallType(enum.IntEnum):
  """The type of a call.

  Attributes:
    UNKNOWN: Unknown call type.
    LEGACY: Traditional circuit-switched voice call (e.g., 2G/3G).
    ViLTE: Video over LTE.
    VOLTE: Voice over LTE.
    VOWIFI: Voice over Wi-Fi.
  """

  UNKNOWN = 0
  LEGACY = 1
  VILTE = 2
  VOLTE = 3
  VOWIFI = 4


@enum.unique
class CallAttributes(enum.IntEnum):
  """A set of properties that define a new Call.

  https://developer.android.com/reference/android/telecom/CallAttributes

  Attributes:
    DIRECTION_UNKNOWN: Unknown call direction.
    DIRECTION_INCOMING: Incoming call.
    DIRECTION_OUTGOING: Outgoing call.
  """

  DIRECTION_UNKNOWN = 0
  DIRECTION_INCOMING = 1
  DIRECTION_OUTGOING = 2


@enum.unique
class CallMediaType(enum.IntEnum):
  """Call Type.

  https://developer.android.com/reference/android/telecom/CallAttributes

  Attributes:
    AUDIO_CALL: Used when answering or dialing a call to indicate that the call
      does not have a video component.
    VIDEO_CALL: Indicates video transmission is supported.
  """

  AUDIO_CALL = 1
  VIDEO_CALL = 2


def wait_until_or_assert(
    condition: Callable[[], bool],
    error_msg: str,
    timeout: datetime.timedelta,
) -> None:
  """Waits until the condition is met, or asserts if timeout.

  Args:
    condition: Represents the condition to wait for.
    error_msg: The error message to be included in the assertion failure.
    timeout: The maximum time to wait for the condition to be met.

  Raises:
    mobly.signals.TestFailure: When the condition is not met within the timeout.
  """
  end_time = time.monotonic() + timeout.total_seconds()
  while time.monotonic() < end_time:
    if condition():
      return
    time.sleep(_DELAY_BETWEEN_ACTIONS.total_seconds())
  asserts.fail(f'{error_msg} within {timeout.total_seconds()} seconds')


def accept_call(
    ad: android_device.AndroidDevice, remote_phone_number: str
) -> None:
  """Accepts a call from DUT to the specified number."""
  ad.log.info('Checking call state for %s', remote_phone_number)
  wait_until_or_assert(
      lambda: ad.tele.telecomGetCallState(remote_phone_number)
      == CallState.STATE_RINGING,
      error_msg=f'{ad} There is no active call to {remote_phone_number}',
      timeout=WAIT_CALL_RINGING_TIMEOUT,
  )
  ad.log.info('Accepting call from %s', remote_phone_number)
  ad.tele.telecomAcceptRingingCall(remote_phone_number)
  wait_until_or_assert(
      lambda: ad.tele.telecomGetCallState(remote_phone_number)
      == CallState.STATE_ACTIVE,
      error_msg=f'{ad} Failed to accept call from {remote_phone_number}',
      timeout=WAIT_CALL_CONNECTED_TIMEOUT,
  )
  ad.log.info('Call from %s is accepted', remote_phone_number)


def monitor_call(
    ad: android_device.AndroidDevice,
    remote_phone_number: str,
    call_duration: datetime.timedelta,
    call_type: CallType | None = None,
) -> None:
  """Monitors the ongoing call with the specified duration."""
  end_time = time.monotonic() + call_duration.total_seconds()
  while time.monotonic() < end_time:
    asserts.assert_equal(
        ad.tele.telecomGetCallState(remote_phone_number),
        CallState.STATE_ACTIVE,
        f'{ad} Call is disconnected during the call duration',
    )
    if call_type is not None:
      current_call_type = ad.tele.telecomGetCallType(remote_phone_number)
      asserts.assert_equal(
          current_call_type,
          call_type,
          f'{ad} Call is changed to {CallType(current_call_type).name},'
          f' expected: {call_type.name}',
      )
    time.sleep(_DELAY_BETWEEN_CALL_STATE_CHECKS.total_seconds())


def end_call(
    ad: android_device.AndroidDevice, remote_phone_number: str
) -> None:
  """Ends the ongoing call."""
  ad.log.info('Ending call with %s', remote_phone_number)
  ad.tele.telecomEndCall(remote_phone_number)
  wait_until_or_assert(
      lambda: ad.tele.telecomGetCallState(remote_phone_number)
      == CallState.STATE_DISCONNECTED,
      error_msg=(
          f'{ad} Failed to end the ongoing call with {remote_phone_number}'
      ),
      timeout=WAIT_CALL_DISCONNECTED_TIMEOUT,
  )
  ad.log.info('Call with %s is ended', remote_phone_number)


def set_default_dialer(
    ad: android_device.AndroidDevice, package_name: str
) -> None:
  """Sets the default dialer to the specified package."""
  ad.adb.shell(['telecom', 'set-default-dialer', package_name])
  ad.log.info('Set default dialer to %s', package_name)


def reset_default_dialer(ad: android_device.AndroidDevice) -> None:
  """Resets the default dialer to the system dialer."""
  system_dialer = (
      ad.adb.shell(['telecom', 'get-system-dialer']).decode().strip()
  )
  ad.adb.shell(['telecom', 'set-default-dialer', system_dialer])
  ad.log.info('Reset default dialer to %s', system_dialer)


def get_phone_number(ad: android_device.AndroidDevice) -> str:
  """Gets the phone number of ad."""
  phone_number = ad.bt_snippet.getLine1Number()
  if not phone_number:
    ad.log.info(
        'Phone number is not written to the SIM card, trying to get from'
        ' dimensions'
    )
    asserts.assert_in(
        'phone_number', ad.dimensions, 'Phone number is not set in dimensions'
    )
    phone_number = ad.dimensions['phone_number']
  return phone_number


def wait_for_call_ringing(
    ad: android_device.AndroidDevice, remote_phone_number: str
) -> None:
  """Wait for a call from DUT to the specified number."""
  ad.log.info('Waiting for call from %s', remote_phone_number)
  wait_until_or_assert(
      lambda: ad.tele.telecomGetCallState(remote_phone_number)
      == CallState.STATE_RINGING,
      error_msg=f'{ad} Failed to receive call from {remote_phone_number}',
      timeout=WAIT_CALL_RINGING_TIMEOUT,
  )
  ad.log.info('Call from %s is ringing', remote_phone_number)


def decline_call_and_verify_call_state(
    ad: android_device.AndroidDevice,
    bt_device: tws_device.TwsDevice,
    remote_phone_number: str,
) -> None:
  """Declines the call from bluetooth device and verifies the call state."""
  bt_device.call_decline()
  wait_until_or_assert(
      lambda: ad.tele.telecomGetCallState(remote_phone_number)
      == CallState.STATE_DISCONNECTED,
      error_msg=(
          f'{ad} Bluetooth device failed to decline call from'
          f' {remote_phone_number}'
      ),
      timeout=WAIT_CALL_DISCONNECTED_TIMEOUT,
  )
  ad.log.info(
      'Call from %s is declined from bluetooth device', remote_phone_number
  )


def log_on_device(ad: android_device.AndroidDevice, info_message: str) -> None:
  """Logs on device and host."""
  ad.log.info(info_message)
  ad.adb.shell(f'log -t TelecomAutomation "{info_message}"')


def verify_voip_call_active(
    ad: android_device.AndroidDevice,
    call_id: str,
    call_direction: CallAttributes,
    endpoint_type: _CallEndpoint = _CallEndpoint.BLUETOOTH,
) -> None:
  """Verifies the VoIP call state is STATE_ACTIVE."""
  try:
    wait_until_or_assert(
        lambda: ad.tele.getTransactionCallState(call_id)
        == CallState.STATE_ACTIVE,
        error_msg=(
            f'{ad} Failed to set the call state to {CallState.STATE_ACTIVE},'
            f' current state: {ad.tele.getTransactionCallState(call_id)}'
        ),
        timeout=WAIT_CALL_CONNECTED_TIMEOUT,
    )
  except AssertionError as e:
    ad.log.error(
        'Validation failed, hanging up call %s to clean up environment.',
        call_id,
    )

    ad.tele.hangupTransactionalCall(call_id)
    raise e

  # Verify the call count is 1 and the call direction is outgoing.
  call_count = ad.tele.getTransactionalCallCount()
  asserts.assert_equal(
      call_count,
      1,
      f'Current transactional call count is {call_count} but expected 1',
  )
  call_count_in_direction = ad.tele.getNumberOfCallsInDirection(call_direction)
  asserts.assert_equal(
      call_count_in_direction,
      1,
      f'Current call count in direction {call_direction} is'
      f' {call_count_in_direction} but expected 1',
  )
  # Waits for the call audio state to be the expected endpoint type.
  wait_until_or_assert(
      lambda: ad.tele.getTransactionCallEndpointType(call_id) == endpoint_type,
      error_msg=f'{ad} Failed to get the call endpoint type to {endpoint_type}',
      timeout=WAIT_CALL_CONNECTED_TIMEOUT,
  )


def place_call(
    caller: android_device.AndroidDevice,
    callee_phone_number: str,
) -> None:
  """Places a call from caller to callee and waits for callee to ring.

  Args:
    caller: The device placing the call.
    callee_phone_number: The phone number of the callee.
  """
  # Originates a call from caller to the callee number.
  log_on_device(
      caller,
      f'Originating call to {callee_phone_number}',
  )
  caller.tele.telecomPlaceCall(callee_phone_number)
  wait_until_or_assert(
      lambda: caller.tele.telecomGetCallState(callee_phone_number)
      == CallState.STATE_DIALING,
      error_msg=f'{caller} Failed to place call to {callee_phone_number}',
      timeout=WAIT_CALL_CONNECTED_TIMEOUT,
  )
  log_on_device(
      caller,
      f'Call to {callee_phone_number} is placed',
  )


@contextlib.contextmanager
def set_pin_lock(
    ad: android_device.AndroidDevice, pin_code: str
) -> Iterator[None]:
  """Context manager to set PIN lock on the device."""

  ad.log.info('Setting screen lock to PIN: %s', pin_code)
  ad.adb.shell(['locksettings', 'set-pin', pin_code])
  try:
    yield  # Yield to the caller to execute the test logic.
  finally:
    # Clear the PIN lock regardless of test result.
    ad.log.info('Clearing screen lock')
    ad.adb.shell(['locksettings', 'clear', '--old', pin_code])
    ad.adb.shell('input keyevent KEYCODE_WAKEUP')


def patch_local_file_paths(user_params: dict[str, Any]) -> None:
  """Patch local file paths to mh_files for local mode."""
  mh_files = user_params.get('mh_files', {})

  if 'telecom_audio_files' in mh_files:
    base_path = mh_files['telecom_audio_files'][0]

    if not (base_path.endswith('.wav') or base_path.endswith('.ogg')):
      audio_full_path = f'{base_path}/call_audio.wav'
    else:
      audio_full_path = base_path

    mh_files['telecom_test_call_audio'] = [audio_full_path]
    logging.info('>>> [file_path]: %s', audio_full_path)


def patch_local_device_dimensions(
    user_params: dict[str, Any], devices: list[Any]
) -> None:
  """Inject phone number to device dimensions."""
  role_keys = ['DUT_num', 'REF_num', 'MEDIA_num']

  for i, ad in enumerate(devices):
    if not hasattr(ad, 'dimensions') or ad.dimensions is None:
      ad.dimensions = {}

    if i < len(role_keys):
      target_key = role_keys[i]
      new_val = user_params.get(target_key)
      existing_val = ad.dimensions.get('phone_number')

      if existing_val and not str(existing_val).startswith('1000000'):
        continue

      if new_val:
        ad.dimensions['phone_number'] = str(new_val)


def verify_primary_sim(ad: android_device.AndroidDevice) -> None:
  """Verifies that the primary device has a SIM-based default outgoing account."""
  ad.log.info('Verifying primary SIM card...')
  asserts.assert_true(
      ad.tele.isDefaultOutgoingAccountSimBased(),
      'Primary device does not have a SIM-based default outgoing account.',
  )
  ad.log.info('Primary SIM card verification passed.')


def setup_emergency_test(
    ad: android_device.AndroidDevice, test_number: str
) -> None:
  """Sets up emergency test mode on the device."""
  ad.adb.shell(f'cmd phone emergency-number-test-mode -a {test_number}')
  ad.log.info('Injected %s into emergency list.', test_number)

  wait_until_or_assert(
      lambda: ad.tele.telephonyIsEmergencyNumber(test_number),
      error_msg=(
          f'Number {test_number} did not enter the emergency list in time!'
      ),
      timeout=datetime.timedelta(seconds=5),
  )
  ad.log.info('Verified: %s is now a valid emergency number.', test_number)


def handle_initial_meet_popups(ad: android_device.AndroidDevice) -> None:
  """Handles Google Meet onboarding popups with fix for infinite loops.

  Args:
    ad: The Android device to handle Meet onboarding popups on.
  """
  overall_timeout_sec = 60
  popup_timeout_ms = 3000
  start_time = time.monotonic()

  meet_popup_regex = (
      r'(?i)Allow|While using the app|Only this time|'
      r'Continue|Got it|TAKE ME TO MEET|Dismiss|Skip|Not now|'
      r'Give access'
  )

  ad.log.info('Starting Google Meet onboarding on %s...', ad.serial)
  ad.adb.shell('am force-stop com.google.android.apps.tachyon')
  # Wait for the device to be idle before launching Meet.
  time.sleep(UI_WAIT_TIME.total_seconds())

  ad.log.info('Launching Meet via monkey...')
  ad.adb.shell(
      'monkey -p com.google.android.apps.tachyon -c'
      ' android.intent.category.LAUNCHER 1'
  )

  all_popups_cleared = False
  while time.monotonic() - start_time < overall_timeout_sec:
    element = ad.ui(textMatches=meet_popup_regex)

    if element.wait.exists(timeout=popup_timeout_ms):
      element_info = element.info
      btn_text = element_info.get('text') or element_info.get(
          'contentDescription'
      )
      element.click()
      ad.log.info('Meet popup %r clicked.', btn_text)

      if btn_text and 'Give access' in btn_text:
        # Give access button is a special case that requires a longer wait.
        time.sleep(UI_WAIT_TIME.total_seconds())
      else:
        # Wait for the device to be idle before the next iteration.
        time.sleep(UI_WAIT_TIME.total_seconds())
    else:
      close_btn = ad.ui(descriptionContains='Close')
      if close_btn.exists:
        close_btn.click()
        ad.log.info("Closed Meet onboarding via 'Close' description.")
        continue

      ad.log.info('No more onboarding popups detected.')
      all_popups_cleared = True
      break

  asserts.assert_true(
      all_popups_cleared,
      f'Failed to reach Meet main screen within {overall_timeout_sec}s',
  )

  main_screen_regex = r'(?i)Search|New|Start a call'
  if (
      ad.ui(descriptionMatches=main_screen_regex).wait.exists(timeout=5000)
      or ad.ui(resourceId='com.google.android.apps.tachyon:id/fab').exists
  ):
    ad.log.info('Google Meet is at main screen and ready.')
  else:
    ad.log.warning(
        'Could not confirm main screen via UI elements, but popups are cleared.'
    )


def handle_meet_onboarding_permissions(
    ad: android_device.AndroidDevice,
) -> None:
  """Handles Google Meet onboarding and permission flow.

  Args:
    ad: The Android device to handle Meet onboarding and permission flow on.

  Raises:
    RuntimeError: If the 'New' button is not found after onboarding.
  """
  restart_meet_app(ad)
  time.sleep(UI_WAIT_TIME.total_seconds())

  continue_btn = ad.ui(textMatches='(?i)Continue as.*')
  if continue_btn.wait.exists(timeout=5000):
    ad.log.info("Clicking 'Continue'...")
    continue_btn.click()
  time.sleep(UI_WAIT_TIME.total_seconds())

  telecom_ui_utils.close_popup_windows(
      ad, popup_timeout=datetime.timedelta(seconds=5)
  )
  ad.log.info('Clicking "Give access"...')
  time.sleep(UI_WAIT_TIME.total_seconds())

  ad.log.info('Clicking "Got it"...')
  telecom_ui_utils.close_popup_windows(
      ad, popup_timeout=datetime.timedelta(seconds=5)
  )
  # 2. Click the "Search contacts" bar in the top right corner to enter the
  # search page
  search_input = ad.ui(textMatches='(?i)Search contacts.*')
  if not search_input.wait.exists(timeout=5000):
    raise RuntimeError(
        f"Onboarding failed on {ad.serial}: 'Search contacts' bar never"
        ' appeared.'
    )

  ad.log.info("Onboarding successful, 'Search contacts' bar is visible.")


def make_meet_audio_call_by_email(
    ad: android_device.AndroidDevice, email: str
) -> None:
  """Makes a Meet audio call to the specified email address.

  This function also handles potential Google Meet onboarding popups.

  Args:
    ad: The Android device to make the call from.
    email: The email address of the contact to call.
  """
  ad.log.info('Starting Meet audio call to %s...', email)

  restart_meet_app(ad)
  time.sleep(UI_WAIT_TIME.total_seconds())

  # 2. Click the "New" button in the bottom right corner to enter the search
  # page
  telecom_ui_utils.close_popup_windows(
      ad, popup_timeout=datetime.timedelta(seconds=5)
  )

  search_input = ad.ui(textMatches='(?i)Search contacts.*')
  if search_input.wait.exists(timeout=5000):
    ad.log.info('Focusing and entering email: %s', email)
    search_input.click()
    time.sleep(UI_WAIT_TIME.total_seconds())
    ad.adb.shell(f'input text "{email}"')
    ad.log.info('Hiding keyboard to reveal search results...')
    ad.adb.shell('input keyevent KEYCODE_BACK')
  else:
    ad.log.error('Failed to find search bar.')

  prefix = email.split('@')[0]
  parts = prefix.split('.')
  fuzzy_email_regex = f'(?i).*{".*".join(parts)}.*@gmail.*'
  contact = ad.ui(
      className='android.widget.TextView', textMatches=fuzzy_email_regex
  )
  if contact.wait.exists(timeout=5000):
    ad.log.info('Found contact entry for %s, performing click.', email)
    contact.click()
  else:
    ad.log.warning(
        'Could not find contact by resourceId, trying fallback tap...'
    )
  time.sleep(UI_WAIT_TIME.total_seconds())
  ad.log.info("Checking for the post-selection 'Continue' button...")
  continue_btn = ad.ui(textMatches='(?i)Continue.*')
  if continue_btn.wait.exists(timeout=5000):
    ad.log.info("Clicking 'Continue'...")
    continue_btn.click()
  time.sleep(UI_WAIT_TIME.total_seconds())
  telecom_ui_utils.close_popup_windows(ad)
  ad.log.info('Looking for Meet Audio Call button...')
  audio_call_btn = ad.ui(
      descriptionMatches='(?i)Audio call',
      packageName='com.google.android.apps.tachyon',
  )
  if audio_call_btn.wait.exists(timeout=5000):
    ad.log.info('Initiating Meet Audio Call...')
    time.sleep(AUDIO_CALL_BUTTON_WAIT_TIME.total_seconds())
    audio_call_btn.click()


def answer_meet_call_via_swipe(ad: android_device.AndroidDevice) -> bool:
  """Answers Meet call by performing a generic swipe-up gesture."""
  ad.log.info('Executing a generic swipe-up to answer Meet call...')

  meet_pkg = 'com.google.android.apps.tachyon'
  ad.adb.shell(
      f'am start -n {meet_pkg}/com.google.android.apps.tachyon.MainActivity'
  )
  time.sleep(timeout_constants.UI_WAIT_TIME.total_seconds())

  raw_size = ad.adb.shell('wm size').decode('utf-8')

  try:
    size_parts = raw_size.split()[-1].split('x')
    width, height = int(size_parts[0]), int(size_parts[1])

  except (IndexError, ValueError):
    ad.log.exception('Failed to parse screen size from: %s.', raw_size)
    width, height = 1080, 2340

  start_x = width // 2
  start_y = int(height * 0.8)
  end_x = start_x
  end_y = int(height * 0.2)

  ad.log.info(
      'Calculated dynamic coordinates: (%s, %s) -> (%s, %s)',
      start_x,
      start_y,
      end_x,
      end_y,
  )

  ad.adb.shell(f'input swipe {start_x} {start_y} {end_x} {end_y} 300')

  time.sleep(timeout_constants.UI_WAIT_TIME.total_seconds())
  return True


def swipe_down_and_answer(ad: android_device.AndroidDevice) -> None:
  """Swipes down from the top of the screen to open status bar and clicks answer."""
  ad.log.info('Expanding notifications to open status bar...')
  ad.adb.shell('cmd statusbar expand-notifications')
  time.sleep(UI_WAIT_TIME.total_seconds())

  ad_answer = ad.ui(descriptionMatches=_ANSWER_RE)
  if ad_answer.wait.exists(timeout=10000):
    ad_answer.click()
    ad.log.info('Call answered via status bar.')
  else:
    ad.log.warning('Answer button not found in status bar.')


def make_meet_video_call_by_email(
    ad: android_device.AndroidDevice, email: str
) -> None:
  """Makes a Meet video call to the specified email address.

  This function also handles potential Google Meet onboarding popups.

  Args:
    ad: The Android device to make the call from.
    email: The email address of the contact to call.
  """
  ad.log.info('Starting Meet video call to %s...', email)

  restart_meet_app(ad)
  time.sleep(UI_WAIT_TIME.total_seconds())

  # 2. Click the "New" button in the bottom right corner to enter the search
  # page
  telecom_ui_utils.close_popup_windows(
      ad, popup_timeout=datetime.timedelta(seconds=5)
  )

  search_input = ad.ui(textMatches='(?i)Search contacts.*')
  if search_input.wait.exists(timeout=5000):
    ad.log.info('Focusing and entering email: %s', email)
    search_input.click()
    time.sleep(UI_WAIT_TIME.total_seconds())
    ad.adb.shell(f'input text "{email}"')
    ad.log.info('Hiding keyboard to reveal search results...')
    ad.adb.shell('input keyevent KEYCODE_BACK')
  else:
    ad.log.error('Failed to find search bar.')

  prefix = email.split('@')[0]
  parts = prefix.split('.')
  fuzzy_email_regex = f'(?i).*{".*".join(parts)}.*@gmail.*'
  contact = ad.ui(
      className='android.widget.TextView', textMatches=fuzzy_email_regex
  )
  if contact.wait.exists(timeout=5000):
    ad.log.info('Found contact entry for %s, performing click.', email)
    contact.click()
  else:
    ad.log.warning('Could not find contact by resourceId.')
  time.sleep(UI_WAIT_TIME.total_seconds())
  ad.log.info("Checking for the post-selection 'Continue' button...")
  continue_btn = ad.ui(textMatches='(?i)Continue.*')
  if continue_btn.wait.exists(timeout=5000):
    ad.log.info("Clicking 'Continue'...")
    continue_btn.click()
  time.sleep(UI_WAIT_TIME.total_seconds())
  telecom_ui_utils.close_popup_windows(ad)
  ad.log.info('Looking for Meet Video Call button...')
  video_call_btn = ad.ui(
      text='Call', packageName='com.google.android.apps.tachyon'
  )
  if video_call_btn.wait.exists(timeout=5000):
    ad.log.info('Initiating Meet Video Call...')
    time.sleep(AUDIO_CALL_BUTTON_WAIT_TIME.total_seconds())
    video_call_btn.click()


def handle_call_and_hangup(ad: android_device.AndroidDevice):
  """Handles the call on the REF device and hangs up after a set duration.

  Args:
    ad: The Android device to handle the call on.
  """

  telecom_ui_utils.close_popup_windows(
      ad, popup_timeout=datetime.timedelta(seconds=5)
  )
  leave_btn = ad.ui(
      resourceIdMatches=(
          'com.google.android.apps.tachyon:id/majorca_leave_call(_container)?$'
      )
  )
  asserts.assert_true(
      leave_btn.wait.exists(timeout=2000),
      'Could not find Leave Call button',
  )
  leave_btn.click()
  ad.log.info('Call ended successfully.')


def is_incoming_call_present(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the incoming call is present on the Dialer screen.

  Args:
    ad: The Android device to verify the label on.
    timeout: The timeout in seconds to wait for the label to be present.

  Returns:
    True if the incoming call is present on the Dialer screen, False otherwise.
  """
  incoming_call_ui = ad.ui(descriptionMatches='(?i)Decline.*')
  if incoming_call_ui.wait.exists(timeout=timeout):
    ad.log.info('Incoming call UI is present.')
    return True
  ad.log.error('Incoming call UI is not present.')
  return False


def restart_meet_app(ad: android_device.AndroidDevice):
  """Restarts the Google Meet app.

  Args:
    ad: The Android device to restart Meet on.
  """
  ad.adb.shell('am force-stop com.google.android.apps.tachyon')
  ad.log.info('Meet stopped. Restarting for UI verification...')
  time.sleep(UI_WAIT_TIME.total_seconds())
  ad.adb.shell('am start -n com.google.android.apps.tachyon/.MainActivity')


def verify_call_log_in_meet(
    ad: android_device.AndroidDevice,
    target_email: str,
    should_exist: bool = True,
    timeout_sec: datetime.timedelta = datetime.timedelta(seconds=5),
) -> None:
  """Verifies call log in Meet App History list.

  Args:
    ad: The Android device to verify the call log entry on.
    target_email: The email address of the contact to verify.
    should_exist: Whether the call log entry should exist.
    timeout_sec: The timeout in seconds to wait for the call log entry to exist.

  Raises:
    RuntimeError: If the expected call log entry existence does not match
      the actual state.
  """
  ad.log.info('Verifying call log for %s in Meet History...', target_email)
  restart_meet_app(ad)
  history_header = ad.ui(
      text='History',
      resourceId='com.google.android.apps.tachyon:id/section_header_text',
  )
  if history_header.wait.exists(timeout=timeout_sec):
    ad.log.info("Found 'History' section header.")
  else:
    ad.log.warning(
        'History header not found, but proceeding to search for email...'
    )
  core_identity = target_email.split('@')[0].replace('.', '')
  selector = ad.ui(textMatches=f'(?i).*{core_identity}.*')
  actual_exists = selector.wait.exists(timeout=timeout_sec)
  if actual_exists != should_exist:
    ad.log.error(f'UI Dump for debugging: {ad.ui.dump()}')
    raise RuntimeError(
        f'Verification Failed: Expected existence to be {should_exist}, '
        f'but got {actual_exists} for {target_email}'
    )
  ad.log.info(
      'Verification Passed: %s status is %s', target_email, should_exist
  )


def delete_call_log_via_ui(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout_sec: datetime.timedelta = datetime.timedelta(seconds=5),
) -> None:
  """Deletes the call log entry for the Meet call via UI.

  Args:
    ad: The Android device to delete the call log entry on.
    target_email: The email address of the contact to delete the call log entry
      for.
    timeout_sec: The timeout in seconds to wait for the call log entry to exist.
  """
  restart_meet_app(ad)
  ad.log.info(
      'Attempting to physically delete call log for %s...', target_email
  )
  telecom_ui_utils.close_popup_windows(
      ad, popup_timeout=datetime.timedelta(seconds=5)
  )
  core_identity = target_email.split('@')[0].replace('.', '')
  selector = ad.ui(textMatches=f'(?i).*{core_identity}.*')
  if selector.wait.exists(timeout=timeout_sec):
    ad.log.info('Long pressing entry for %s...', core_identity)
    selector.long_click()
    time.sleep(1)
    # 3. Click the "Remove from history" button
    remove_btn = ad.ui(
        text='Remove from history',
    )
    if remove_btn.wait.exists(timeout=timeout_sec):
      ad.log.info("Clicking 'Remove from history'...")
      remove_btn.click()
      confirm_btn = ad.ui(
          textMatches='(?i)Remove|Delete|OK', resourceIdMatches='.*button1.*'
      )
      if confirm_btn.exists:
        confirm_btn.click()
        ad.log.info('Confirmation dialog dismissed.')
      ad.log.info('Successfully deleted %s via UI.', target_email)
    else:
      ad.log.error(
          "Long press succeeded but 'Remove from history' menu didn't appear."
      )
  else:
    ad.log.warning('Entry for %s not found. Nothing to delete.', target_email)


def verify_audio_call_label(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the 'Audio call' label is present on the screen.

  Args:
      ad: The Android device to verify the label on.
      timeout: The timeout in seconds to wait for the label to be present.

  Returns:
    True if the 'Audio call' label is present on the screen, False otherwise.
  """
  audio_call_ui = ad.ui(textMatches=r'(?i)Audio call.*')

  ad.log.info("Waiting for 'Audio call' UI element...")
  if audio_call_ui.wait.exists(timeout=timeout):
    # 2. Get the element information
    actual_text = audio_call_ui.text
    ad.log.info(
        'UI Verification Passed: Found element with text %s', actual_text
    )
    return True
  ad.log.error("UI Verification Failed: Could not find 'Audio call' on screen.")
  return False


def set_snippet_dialer(
    ad: android_device.AndroidDevice, package_name: str
) -> None:
  """Sets the specified package name as the default dialer.

  Args:
    ad: The Android device to set the default dialer on.
    package_name: The package name of the dialer app to set as default.
  """
  ad.log.info('Setting default dialer to: %s', package_name)
  ad.adb.shell(['telecom', 'set-default-dialer', package_name])


def verify_audio_call_label_dialer(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the target email is present on the Dialer screen.

  Args:
    ad: The Android device to verify the label on.
    target_email: The email address of the contact to verify.
    timeout: The timeout in seconds to wait for the label to be present.

  Returns:
    True if the target email is present on the Dialer screen for the
    given email, False
    otherwise.
  """
  prefix = target_email.split('@')[0]
  parts = prefix.split('.')
  fuzzy_regex = f'(?i).*{".*".join(parts)}.*@gmail.*'

  success = False
  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.log.info('Restarting Dialer for clean state...')
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    time.sleep(UI_WAIT_TIME.total_seconds())
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')
    time.sleep(UI_WAIT_TIME.total_seconds())
    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      ad.log.info('Clicked "Recents" tab')
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab')
      success = False
    email_ui = ad.ui(textMatches=fuzzy_regex)
    ad.log.info('Searching for email with regex: %s', fuzzy_regex)
    if email_ui.wait.exists(timeout=timeout):
      ad.log.info('UI verification passed: Found %s', target_email)
      success = True
    else:
      ad.log.error('UI verification failed: Could not find %s', target_email)
      hierarchy_dump = ad.ui.dump()
      ad.log.error(
          '--- START UI HIERARCHY DUMP ---\n%s\n--- END UI HIERARCHY DUMP ---',
          hierarchy_dump,
      )
  except Exception as e:
    ad.log.error(f'Unexpected error during UI verification: {e}')
    raise

  finally:
    ad.log.info('Forcing stop Dialer: %s', _DIALER_PKG)
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    ad.log.info('Restoring default dialer back to Snippet')
    set_snippet_dialer(ad, _SNIPPET_PKG)

  return success


def verify_meet_timestamp_present(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the Meet timestamp is present on the Dialer screen.

  Args:
    ad: The Android device to verify the label on.
    timeout: The timeout in seconds to wait for the label to be present.

  Returns:
    True if the Meet timestamp is present on the Dialer screen, False
    otherwise.
  """
  timestamp_regex = r'(?i)Meet\s*•\s*(\d+\s*min\s*ago|Just\s*now)'

  try:
    ad.log.info('Switching default dialer to: %s')
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab')

    ad.log.info('Verifying for timestamp with regex: %s', timestamp_regex)
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
    set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_meet_label_present(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the 'Meet' label is present on the Dialer screen.

  Args:
      ad: The Android device to verify the label on.
      timeout: The timeout in seconds to wait for the label to be present.

  Returns:
      True if the 'Meet' label is present on the Dialer screen, False
    otherwise.
  """
  meet_regex = r'(?i).*Meet.*'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      ad.log.info('Clicked "Recents" tab')
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab')
      return False
    meet_ui = ad.ui(textMatches=meet_regex)
    ad.log.info('Verifying if the screen contains the keyword: "Meet"')

    if meet_ui.wait.exists(timeout=timeout):
      actual_text = meet_ui.text
      ad.log.info('UI verification passed: Found %s', actual_text)
      return True
    else:
      ad.log.error('UI verification failed: Could not find Meet on screen.')
      hierarchy = ad.ui.dump()
      ad.log.error(
          '--- UI Dump ---\n%s\n--- END UI DUMP ---',
          hierarchy,
      )
      return False

  finally:
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    ad.log.info('Restoring default dialer back to Snippet')
    set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_group_call_label_dialer(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the 'Group call' label is present on the Dialer screen.

  Args:
    ad: The Android device to verify the label on.
    timeout: The timeout in seconds to wait for the label to be present.

  Returns:
    True if the 'Group call' label is present on the Dialer screen, False
    otherwise.
  """
  group_call_regex = r'(?i).*Group\s*call.*'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    time.sleep(UI_WAIT_TIME.total_seconds())
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      ad.log.info('Clicked "Recents" tab')
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab')
      return False

    group_call_ui = ad.ui(textMatches=group_call_regex)
    ad.log.info('Verifying if the screen contains the keyword: "Group call"')

    if group_call_ui.wait.exists(timeout=timeout):
      actual_text = group_call_ui.text
      ad.log.info('UI verification passed: Found %s', actual_text)
      return True
    else:
      pic_path = ad.take_screenshot(
          destination=ad.log_path,
          prefix='fail_group_call_not_found',
      )
      ad.log.info('Screenshot saved at: %s', pic_path)
      ad.log.error(
          'UI verification failed: Could not find Group call on screen.'
      )
      ad.log.error(
          'UI verification failed: Could not find Group call on screen.'
      )
      ad.log.error('UI verification failed: Could not find callback button.')
      return False
  finally:
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    ad.log.info('Restoring default dialer back to Snippet')
    set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_call_direction_outgoing(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the call direction is outgoing for the target email.

  Args:
    ad: The Android device to verify the call direction on.
    target_email: The email address of the contact to verify.
    timeout: The timeout in seconds to wait for the call direction to be
      outgoing.

  Returns:
    True if the call direction is outgoing for the target email, False
    otherwise.
  """

  prefix = target_email.split('@')[0]
  parts = prefix.split('.')
  fuzzy_email = f'(?i).*{".*".join(parts)}.*@gmail.*'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    time.sleep(UI_WAIT_TIME.total_seconds())
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    time.sleep(UI_WAIT_TIME.total_seconds())

    email_element = ad.ui(textMatches=fuzzy_email)
    ad.log.info('Searching for and clicking contact: %s', target_email)
    if email_element.wait.exists(timeout=timeout):
      email_element.click()
    else:
      ad.log.error(f'Could not find contact: {target_email}')
      return False

    history_btn = ad.ui(textMatches=r'(?i)History')
    ad.log.info('Clicking "History" button to enter call details...')
    if history_btn.wait.exists(timeout=timeout):
      history_btn.click()
    else:
      ad.log.error('Could not find "History" button')
      return False
    outgoing_ui = ad.ui(textMatches=r'(?i).*Outgoing\s*(video\s+)?call.*')
    ad.log.info('Verifying if the screen contains the keyword: "Outgoing call"')
    if outgoing_ui.wait.exists(timeout=timeout):
      ad.log.info('UI verification passed: Found Outgoing call on screen.')
      return True
    else:
      pic_path = ad.take_screenshot(
          destination=ad.log_path,
          prefix='fail_outgoing_call_not_found',
      )
      ad.log.info('Screenshot saved at: %s', pic_path)
      ad.log.error(
          'UI verification failed: Could not find Outgoing call on screen.'
      )
      return False

  finally:
    ad.log.info(
        'Cleaning up environment: forcing stop Dialer and restoring default'
        ' dialer'
    )
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_call_direction_incoming(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the call direction is incoming for the target email.

  Args:
    ad: The Android device to verify the call direction on.
    target_email: The email address of the contact to verify.
    timeout: The timeout in seconds to wait for the call direction to be
      incoming.

  Returns:
    True if the call direction is incoming for the target email, False
    otherwise.
  """
  prefix = target_email.split('@')[0]
  parts = prefix.split('.')
  fuzzy_email = f'(?i).*{".*".join(parts)}.*@gmail.*'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')
    time.sleep(UI_WAIT_TIME.total_seconds())
    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      ad.log.info('Clicked "Recents" tab')
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab')
      return False

    email_element = ad.ui(textMatches=fuzzy_email)
    ad.log.info('Searching for and clicking contact: %s', target_email)
    if email_element.wait.exists(timeout=timeout):
      email_element.click()
    else:
      ad.log.error(f'Could not find contact: {target_email}')
      return False
    history_btn = ad.ui(textMatches=r'(?i)History')
    ad.log.info('Clicking "History" button to enter call details...')
    if history_btn.wait.exists(timeout=timeout):
      history_btn.click()
    else:
      ad.log.error('Could not find "History" button')
      return False
    incoming_ui = ad.ui(textMatches=r'(?i).*Incoming\s*(video\s+)?call.*')
    ad.log.info('Verifying if the screen contains the keyword: "Incoming call"')
    if incoming_ui.wait.exists(timeout=timeout):
      ad.log.info('UI verification passed: Found Incoming call on screen.')
      return True
    else:
      ad.log.error(
          'UI verification failed: Could not find Incoming call on screen.'
      )
      return False
  finally:
    ad.log.info(
        'Cleaning up environment: forcing stop Dialer and restoring default'
        ' dialer'
    )
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_multiple_calls_in_history(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies multiple call entries exist in the history page.

  Args:
    ad: The Android device to verify the call history on.
    target_email: The email address of the contact to verify.
    timeout: The timeout to wait for the expected calls to be present.

  Returns:
    return True if multiple call history types are found on the screen,
    False otherwise.
  """
  prefix = target_email.split('@')[0]
  parts = prefix.split('.')
  fuzzy_email = f'(?i).*{".*".join(parts)}.*@gmail.*'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    time.sleep(UI_WAIT_TIME.total_seconds())
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    time.sleep(UI_WAIT_TIME.total_seconds())
    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      ad.log.info('Clicked "Recents" tab')
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab')
      return False

    email_element = ad.ui(textMatches=fuzzy_email)
    ad.log.info('Searching for and clicking contact: %s', target_email)
    if email_element.wait.exists(timeout=timeout):
      email_element.click()
    else:
      ad.log.error(f'Could not find contact: {target_email}')
      return False

    history_btn = ad.ui(textMatches=r'(?i)History')
    ad.log.info('Clicking "History" button to enter call details...')
    if history_btn.wait.exists(timeout=timeout):
      history_btn.click()
    else:
      ad.log.error('Could not find "History" button')
      return False

    outgoing_ui = ad.ui(textMatches=r'(?i).*(Outgoing\s*(video\s+)?(call)?).*')
    incoming_ui = ad.ui(textMatches=r'(?i).*Incoming\s*(video\s+)?(call)?.*')
    missed_ui = ad.ui(textMatches=r'(?i).*Missed\s*(video\s+)?(call)?.*')
    declined_ui = ad.ui(textMatches=r'(?i).*Declined\s*(video\s+)?(call)?.*')
    success = True
    call_types = {
        'Outgoing': outgoing_ui,
        'Incoming': incoming_ui,
        'Missed': missed_ui,
        'Declined': declined_ui,
    }
    found_types = set()
    start_time = time.monotonic()
    total_timeout = timeout.total_seconds()

    ad.log.info('Simultaneously waiting for %s...', list(call_types.keys()))
    while time.monotonic() - start_time < total_timeout:
      for call_type, ui_element in call_types.items():
        if call_type not in found_types:
          if ui_element.exists:
            ad.log.info('Found %s call in history.', call_type)
            found_types.add(call_type)
        if len(found_types) == len(call_types):
          break

    for call_type in call_types:
      if call_type not in found_types:
        ad.log.error(
            f'Could not find {call_type} call in history after'
            f' {total_timeout}s.'
        )
        success = False

    if not success:
      pic_path = ad.take_screenshot(
          destination=ad.log_path,
          prefix='fail_multiple_calls_in_history_not_found',
      )
      ad.log.info('Screenshot saved at: %s', pic_path)
    return success

  finally:
    ad.log.info(
        'Cleaning up environment: forcing stop Dialer and restoring default'
        ' dialer'
    )
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    set_snippet_dialer(ad, _SNIPPET_PKG)


def make_meet_group_audio_call(
    ad: android_device.AndroidDevice, emails: list[str]
) -> None:
  """Makes a Meet group audio call to the specified email addresses."""
  ad.log.info('Starting Meet group audio call to %s...', emails)
  restart_meet_app(ad)
  time.sleep(UI_WAIT_TIME.total_seconds())

  telecom_ui_utils.close_popup_windows(
      ad, popup_timeout=datetime.timedelta(seconds=5)
  )

  new_btn = ad.ui(descriptionMatches='(?i)New')
  if new_btn.wait.exists(timeout=5000):
    ad.log.info('Clicking "New" button...')
    new_btn.click()
  else:
    ad.log.error('Failed to find "New" button.')

  time.sleep(UI_WAIT_TIME.total_seconds())

  create_group_btn = ad.ui(descriptionMatches='(?i)Create a group call')
  if create_group_btn.wait.exists(timeout=5000):
    ad.log.info('Clicking "Create a group call" button...')
    create_group_btn.click()
  else:
    ad.log.error('Failed to find "Create a group call" button.')

  time.sleep(UI_WAIT_TIME.total_seconds())

  for email in emails:
    search_edit = ad.ui(className='android.widget.EditText')
    if search_edit.wait.exists(timeout=5000):
      ad.log.info('Entering email: %s', email)
      search_edit.click()
      time.sleep(UI_WAIT_TIME.total_seconds())
      ad.adb.shell(f'input text "{email}"')
      time.sleep(UI_WAIT_TIME.total_seconds())
      ad.adb.shell('input keyevent KEYCODE_ENTER')
      time.sleep(UI_WAIT_TIME.total_seconds())
    else:
      ad.log.error('Failed to find Search EditText box.')

  next_btn = ad.ui(textMatches='(?i)Next', className='android.widget.Button')
  if next_btn.wait.exists(timeout=5000):
    ad.log.info('Clicking "Next" button...')
    next_btn.click()
  else:
    next_btn_desc = ad.ui(
        descriptionMatches='(?i)Next', className='android.widget.Button'
    )
    if next_btn_desc.wait.exists(timeout=5000):
      ad.log.info('Clicking "Next" button (via content description)...')
      next_btn_desc.click()
    else:
      fallback_next = ad.ui(textMatches='(?i)Next|Done')
      if fallback_next.wait.exists(timeout=5000):
        fallback_next.click()
      else:
        ad.log.error('Failed to find "Next" button.')

  time.sleep(UI_WAIT_TIME.total_seconds())

  telecom_ui_utils.close_popup_windows(ad)
  ad.log.info('Looking for Audio Call button or Start button...')
  audio_call_btn = ad.ui(
      descriptionMatches='(?i)Audio call',
      packageName='com.google.android.apps.tachyon',
  )
  if audio_call_btn.wait.exists(timeout=5000):
    ad.log.info('Initiating Meet Group Audio Call...')
    time.sleep(AUDIO_CALL_BUTTON_WAIT_TIME.total_seconds())
    audio_call_btn.click()
  else:
    start_call_btn = ad.ui(
        textMatches='(?i)Start.*', className='android.widget.Button'
    )
    if start_call_btn.wait.exists(timeout=5000):
      ad.log.info('Initiating Meet Group Call via Start button...')
      time.sleep(AUDIO_CALL_BUTTON_WAIT_TIME.total_seconds())
      start_call_btn.click()
    else:
      ad.log.warning('Could not find explicit audio call button for group.')


def make_callback_from_dialer(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Makes a callback from the Dialer to the target email.

  Args:
    ad: The Android device to make the callback from.
    target_email: The exact email address of the contact to call back.
    timeout: The timeout in seconds to wait for the UI elements.

  Returns:
    True if the callback button is found and clicked, False otherwise.
  """
  email_prefix = target_email.split('@')[0]
  parts = email_prefix.split('.')
  fuzzy_email = f'(?i).*{".*".join(parts)}.*@gmail.*'
  callback_desc_regex = (
      f'(?i)^(call {fuzzy_email}|make a video call to {fuzzy_email})$'
  )

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    time.sleep(UI_WAIT_TIME.total_seconds())
    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      ad.log.info('Clicked "Recents" tab')
      recents_tab.click()
    callback_btn = ad.ui(descriptionMatches=callback_desc_regex)
    ad.log.info(
        'Searching for callback icon with regex: %s', callback_desc_regex
    )

    if callback_btn.wait.exists(timeout=timeout):
      ad.log.info(
          'UI verification passed: Found exact email callback icon. Initiating'
          ' call.'
      )
      callback_btn.click()
      time.sleep(UI_WAIT_TIME.total_seconds())
      return True
    else:
      ad.log.error('Could not find callback button matching the exact email.')
      pic_path = ad.take_screenshot(
          destination=ad.log_path,
          prefix='fail_callback_button_not_found',
      )
      ad.log.info('Screenshot saved at: %s', pic_path)
      ad.log.error('UI verification failed: Could not find callback button.')
      return False

  finally:
    ad.log.info(
        'Restoring default dialer back to Snippet (without force stopping'
        ' dialer mid-call)'
    )
    set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_missed_call_logged(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies that the Dialer screen shows 'Missed call' for the target email.

  Args:
    ad: The Android device to verify the missed call on.
    target_email: The email address of the contact to verify.
    timeout: The timeout in seconds to wait for the missed call to be logged.

  Returns:
    True if the Dialer screen shows 'Missed call' for the target email, False
    otherwise.
  """

  prefix = target_email.split('@')[0]
  parts = prefix.split('.')
  fuzzy_email = f'(?i).*{".*".join(parts)}.*@gmail.*'

  missed_call_regex = r'(?i).*Missed.*call.*'

  try:
    ad.log.info('Starting Dialer to verify missed call status...')
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    time.sleep(UI_WAIT_TIME.total_seconds())

    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.exists:
      recents_tab.click()

    email_element = ad.ui(textMatches=fuzzy_email)
    ad.log.info('Searching for and clicking contact: %s', target_email)
    if email_element.wait.exists(timeout=timeout):
      email_element.click()
    else:
      ad.log.error(f'Could not find contact: {target_email}')
      return False

    history_btn = ad.ui(textMatches=r'(?i)History')
    ad.log.info('Clicking "History" button to enter call details...')
    if history_btn.wait.exists(timeout=timeout):
      history_btn.click()
    else:
      ad.log.error('Could not find "History" button')
      return False
    missed_call_ui = ad.ui(textMatches=missed_call_regex)
    ad.log.info('Verifying if the screen contains the keyword: "Missed call"')
    if missed_call_ui.wait.exists(timeout=timeout):
      ad.log.info('UI verification passed: Found Missed call on screen.')
      return True
    else:
      ad.log.error(
          'UI verification failed: Could not find Missed call on screen.'
      )
      return False

  finally:
    ad.log.info(
        'Cleaning up environment: forcing stop Dialer and restoring default'
        ' dialer'
    )
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_declined_call_logged(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies that the Dialer screen shows 'Declined call' for the target email.

  Args:
    ad: The Android device to verify the declined call on.
    target_email: The email address of the contact to verify.
    timeout: The timeout in seconds to wait for the declined call to be logged.

  Returns:
    True if the Dialer screen shows 'Declined call' for the target email, False
    otherwise.
  """

  prefix = target_email.split('@')[0]
  parts = prefix.split('.')
  fuzzy_email = f'(?i).*{".*".join(parts)}.*@gmail.*'

  declined_call_regex = r'(?i).*Declined.*call.*'

  try:
    ad.log.info('Starting Dialer to verify declined call status...')
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')
    time.sleep(UI_WAIT_TIME.total_seconds())

    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.exists:
      recents_tab.click()

    email_element = ad.ui(textMatches=fuzzy_email)
    ad.log.info('Searching for and clicking contact: %s', target_email)
    if email_element.wait.exists(timeout=timeout):
      email_element.click()
    else:
      ad.log.error(f'Could not find contact: {target_email}')
      return False

    history_btn = ad.ui(textMatches=r'(?i)History')
    ad.log.info('Clicking "History" button to enter call details...')
    if history_btn.wait.exists(timeout=timeout):
      history_btn.click()
    else:
      ad.log.error('Could not find "History" button')
      return False
    declined_call_ui = ad.ui(textMatches=declined_call_regex)
    ad.log.info('Verifying if the screen contains the keyword: "Declined call"')
    if declined_call_ui.wait.exists(timeout=timeout):
      ad.log.info('UI verification passed: Found Declined call on screen.')
      return True
    else:
      ad.log.error(
          'UI verification failed: Could not find Declined call on screen.'
      )
      return False

  finally:
    ad.log.info(
        'Cleaning up environment: forcing stop Dialer and restoring default'
        ' dialer'
    )
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_call_log_type_is_audio(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the call log type is audio."""

  email_prefix = target_email.split('@')[0]
  parts = email_prefix.split('.')

  audio_desc_regex = f'^(?i)call\\s+(?!.*video).*{".*".join(parts)}.*@gmail.*'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    time.sleep(UI_WAIT_TIME.total_seconds())

    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.exists:
      recents_tab.click()

    audio_icon = ad.ui(descriptionMatches=audio_desc_regex)
    ad.log.info('Searching for audio icon with regex: %s', audio_desc_regex)

    if audio_icon.wait.exists(timeout=timeout):
      ad.log.info('UI verification passed: Found audio icon')
      ad.log.info('Actual content-desc: %s', audio_icon.description)
      return True
    else:
      ad.log.error('UI verification failed: Could not find audio icon.')
      uiautomator_g3.dump_to_hsv(ad, ad.ui, ad.current_test_info)
      return False

  finally:
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    ad.log.info('Restoring default dialer back to Snippet')
    set_snippet_dialer(ad, _SNIPPET_PKG)


def verify_history_contact_email(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the history contact email is present on the Dialer screen.

  Args:
    ad: The Android device to verify the call direction on.
    target_email: The email address of the contact to verify.
    timeout: The timeout in seconds to wait for the label to be present.

  Returns:
    True if the history contact email is present on the Dialer screen, False
    otherwise.
  """

  prefix = target_email.split('@')[0]
  parts = prefix.split('.')
  fuzzy_email = f'(?i).*{".*".join(parts)}.*@gmail.*'

  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    time.sleep(UI_WAIT_TIME.total_seconds())
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')

    time.sleep(UI_WAIT_TIME.total_seconds())

    email_element = ad.ui(textMatches=fuzzy_email)
    ad.log.info('Searching for and clicking contact: %s', target_email)
    if email_element.wait.exists(timeout=timeout):
      email_element.click()
    else:
      ad.log.error('Could not find contact: %s', target_email)
      return False

    history_btn = ad.ui(textMatches=r'(?i)History')
    ad.log.info('Clicking "History" button to enter call details...')
    if history_btn.wait.exists(timeout=timeout):
      history_btn.click()
    else:
      ad.log.error('Could not find "History" button')
      return False

    if email_element.wait.exists(timeout=timeout):
      ad.log.info('UI verification passed: Found %s on screen.', target_email)
      return True
    else:
      ad.log.error(
          'UI verification failed: Could not find %s on screen.',
          target_email,
      )
      uiautomator_g3.dump_to_hsv(ad, ad.ui, ad.current_test_info)
      return False

  finally:
    ad.log.info(
        'Cleaning up environment: forcing stop Dialer and restoring default'
        ' dialer'
    )
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    set_snippet_dialer(ad, _SNIPPET_PKG)


def clear_dialer_call_history(
    ad: android_device.AndroidDevice,
    target_email: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=3),
) -> bool:
  """Clears the call history in the Dialer.

  Args:
    ad: The Android device to clear the call history on.
    target_email: The email address of the contact to clear the call history
      for.
    timeout: The timeout in seconds to wait for the call history to be cleared.

  Returns:
    True if the call history is cleared successfully, False otherwise.
  """
  try:
    ad.log.info('Switching default dialer to: %s', _DIALER_PKG)
    set_snippet_dialer(ad, _DIALER_PKG)
    ad.adb.shell(f'am start -S -W -n {_DIALER_PKG}/{_DIALER_ACTIVITY}')
    time.sleep(UI_WAIT_TIME.total_seconds())
    recents_tab = ad.ui(textMatches=r'(?i)Recents?')
    if recents_tab.wait.exists(timeout=timeout):
      ad.log.info('Clicked "Recents" tab')
      recents_tab.click()
    else:
      ad.log.warning('Could not find "Recents" tab')
      return False
    more_options = ad.ui(description='More options')
    if more_options.wait.exists(timeout=timeout):
      more_options.click()
      ad.log.info('Clicked "More options" button')
    else:
      ad.log.warning(
          'Could not find "More options" button, call history may be empty'
      )
      return False
    clear_btn = ad.ui(textMatches=r'(?i)Clear call history')
    if clear_btn.wait.exists(timeout=timeout):
      clear_btn.click()
      ad.log.info('Clicked "Clear call history"')
    else:
      ad.log.error('Could not find "Clear call history" button')
      return False
    ok_btn = ad.ui(text='OK')
    if ok_btn.wait.exists(timeout=timeout):
      ok_btn.click()
      ad.log.info('Call history cleared successfully')
    else:
      ad.log.error('Could not find "OK" button')
      return False
    prefix = target_email.split('@')[0]
    fuzzy_regex = f'(?i).*{prefix}.*@gmail.*'
    if not ad.ui(textMatches=fuzzy_regex).exists:
      ad.log.error(
          f'Verification failed: Call history still contains {target_email}'
      )
      return True
    else:
      ad.log.error(
          f'Verification failed: Call history still contains {target_email}'
      )
      return False

  finally:
    ad.adb.shell(f'am force-stop {_DIALER_PKG}')
    ad.log.info('Restoring default dialer back to Snippet')
    set_snippet_dialer(ad, _SNIPPET_PKG)


def setup_and_launch_mobdog(ad: android_device.AndroidDevice) -> bool:
  """Initializes and launches the Mobdog app.

  Args:
    ad: The Android device to launch Mobdog on.

  Returns:
    True if Mobdog is launched successfully and the search bar is found, False
    otherwise.
  """
  pkg = 'com.google.android.apps.mobileutilities'
  activity = 'com.google.android.apps.mobileutilities.activity.applications.list.MobdogActivity'

  ad.log.info('Initializing Mobile Utilities (Mobdog)...')
  ad.adb.shell('am force-stop ' + pkg)
  time.sleep(UI_WAIT_TIME.total_seconds())
  ad.adb.shell('am start -n ' + pkg + '/' + activity)
  time.sleep(UI_WAIT_TIME.total_seconds())

  # Check for the search bar to appear as a sign of successful launch
  search_bar = ad.ui(
      resourceId='com.google.android.apps.mobileutilities:id/search_bar'
  )
  if search_bar.wait.exists(timeout=10):
    ad.log.info('Mobdog is ready, search bar appeared.')
    return True
  return False


def search_and_select_package(
    ad: android_device.AndroidDevice,
    app_name: str,
    package_name: str,
    flag_id: str,
    flag_keyword: str,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Searches for an app in Mobdog and selects it.

  Args:
    ad: The Android device to search and select the package on.
    app_name: The name of the app to search for.
    package_name: The package name of the app to select.
    flag_id: The flag ID of the app to select.
    flag_keyword: The target flag of the app to select.
    timeout: The timeout in seconds to wait for the app to be found.

  Returns:
    True if the app is found and selected, False otherwise.
  """
  time.sleep(UI_WAIT_TIME.total_seconds())
  continue_btn = ad.ui(textMatches=r'(?i)Continue')

  if not continue_btn.exists:
    ad.log.info('Continue button not found, trying to scroll...')
    # Execute a downward scroll to ensure the agreement is at the bottom.
    ad.ui.swipe(sx=500, sy=1500, ex=500, ey=500, steps=50)

  # Try clicking the Continue button again.
  if continue_btn.wait.exists(timeout=datetime.timedelta(seconds=5)):
    ad.log.info('Clicking Continue button...')
    continue_btn.click()

  # 1. Locate the search bar and enter the app name
  search_bar = ad.ui(
      resourceId='com.google.android.apps.mobileutilities:id/search_bar'
  )

  ad.log.info('Searching for app: %s', app_name)
  if search_bar.wait.exists(timeout=timeout):
    search_bar.click()
    ad.adb.shell('input text "' + app_name + '"')
    ad.log.info('Hiding keyboard to reveal search results...')
    ad.adb.shell('input keyevent KEYCODE_BACK')
  else:
    ad.log.error('Could not find search bar.')
    return False

  # 2. Find and click the exact package_name in the results
  target_package = ad.ui(text=package_name)
  if target_package.wait.exists(timeout=timeout):
    target_package.click()
    ad.log.info('Clicked %s in the list page', package_name)
  else:
    ad.log.error('Could not find package: %s', package_name)
    return False
  flags_tab = ad.ui(text='Flags')
  ad.log.info('Searching for Flags tab...')
  if flags_tab.wait.exists(timeout=timeout):
    flags_tab.click()
  else:
    ad.log.error('Could not find Flags tab.')
    return False

  flag_search_bar = ad.ui(
      resourceId='com.google.android.apps.mobileutilities:id/search_bar'
  )
  ad.log.info('Searching for flag ID...')
  if flag_search_bar.wait.exists(timeout=timeout):
    flag_search_bar.click()
    ad.adb.shell('input text "' + flag_id + '"')
    ad.adb.shell('input keyevent KEYCODE_ENTER')
    ad.log.info('Searched for flag ID: %s', flag_id)
  else:
    ad.log.error('Could not find search bar.')
    return False
  target_flag_item = ad.ui(textMatches='(?i).*' + flag_keyword + '.*')

  ad.log.info('Searching for flag ID: %s', flag_keyword)
  if target_flag_item.wait.exists(timeout=timeout):
    target_flag_item.click()
    ad.log.info('Clicked flag ID: %s in the list page', flag_keyword)
    return True

  ad.log.error('Could not find flag ID: %s', flag_keyword)
  return False


def override_flag_value_ui(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Overrides the flag value to true via UI."""

  override_btn = ad.ui(textMatches=r'(?i).*OVERRIDE FLAG.*')
  ad.log.info("Clicking 'OVERRIDE FLAG' button...")
  if override_btn.wait.exists(timeout=timeout):
    override_btn.click()
  else:
    ad.log.error("Could not find 'OVERRIDE FLAG' button.")
    return False

  false_value = ad.ui(text='false')
  true_value = ad.ui(text='true')

  if false_value.exists:
    ad.log.info("Clicking 'false' button...")
    false_value.click()

    true_option = ad.ui(text='true')
    if true_option.wait.exists(timeout=timeout):
      true_option.click()
    else:
      ad.log.error("Could not find 'true' option in the value toggle list.")
      return False
  elif true_value.exists:
    ad.log.info(
        "Detected that the current value is already 'true', no need to modify,"
        ' directly click OK.'
    )
  ok_btn = ad.ui(text='OK')
  if ok_btn.wait.exists(timeout=timeout):
    ok_btn.click()
    ad.log.info("Clicked 'OK' successfully to return.")
    return True

  ad.log.error("Could not find 'OK' button.")
  return False


def verify_flag_is_enabled(
    ad: android_device.AndroidDevice,
    email: str | None,
    timeout: datetime.timedelta = datetime.timedelta(seconds=5),
) -> bool:
  """Verifies the flag value is set to true for the given email."""
  if email is None:
    ad.log.error('email cannot be None for verify_flag_is_enabled.')
    return False
  ad.log.info('Verifying flag status for %s is true...', email)

  account_element = ad.ui(text=email)

  if account_element.wait.exists(timeout=timeout):
    is_true_present = ad.ui(text='true').wait.exists(timeout=timeout)

    if is_true_present:
      ad.log.info('Flag value is true for account %s', email)
      return True
    else:
      if ad.ui(text='false').wait.exists(timeout=timeout):
        ad.log.error('Flag value is false for account %s', email)
      else:
        ad.log.error('Flag value text not found on screen.')
      return False

  ad.log.error('Could not find account element: %s', email)
  return False


def enable_phenotype_flag_ui_flow(
    ad: android_device.AndroidDevice,
    app_name: str,
    package_name: str,
    flag_id: str,
    flag_keyword: str,
    email: str | None = None,
) -> bool:
  """Enables the phenotype flag via UI flow.

  Args:
    ad: The Android device to enable the flag on.
    app_name: The name of the app to enable the flag on.
    package_name: The package name of the app to enable the flag on.
    flag_id: The flag ID of the app to enable the flag on.
    flag_keyword: The target flag of the app to enable the flag on.
    email: The email address of the account to enable the flag on.

  Returns:
    True if the flag is enabled successfully, False otherwise.
  """
  if email is None:
    email = getattr(ad, 'mail', None)

  setup_and_launch_mobdog(ad)

  # Search and enter the package name Flag list page, and search for the ID and
  # keyword in the Flags tab
  if not search_and_select_package(
      ad, app_name, package_name, flag_id, flag_keyword
  ):
    ad.log.error(
        'Could not find package: %s or Flag %s', package_name, flag_keyword
    )
    return False

  # Execute the override operation (false -> true)
  if not override_flag_value_ui(ad):
    ad.log.error('Could not override flag value for %s', flag_keyword)
    return False

  # Wait for the flag value to be updated
  time.sleep(UI_WAIT_TIME.total_seconds())

  # Verify the flag value is set to true for the given email
  if not verify_flag_is_enabled(ad, email):
    ad.log.error('Flag %s is not enabled for account %s', flag_keyword, email)
    return False

  ad.log.info('Flag %s is enabled for account %s', flag_keyword, email)
  close_mobdog_app(ad, package_name)
  return True


def close_mobdog_app(ad: android_device.AndroidDevice, package_name: str):
  """Closes the Mobdog app and the target app."""
  ad.log.info('Closing Mobdog app...')
  ad.adb.shell('am force-stop com.google.android.apps.mobileutilities')
  ad.log.info('Closing target app...')
  ad.adb.shell('am force-stop ' + package_name)
  ad.log.info('Closed Mobdog app and target app.')


def verify_emergency_dialer_ui(
    ad: android_device.AndroidDevice,
    timeout: datetime.timedelta = datetime.timedelta(seconds=10),
) -> bool:
  """Verifies the emergency dialer UI is present on the screen.

  Args:
      ad: The Android device to verify the UI on.
      timeout: The timeout in seconds to wait for the UI to be present.

  Returns:
    True if the emergency dialer UI is present on the screen, False otherwise.
  """
  emergency_label = ad.ui(text='Emergency number')
  if not emergency_label.wait.exists(timeout=timeout):
    ad.log.error(
        "UI Verification Failed: Could not find 'Emergency number' on screen."
    )
    return False
  location_label = ad.ui(
      className='android.widget.TextView',
      textMatches='(?i).*(You are here|Location).*',
  )
  ad.log.info("Verifying Location info ('You are here' or 'Location')...")
  if location_label.wait.exists(timeout=timeout):
    # --- Core Fix: Access dictionary using .get() ---
    ui_info = location_label.text
    ad.log.info('UI Verification Passed: Found element with text %s', ui_info)
  else:
    ad.log.error(
        "UI Verification Failed: Could not find 'You are here' on screen."
    )
    return False
  ad.log.info('Successfully verified all Emergency UI elements.')
  return True


def add_contact_via_intent(
    ad: android_device.AndroidDevice, name: str, phone_number: str
) -> None:
  """Adds a contact with the specified name and phone number via Intent.

  Args:
    ad: The Android device to add the contact to.
    name: The name of the new contact.
    phone_number: The phone number belonging to that contact.

  Raises:
    RuntimeError: If the raw contact cannot be created.
  """
  ad.log.info('Adding contact via Intent: %s (%s)', name, phone_number)

  formatted_phone = phone_number.replace(' ', '')

  cmd = (
      'am start -a android.intent.action.INSERT '
      '-t "vnd.android.cursor.dir/contact" '
      f'-e name "{name}" -e phone "{formatted_phone}"'
  )
  ad.adb.shell(cmd)

  save_btn = ad.ui(text='Save')
  if save_btn.wait.exists(timeout=5000):
    save_btn.click()
    ad.log.info('Clicked Save button.')
  else:
    ad.log.warning('Could not find Save button text, trying Enter key...')
    ad.adb.shell('input keyevent KEYCODE_ENTER')


def delete_contact_by_number(
    ad: android_device.AndroidDevice, phone_number: str
) -> None:
  """Deletes all contacts matching the specified phone number using adb.

  Args:
    ad: The Android device to delete the contact from.
    phone_number: The phone number of the contact to delete.
  """
  ad.log.info('Deleting contact with phone number: %s', phone_number)

  # Use a more robust way to find and delete data entries first
  # Finding raw_contact_ids associated with this phone number
  query_res = (
      ad.adb.shell(
          'content query --uri content://com.android.contacts/data'
          ' --projection raw_contact_id'
          f" --where \"data1='{phone_number}' AND"
          " mimetype='vnd.android.cursor.item/phone_v2'\""
      )
      .decode()
      .strip()
  )

  ids = re.findall(r'raw_contact_id=(\d+)', query_res)
  if not ids:
    ad.log.info('No contacts found with phone number %s', phone_number)
    return

  for raw_id in set(ids):
    ad.log.info('Deleting raw contact ID: %s', raw_id)
    ad.adb.shell(
        'content delete --uri content://com.android.contacts/raw_contacts'
        f' --where "_id={raw_id}"'
    )
  ad.log.info('Deletion complete.')
