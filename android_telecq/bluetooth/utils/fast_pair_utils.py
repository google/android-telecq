"""Utility functions for Fast Pair operations."""

import datetime
import logging
import time

from mobly import asserts
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb
import tenacity

from android_telecq.bluetooth.platforms.bluetooth import tws_device


FAST_PAIR_CONNECTION_DELAY = datetime.timedelta(seconds=45)

_UI_OPERATION_TIMEOUT = datetime.timedelta(seconds=6)
_WAIT_FOR_BROADCAST_DELAY = datetime.timedelta(seconds=20)
_WAIT_FOR_BLUETOOTH_SCAN_DELAY = datetime.timedelta(seconds=3)

_GMS_CORE_PACKAGE = 'com.google.android.gms'
_FAST_PAIR_DB_FOLDER = 'data/data/com.google.android.gms/files/nearby-fast-pair'

_BACK_TO_HOME_SCREEN_COMMAND = (
    'am start -a android.intent.action.MAIN -c android.intent.category.HOME'
)
_SETTINGS_PUT_GLOBAL_COMMAND = 'settings put global {setting} {value}'
_OPEN_NEARBY_SCAN_COMMAND = 'google_setup_nearby_scanning_enabled'
_OPEN_BLE_SCAN_COMMAND = 'ble_scan_always_enabled'
_OPEN_NEARBY_SAVE_DEVICE_COMMAND = 'google_setup_nearby_save_devices_enabled'
_OPEN_NEARBY_CONSENT_COMMAND = 'google_setup_nearby_consent_status'
_OPEN_FAST_PAIR_CONNECTION_PAGE_COMMAND = (
    'am start -n'
    ' com.google.android.gms/com.google.android.gms.fastpair.devices.'
    'DevicesListSilkActivity'
)
_OPEN_SETTINGS_COMMAND = (
    'am start -a android.settings.SETTINGS'
)
_ENABLE_FAST_PAIR_DEBUG_MODE_COMMAND = (
    'am broadcast -a com.google.android.gms.phenotype.FLAG_OVERRIDE '
    '--es package "com.google.android.gms.nearby" --es user "*" '
    '--es name "Nearby__default_debug_mode_enabled" --ez value true'
)
_DEVELOPMENT_SETTINGS_ENABLED = 'development_settings_enabled'


def clear_cache_and_setup_fast_pair_settings(
    ad: android_device.AndroidDevice,
) -> None:
  """Clears Fast Pair cache and sets up Fast Pair settings."""
  open_nearby_and_ble_scan(ad)
  clear_android_fast_pair_cache(ad)
  ad.log.info('Fast Pair settings are set up, rebooting the device.')
  ad.reboot()


def open_nearby_and_ble_scan(ad: android_device.AndroidDevice) -> None:
  """Opens Nearby and enables BLE scan on the device."""
  ad.adb.shell(
      _SETTINGS_PUT_GLOBAL_COMMAND.format(
          setting=_OPEN_NEARBY_SCAN_COMMAND, value=1
      )
  )
  ad.adb.shell(
      _SETTINGS_PUT_GLOBAL_COMMAND.format(
          setting=_OPEN_BLE_SCAN_COMMAND, value=1
      )
  )


@tenacity.retry(
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_exponential(multiplier=1, max=10),
    before_sleep=tenacity.before_sleep_log(
        logging.getLogger(__name__), logging.INFO
    ),
)
def open_fast_pair_debug_result(ad: android_device.AndroidDevice) -> None:
  """Attempts to enable Fast Pair debug mode with strict state checking."""
  try:
    ad.adb.shell(f'settings put global {_DEVELOPMENT_SETTINGS_ENABLED} 1')
    ad.adb.shell(_ENABLE_FAST_PAIR_DEBUG_MODE_COMMAND)
    ad.adb.shell(['am', 'force-stop', _GMS_CORE_PACKAGE])
    ad.log.info('Sent ADB command to enable debug mode, now verifying...')
  except adb.AdbError:
    ad.log.warning('ADB command failed to send, falling back to UI check.')

  open_fast_pair_connection_page(ad)

  debug_results_label = ad.uia(text='Include debug results')

  if not debug_results_label.wait.exists(_UI_OPERATION_TIMEOUT):
    if ad.uia(textMatches='(?i)Done|Close').wait.exists(
        _UI_OPERATION_TIMEOUT / 2
    ):
      ad.uia(textMatches='(?i)Done|Close').click()

  debug_results_switch = ad.uia(text='Include debug results').right(
      clazz='android.widget.Switch'
  )

  if debug_results_switch.wait.exists(_UI_OPERATION_TIMEOUT):
    is_checked = debug_results_switch.info.get('checked')
    if not is_checked:
      ad.log.info('Debug mode switch is OFF, clicking to enable...')
      debug_results_switch.click()
    else:
      ad.log.info('Debug mode switch is already ON, skipping click.')
  else:
    raise asserts.fail('Could not find the "Include debug results" switch.')

  asserts.assert_true(
      ad.uia(text='Include debug results')
      .right(clazz='android.widget.Switch')
      .info.get('checked'),
      'Fast Pair debug mode failed to enable.',
  )


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, max=10),
    before_sleep=tenacity.before_sleep_log(
        logging.getLogger(__name__), logging.INFO
    ),
)
def open_nearby_save_device(
    ad: android_device.AndroidDevice, is_independent: bool = False
) -> None:
  """Opens Nearby and enables save device on the device."""
  ad.adb.shell(
      _SETTINGS_PUT_GLOBAL_COMMAND.format(
          setting=_OPEN_NEARBY_SAVE_DEVICE_COMMAND, value=1
      )
  )
  ad.adb.shell(
      _SETTINGS_PUT_GLOBAL_COMMAND.format(
          setting=_OPEN_NEARBY_CONSENT_COMMAND, value=1
      )
  )

  ad.uia(textMatches='(?i)Done|Close').wait.click(_UI_OPERATION_TIMEOUT)
  open_fast_pair_saved_devices_page(ad)
  save_devices_label = ad.uia(textMatches='Automatically save devices')
  if not save_devices_label.wait.exists(_UI_OPERATION_TIMEOUT):
    if ad.uia(textMatches='(?i)Done|Close').wait.exists(
        _UI_OPERATION_TIMEOUT / 2
    ):
      ad.uia(textMatches='(?i)Done|Close').click()

  save_devices_switch = ad.uia(textMatches='Automatically save devices').right(
      clazz='android.widget.Switch'
  )
  if save_devices_switch.wait.exists(_UI_OPERATION_TIMEOUT):
    is_checked = save_devices_switch.info.get('checked')
    if not is_checked:
      ad.log.info(
          'Automatically save devices switch is OFF, clicking to enable...'
      )
      save_devices_switch.click()
    else:
      ad.log.info(
          'Automatically save devices switch is already ON, skipping click.'
      )
  else:
    ad.log.warning('Could not find the "Automatically save devices" switch.')

  if is_independent:
    ad.reboot()


