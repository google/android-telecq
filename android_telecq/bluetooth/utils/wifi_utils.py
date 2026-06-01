"""Utility functions for WiFi operations."""

import dataclasses
import datetime
import logging
import time

from mobly.controllers import android_device
from mobly.snippet import errors
import tenacity

from android_telecq.bluetooth.utils import test_utils


_WAIT_FOR_DATA_CONNECTION = datetime.timedelta(seconds=60)
_WAIT_FOR_WIFI_ENABLE = datetime.timedelta(seconds=3)


@dataclasses.dataclass(frozen=True)
class WifiInfo:
  """Wi-Fi information."""

  ssid: str
  password: str | None = None
  bssid: str | None = None

  def to_dict(self) -> dict[str, int | str]:
    """Converts to a dict which can be accepted by MBS."""
    wifi_info = {'SSID': self.ssid}
    if self.password is not None:
      wifi_info['password'] = self.password
    if self.bssid is not None:
      wifi_info['BSSID'] = self.bssid
    return wifi_info


def connect_to_wifi(
    ad: android_device.AndroidDevice,
    wifi_ssid: str,
    wifi_password: str | None = None,
) -> None:
  """Connects the device to the specified WiFi network."""
  ad.log.info('Connecting to WiFi SSID: %s', wifi_ssid)
  wifi_info = WifiInfo(ssid=wifi_ssid, password=wifi_password)
  try:
    ad.bt_snippet.wifiConnect(wifi_info.to_dict())
  except errors.ApiError:
    ad.log.info('Failed to connect to WiFi SSID: %s', wifi_ssid)


def is_data_connected(ad: android_device.AndroidDevice) -> bool:
  """Checks if the device is connected to the data network."""
  return ad.bt_snippet.isWifiConnected()


def wait_for_data_connected(ad: android_device.AndroidDevice) -> None:
  """Waits for the device to be connected to the data network."""
  test_utils.wait_until_or_assert(
      condition=lambda: is_data_connected(ad),
      error_msg='Failed to connect to data network',
      timeout=_WAIT_FOR_DATA_CONNECTION,
  )


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, max=10),
    before_sleep=tenacity.before_sleep_log(
        logging.getLogger(__name__), logging.INFO
    ),
)
def connect_to_wifi_and_wait_for_data_connected(
    ad: android_device.AndroidDevice,
    wifi_ssid: str,
    wifi_password: str | None = None,
) -> None:
  """Connects to the specified WiFi network and waits for data connection.

  This function enables WiFi, connects to the given SSID with an optional
  password, and then waits until a data connection is established.

  Args:
    ad: The Android device to perform the operation on.
    wifi_ssid: The SSID of the WiFi network.
    wifi_password: The password for the WiFi network, if required.
  """
  ad.bt_snippet.wifiEnable()
  time.sleep(_WAIT_FOR_WIFI_ENABLE.total_seconds())
  connect_to_wifi(ad, wifi_ssid, wifi_password)
  wait_for_data_connected(ad)


def connect_wifi_if_need(
    ad: android_device.AndroidDevice,
    has_wifi: bool,
    wifi_ssid: str | None,
    wifi_password: str | None = None,
) -> None:
  """Connects to the specified WiFi network if has_wifi is True."""
  if not wifi_ssid and has_wifi:
    raise ValueError('WiFi SSID is None.')
  if has_wifi:
    connect_to_wifi_and_wait_for_data_connected(ad, wifi_ssid, wifi_password)


def disconnect_wifi_if_has_wifi(
    ad: android_device.AndroidDevice, has_wifi: bool
) -> None:
  """Turns off Wi-Fi if has_wifi is True.

  Args:
    ad: The Android device to perform the operation on.
    has_wifi: Whether the device has Wi-Fi.
  """
  if has_wifi:
    ad.bt_snippet.wifiClearConfiguredNetworks()
    ad.bt_snippet.wifiDisable()


def reconnect_wifi_if_data_connection_lost(
    ad: android_device.AndroidDevice,
    has_wifi: bool,
    wifi_ssid: str | None,
    wifi_password: str | None = None,
) -> None:
  """Checks the data connection and reconnect if needed."""
  if wifi_ssid is None and has_wifi:
    raise ValueError('WiFi SSID is None.')
  if has_wifi and not is_data_connected(ad):
    connect_to_wifi_and_wait_for_data_connected(ad, wifi_ssid, wifi_password)
