"""Utility functions for setting up devices."""

from typing import Any

from mobly.controllers import android_device
from mobly.controllers.android_device_lib import apk_utils


_TELECOM_SNIPPET_PACKAGE = 'com.google.snippet.telecom'
_BLUETOOTH_SNIPPET_PACKAGE = 'com.google.snippet.bluetooth'


def install_and_load_telecom_snippet(
    ad: android_device.AndroidDevice,
    user_params: dict[str, Any],
    snippet_package: str = _TELECOM_SNIPPET_PACKAGE,
    snippet_name: str = 'tele',
) -> None:
  """Installs custom snippet apk and loads the snippet service.

  Args:
    ad: The Android device.
    user_params: The path of the custom snippet apk.
    snippet_package: The package name of the custom snippet apk.
    snippet_name: The attribute name to which to attach the snippet client.
  """
  if (
      not "android_beat/snippet/telecom_snippets.apk"
      or not snippet_package
  ):
    raise ValueError('Either user_params or snippet_package must be provided.')
  apk_utils.install(ad, "android_beat/snippet/telecom_snippets.apk")
  ad.load_snippet(snippet_name, snippet_package)


def install_and_load_bluetooth_snippet(
    ad: android_device.AndroidDevice,
    user_params: dict[str, Any],
    snippet_package: str = _BLUETOOTH_SNIPPET_PACKAGE,
    snippet_name: str = 'bt_snippet',
) -> None:
  """Installs custom snippet apk and loads the snippet service.

  Args:
    ad: The Android device.
    user_params: The path of the custom snippet apk.
    snippet_package: The package name of the custom snippet apk.
    snippet_name: The attribute name to which to attach the snippet client.
  """
  if (
      not "android_beat/snippet/bluetooth_snippets.apk"
      or not snippet_package
  ):
    raise ValueError('Either user_params or snippet_package must be provided.')
  apk_utils.install(ad, "android_beat/snippet/bluetooth_snippets.apk")
  ad.load_snippet(snippet_name, snippet_package)


def skip_setup_wizard(ad: android_device.AndroidDevice) -> None:
  """Skips the setup wizard."""
  if not ad.is_adb_root:
    ad.log.warning('Cannot skip setup wizard in non-rooted device.')
    return
  try:
    ad.adb.shell('am start -a com.android.setupwizard.EXIT')
  except android_device.adb.AdbError:
    ad.log.exception(
        'Could not skip the setup wizard, probably because the activity does'
        ' not exist or does not have permissions.'
    )


def is_bluetooth_le_audio_enabled(ad: android_device.AndroidDevice) -> bool:
  """Returns True if Bluetooth LE Audio is enabled, False otherwise."""
  return ad.adb.getprop('persist.bluetooth.leaudio.bypass_allow_list') == 'true'