def set_fast_pair_device_config(
    bt_device: tws_device.TwsDevice,
) -> None:
  """Sets the Fast Pair device name, model ID, and private key."""
  bt_device.set_name_and_fp_params(
      bluetooth_name=bt_device.config.get('device_name'),
      ble_name=bt_device.config.get('device_name'),
      model_id=bt_device.config.get('model_id'),
      private_key=bt_device.config.get('fp_privkey'),
  )
  time.sleep(_WAIT_FOR_BROADCAST_DELAY.total_seconds())


def open_fast_pair_connection_page(ad: android_device.AndroidDevice) -> None:
  """Opens the Fast Pair connection page on the device."""
  try:
    ad.adb.shell(_OPEN_FAST_PAIR_CONNECTION_PAGE_COMMAND)
  except adb.AdbError:
    ad.log.exception(
        'Failed to open Fast Pair connection page by ADB, try to using'
        ' UIAutomator.'
    )
    ad.adb.shell(_OPEN_SETTINGS_COMMAND)
    ad.uia(textMatches='Google services').wait.click(_UI_OPERATION_TIMEOUT)
    ad.uia(textMatches='All services').wait.click(_UI_OPERATION_TIMEOUT)
    ad.uia(textMatches='Devices').wait.click(_UI_OPERATION_TIMEOUT)


def open_fast_pair_saved_devices_page(ad: android_device.AndroidDevice) -> None:
  """Opens the Fast Pair saved devices page on the device."""
  open_fast_pair_connection_page(ad)
  ad.uia(textMatches='Done|Close').wait.click(_UI_OPERATION_TIMEOUT)
  ad.uia(textMatches='Saved devices').wait.click(_UI_OPERATION_TIMEOUT)


def back_to_home_screen(ad: android_device.AndroidDevice) -> None:
  """Navigates back to the home screen on the device."""
  ad.adb.shell(_BACK_TO_HOME_SCREEN_COMMAND)
  time.sleep(1)


def clear_android_fast_pair_cache(
    ad: android_device.AndroidDevice, is_independent: bool = False
) -> None:
  """Clears Fast Pair cache.

  Fully clears out the Fast Pair cache storage in Nearby module by removing
  the corresponding DB files and force-stopping GMS Core.

  Args:
    ad: The Android device to clear Fast Pair cache.
    is_independent: Whether this function is called independently. If True,
      the device will reboot after clearing the cache.
  """
  try:
    ad.adb.shell(['rm', '-rf', _FAST_PAIR_DB_FOLDER])
    ad.adb.shell(['am', 'force-stop', _GMS_CORE_PACKAGE])
    if is_independent:
      ad.reboot()
  except adb.AdbError:
    ad.log.exception('No permission to clear fast pair cache.')


def close_wrong_fast_pair_page_and_connect_right_device(
    ad: android_device.AndroidDevice,
    device_name: str,
) -> bool:
  """Closes the wrong Fast Pair page and connects the right device."""
  if ad.uia(textContains=device_name).wait.exists(_UI_OPERATION_TIMEOUT):
    return ad.uia(textContains='Connect').wait.click(_UI_OPERATION_TIMEOUT)
  else:
    ad.uia(textMatches='Done|Close').wait.click(_UI_OPERATION_TIMEOUT)
    return False


def is_fast_pair_device_in_saved_devices(
    ad: android_device.AndroidDevice, device_name: str
) -> bool:
  """Returns true if the Fast Pair device is in saved devices."""
  back_to_home_screen(ad)
  open_fast_pair_saved_devices_page(ad)
  ad.uia(textMatches='Done|Close').wait.click(_UI_OPERATION_TIMEOUT)
  return ad.uia(textContains=device_name).wait.exists(_UI_OPERATION_TIMEOUT)


def connect_devices_in_ref_phone(
    ad: android_device.AndroidDevice, device_name: str
) -> bool:
  """Connects the devices in the ref phone."""
  ad.log.info('Connect devices in ref phone: %s', device_name)
  back_to_home_screen(ad)
  ad.log.info('Open fast pair connection page')
  open_fast_pair_connection_page(ad)
  ad.log.info('Click device name')
  return ad.uia(textContains=device_name).wait.click(_UI_OPERATION_TIMEOUT)
