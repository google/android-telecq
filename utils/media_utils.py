"""Utility functions for media related operations."""

import datetime

from mobly.controllers import android_device

from bluetooth.utils import test_utils


_MEDIA_PLAY_TIME = datetime.timedelta(seconds=60)
_STATUS_WAIT_TIMEOUT = datetime.timedelta(seconds=10)
_BLUETOOTH_PROFILE_CONNECTION_TIMEOUT = datetime.timedelta(seconds=45)
_MEDIA_LOCAL_PARENT_PATH = '/sdcard/Download'


def play_media_on_android_device(
    ad: android_device.AndroidDevice,
    media_file_path: str,
) -> None:
  """Plays media on Android device."""
  ad.bt_snippet.media3StartLocalFile(media_file_path)
  ad.log.info('Start playing audio...')

  test_utils.wait_until_or_assert(
      condition=ad.bt_snippet.media3IsPlayerPlaying,
      error_msg='Failed to start playing media on Android device',
      timeout=_MEDIA_PLAY_TIME,
  )


def wait_for_a2dp_state(
    ad: android_device.AndroidDevice,
    bt_address: str,
    expected_a2dp_state: bool,
) -> None:
  """Checks if A2DP is playing."""

  test_utils.wait_until_or_assert(
      condition=lambda: ad.bt_snippet.btIsA2dpPlaying(bt_address)
      == expected_a2dp_state,
      error_msg=(
          'A2DP state is not correct. Expected:'
          f' {expected_a2dp_state} but got:'
          f' {ad.bt_snippet.btIsA2dpPlaying(bt_address)}'
      ),
      timeout=_STATUS_WAIT_TIMEOUT,
  )


def wait_for_media3_playing_state(
    ad: android_device.AndroidDevice,
    expected_media3_playing_state: bool,
) -> None:
  """Waits for media3 is player playing state."""

  test_utils.wait_until_or_assert(
      condition=lambda: ad.bt_snippet.media3IsPlayerPlaying()
      == expected_media3_playing_state,
      error_msg=(
          'Media3 is player playing is not correct. Expected:'
          f' {expected_media3_playing_state} but got:'
          f' {ad.bt_snippet.media3IsPlayerPlaying()}'
      ),
      timeout=_STATUS_WAIT_TIMEOUT,
  )


def wait_for_music_active_state(
    ad: android_device.AndroidDevice,
    *,
    expected_music_state: bool,
) -> None:
  """Waits for is music active state."""

  test_utils.wait_until_or_assert(
      condition=lambda: ad.bt_snippet.media3IsMusicActive()
      == expected_music_state,
      error_msg=(
          'Music state is not correct. Expected:'
          f'{expected_music_state} but got:'
          f' {ad.bt_snippet.media3IsMusicActive()}'
      ),
      timeout=_STATUS_WAIT_TIMEOUT,
  )


def push_call_test_audio_file(
    ad: android_device.AndroidDevice,
    host_file_path: str,
) -> None:
  """Pushes the telecom test audio file to the device.

  Args:
    ad: The Android device that needs to push the audio file.
    host_file_path: The path of the audio file on the host.
  """
  ad.log.info(
      'Pushing %s to %s',
      host_file_path,
      _MEDIA_LOCAL_PARENT_PATH,
  )
  ad.adb.push([host_file_path, _MEDIA_LOCAL_PARENT_PATH])
  ad.log.info('Pushed %s to %s', host_file_path, _MEDIA_LOCAL_PARENT_PATH)


def stop_media_on_android_device(
    ad: android_device.AndroidDevice,
) -> None:
  """Stops currently playing media on Android device.

  Args:
    ad: The Android device.
  """
  if ad.bt_snippet.media3IsPlayerPlaying():
    ad.log.info('Stopping currently playing media.')
    ad.bt_snippet.media3Stop()
    wait_for_media3_playing_state(ad, expected_media3_playing_state=False)
    ad.log.info('Media stopped.')
  else:
    ad.log.info('No media is currently playing.')


def wait_for_lea_state(
    ad: android_device.AndroidDevice,
    bluetooth_address: str,
    *,
    expect_lea_active: bool,
    timeout: datetime.timedelta = _BLUETOOTH_PROFILE_CONNECTION_TIMEOUT,
) -> None:
  """Waits for LEA to be expect_active to Bluetooth device.

  Args:
    ad: The Android device used to check connection with the Bluetooth LE Audio
      device.
    bluetooth_address: The Bluetooth address of the LE Audio device.
    expect_lea_active: The expected state of LE Audio connection. True if the
      expected LE Audio connection is active, False otherwise.
    timeout: The timeout for waiting for LE Audio to be expected Le Audio
      connection state.

  Raises:
    signals.TestFailure: If the LE Audio state is not expected Le Audio
      connection state after timeout.
  """
  lea_state = ad.bt_snippet.btIsLeAudioConnected(bluetooth_address)
  ad.log.info('LE Audio state: %s', lea_state)
  test_utils.wait_until_or_assert(
      condition=lambda: lea_state == expect_lea_active,
      error_msg=(
          'Failed to get expected state of Bluetooth device LE Audio profile. '
          f'Expected: {expect_lea_active}, Actual: {lea_state}.'
      ),
      timeout=timeout,
  )


def restart_call_audio_on_ref2(
    ad_ref_2: android_device.AndroidDevice,
    call_audio_file_path: str,
) -> None:
  """Stops and restarts call audio playback on ad_ref_2."""
  stop_media_on_android_device(ad_ref_2)
  play_media_on_android_device(ad_ref_2, call_audio_file_path)
