"""Base test for telecom tests."""

import enum
import logging
import shutil
import time

from mobly import asserts
from mobly import base_test
from mobly import records
from mobly import utils as mobly_utils
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb
from mobly.snippet import errors
from snippet_uiautomator import uiautomator

from android_beat.bluetooth.platforms.bluetooth import bluetooth_reference_device
from android_beat.bluetooth.platforms.bluetooth import tws_device
from android_beat.bluetooth.utils import audio_utils
from android_beat.bluetooth.utils import bluetooth_utils
from android_beat import call_audio_state
from android_beat import device_setup_utils
from android_beat.utils import media_utils as telecom_media_utils
from android_beat.utils import telecom_utils

from mobly.controllers.android_device_lib.services import screen_recorder
from android_beat.bluetooth.platforms.android.services.logcat import logcat_pubsub_service

_TELECOM_SNIPPET_PACKAGE = 'com.google.snippet.telecom'
MEDIA_LOCAL_PARENT_PATH = '/sdcard/Download'
MEDIA_FILE_NAME = 'sine_tone.wav'


@enum.unique
class TelecomBaseState(enum.Enum):
  LEA = enum.auto()
  HFP = enum.auto()


@enum.unique
class TelecomBaseDeviceNum(enum.IntEnum):
  SINGLE_DEVICE = 1
  DOUBLE_DEVICE = 2
  TRIPLE_DEVICE = 3


@enum.unique
class BluetoothDeviceAmount(enum.IntEnum):
  """The required quantity of Bluetooth devices for a given test execution."""

  SINGLE_DEVICE = 1
  TWO_DEVICES = 2


@enum.unique
class RecordTiming(enum.Enum):
  """Record timing for telecom tests.

  These variables are used to determine the configuration of scrcpy recording.
  If recording starts before call accepted, register it with
  VOICE_CALL_DOWN_LINK audio source config.
  If recording starts after call accepted, register it with default audio
  source config(full conversation).

  Attributes:
    BEFORE_CALL_ACCEPTED: Start scrcpy recording before call accepted.
    AFTER_CALL_ACCEPTED: Start scrcpy recording after call accepted.
  """

  BEFORE_CALL_ACCEPTED = enum.auto()
  AFTER_CALL_ACCEPTED = enum.auto()


class AdbLogHandler(logging.Handler):
  """Custom log handler to sync Mobly logs to Android Logcat."""

  def __init__(self, ad: android_device.AndroidDevice):
    super().__init__()
    self.ad = ad
    self.serial = ad.serial

  def emit(self, record):
    try:
      log_msg = record.getMessage()
      if self.serial not in log_msg:
        return
      log_entry = self.format(record)
      if record.levelno >= logging.INFO:
        self.ad.adb.shell(f'log -t TelecomAutomation "{log_entry}"')
    except adb.AdbError:
      self.handleError(record)


class TelecomBaseTest(base_test.BaseTestClass):
  """Base test for telecom tests.

  Attributes:
    ad: The primary Android device under test, a SIM card is required.
    ad_ref: The reference Android device, if available, a SIM card is required.
    ad_ref_2: The second reference Android device, if available. This device is
      used for playing audio, and a SIM card is not required.
    bt_device: The Bluetooth device under test.
    bt_address_primary: The Bluetooth address of the primary earbud.
    bt_address_secondary: The Bluetooth address of the secondary earbud.
    ad_phone_number: The phone number of the primary Android device.
    ad_ref_phone_number: The phone number of the reference Android device, if
      ad_ref is provided.
    ad_address: The Bluetooth address of the primary Android device.
    recorded_audio_file: A list of paths to recorded audio files.
  """

  _REQUIRE_BLUETOOTH = True
  _BT_DEVICE_AMOUNT = BluetoothDeviceAmount.SINGLE_DEVICE
  _BLUETOOTH_MODE = TelecomBaseState.HFP
  _RECORD_TIMING = RecordTiming.AFTER_CALL_ACCEPTED
  _IS_VOIP_TEST = False
  _NEED_REBOOT = True
  _DEVICE_NUM = TelecomBaseDeviceNum.TRIPLE_DEVICE
  _TELECOM_LOG_TAG = True

  devices: list[android_device.AndroidDevice]
  ad: android_device.AndroidDevice
  ad_ref: android_device.AndroidDevice | None = None
  ad_ref_2: android_device.AndroidDevice | None = None
  bt_device: tws_device.TwsDevice
  bt_address_primary: str
  bt_address_secondary: str
  record_timing = RecordTiming.AFTER_CALL_ACCEPTED

  def is_bluetooth_le_audio_enabled(
      self, ad: android_device.AndroidDevice
  ) -> bool:
    """Returns True if Bluetooth LE Audio is enabled, False otherwise."""
    return (
        ad.adb.getprop('persist.bluetooth.leaudio.bypass_allow_list') == 'true'
    )

  def switch_bluetooth_le_audio(
      self, ad: android_device.AndroidDevice, bluetooth_mode: TelecomBaseState
  ) -> None:
    """Switches Bluetooth LE Audio."""
    if not ad.is_adb_root:
      ad.log.warning('Cannot switch bluetooth le audio in non-rooted device.')
      return
    if bluetooth_mode == TelecomBaseState.LEA:
      if self.is_bluetooth_le_audio_enabled(ad):
        ad.log.info('Bluetooth LE Audio is already enabled.')
        return
      ad.adb.shell('setprop persist.bluetooth.leaudio.bypass_allow_list true')
      ad.reboot()
      asserts.assert_true(
          self.is_bluetooth_le_audio_enabled(ad),
          'Failed to enable Bluetooth LE Audio',
      )
    elif bluetooth_mode == TelecomBaseState.HFP:
      if not self.is_bluetooth_le_audio_enabled(ad):
        ad.log.info('Bluetooth LE Audio is already disabled.')
        return
      ad.adb.shell('setprop persist.bluetooth.leaudio.bypass_allow_list false')
      ad.reboot()
      asserts.assert_false(
          self.is_bluetooth_le_audio_enabled(ad),
          'Failed to disable Bluetooth LE Audio',
      )

  def _setup_device_logging(self, ad: android_device.AndroidDevice) -> None:
    """Sets up custom logging for the Android device."""
    handler = AdbLogHandler(ad)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    target_logger = getattr(ad.log, 'logger', ad.log)
    if hasattr(target_logger, 'addHandler'):
      target_logger.addHandler(handler)
      target_logger.propagate = False

  def _setup_android_device(self, ad: android_device.AndroidDevice) -> None:
    """Sets up the Android device."""
    if self._NEED_REBOOT:
      ad.reboot()
    if ad in [self.ad, self.ad_ref]:
      video_alias = 'video'
      ad.services.register(video_alias, screen_recorder.ScreenRecorder)
    if self._REQUIRE_BLUETOOTH:
      self.switch_bluetooth_le_audio(
          ad,
          bluetooth_mode=self._BLUETOOTH_MODE,
      )
    ad.adb.shell('settings put global package_verifier_enable 0')
    ad.adb.shell('settings put global verifier_verify_adb_installs 0')
    device_setup_utils.install_and_load_bluetooth_snippet(
        ad,
        self.user_params,
    )
    device_setup_utils.install_and_load_telecom_snippet(
        ad,
        self.user_params,
    )
    ad.ui = uiautomator.UiDevice(ui=ad.bt_snippet)
    ad.uia = ad.ui
    ad.adb.shell('svc bluetooth enable')
    # Clear saved devices before test starts
    if self._REQUIRE_BLUETOOTH:
      bluetooth_utils.clear_saved_devices(ad)
    ad.services.register(
        'logcat_pubsub', logcat_pubsub_service.LogcatPublisherService
    )

  def setup_class(self) -> None:
    telecom_utils.patch_local_file_paths(self.user_params)
    self.media_file_path = f'{MEDIA_LOCAL_PARENT_PATH}/{MEDIA_FILE_NAME}'
    self.devices = self.register_controller(
        android_device, min_number=self._DEVICE_NUM
    )
    self.ad = self.devices[0]
    sdk_version = int(self.ad.build_info['build_version_sdk'])
    asserts.skip_if(
        self._IS_VOIP_TEST and sdk_version < 34,
        'VoIP tests require SDK version 34 or higher, but current version is'
        f' {sdk_version}.',
    )
    if self._DEVICE_NUM > 1:
      self.ad_ref = self.devices[1]
    if self._DEVICE_NUM > 2:
      self.ad_ref_2 = self.devices[2]
    self.ad.debug_tag += 'DUT'
    if self.ad_ref:
      self.ad_ref.debug_tag += 'REF'
    if self.ad_ref_2:
      self.ad_ref_2.debug_tag += 'REF2'

    if self._TELECOM_LOG_TAG:
      mobly_utils.concurrent_exec(
          self._setup_device_logging,
          [[d] for d in self.devices],
          raise_on_exception=True,
      )
    mobly_utils.concurrent_exec(
        self._setup_android_device,
        [[d] for d in self.devices],
        raise_on_exception=True,
    )
    if self._REQUIRE_BLUETOOTH:
      self.bt_device = self.register_controller(bluetooth_reference_device)
      self.bt_address_primary = self.bt_device[0].bluetooth_address_primary
      self.bt_address_secondary = self.bt_device[0].bluetooth_address_secondary
      self.bt_device, self.bt_device_ref = (
          bluetooth_utils.reset_bluetooth_devices(
              self.bt_device,
              self._BT_DEVICE_AMOUNT,
          )
      )
      # Pair devices for each test
      bluetooth_utils.pair_and_assert_bluetooth_state(
          self.ad,
          [self.bt_device],
          self._BLUETOOTH_MODE == TelecomBaseState.LEA,
      )
    telecom_utils.patch_local_device_dimensions(self.user_params, self.devices)
    
    call_audio_files = self.user_params.get('telecom_test_call_audio', [])
    asserts.assert_true(
        call_audio_files, 'No call audio file provided in mh_files.'
    )
    # Set up the reference device phone number
    self.ad_phone_number = telecom_utils.get_phone_number(self.ad)
    if self.ad_ref:
      self.ad_ref_phone_number = telecom_utils.get_phone_number(self.ad_ref)
    audio_utils.generate_and_push_audio_files_to_device(
        self.ad,
        [MEDIA_FILE_NAME],
        self.current_test_info.output_path,
    )
    # Push test call audio file once per class setup
    if self.ad_ref_2:
      telecom_media_utils.push_call_test_audio_file(
          self.ad_ref_2,
          call_audio_files[0],
      )
      # Set the media volume in ad_ref_2 device to maximum.
      # This is for achieving optimal sound clarity in audio recordings.
      max_music_volume = self.ad_ref_2.bt_snippet.getMusicMaxVolume()
      self.ad_ref_2.bt_snippet.setMusicVolume(max_music_volume)
    for ad in self.devices:
      # Set the ringer mode to 2 and ring volume to maximum.
      ad.adb.shell('cmd notification set_dnd off')
      ad.adb.shell('settings put global zen_mode 0')

  def setup_test(self) -> None:
    if self._REQUIRE_BLUETOOTH:
      is_classic_disconnected = (
          self._BLUETOOTH_MODE == TelecomBaseState.HFP
          and not self.ad.bt_snippet.btIsA2dpConnected(self.bt_address_primary)
      )
      is_lea_disconnected = (
          self._BLUETOOTH_MODE == TelecomBaseState.LEA
          and not self.ad.bt_snippet.btIsLeAudioConnected(
              self.bt_address_primary
          )
      )
      if is_classic_disconnected or is_lea_disconnected:
        self.ad.log.info('Bluetooth connection lost, re-pairing devices.')
        bluetooth_utils.clear_saved_devices(self.ad, [self.bt_address_primary])
        self.bt_device.factory_reset()
        bluetooth_utils.pair_bluetooth_device(self.ad, self.bt_device)
    # Register the screen recorder v2.
    for devices in [self.ad, self.ad_ref]:
      if not devices:
        continue
      if self.record_timing == RecordTiming.AFTER_CALL_ACCEPTED:
        devices.log.info('Current record timing is AFTER_CALL_ACCEPTED')
        # If recording starts after call accepted, register it with
        # VOICE_CALL_DOWN_LINK audio source config.
        devices.services.register(
            'screen_recorder',
            screen_recorder.ScreenRecorder,
            screen_recorder.Configs(
                enable_audio=True,
                save_audio_file=True,
                audio_source="voice-call-downlink",
                restart_after_create_excerpts=False,
            ),
            start_service=False,
        )
      elif self.record_timing == RecordTiming.BEFORE_CALL_ACCEPTED:
        devices.log.info('Current record timing is BEFORE_CALL_ACCEPTED')
        # If recording starts before call accepted, register it with
        # default audio source config(full conversation).
        devices.services.register(
            'screen_recorder',
            screen_recorder.ScreenRecorder,
            screen_recorder.Configs(
                enable_audio=True,
                save_audio_file=True,
                restart_after_create_excerpts=False,
            ),
            start_service=False,
        )

    self.recorded_audio_file = []
    self.record_data({
        'Test Name': self.current_test_info.name,
        'sponge_properties': {
            'beto_team': 'Telecom',
            'beto_feature': 'Telecom',
        },
    })
    # Set default dialer.
    mobly_utils.concurrent_exec(
        lambda d: telecom_utils.set_default_dialer(d, _TELECOM_SNIPPET_PACKAGE),
        [[d] for d in self.devices],
        raise_on_exception=True,
    )

  def teardown_test(self) -> None:
    self.ad.adb.shell('cmd phone emergency-number-test-mode -c')
    for device in [self.ad, self.ad_ref]:
      if device is None:
        continue
      if hasattr(device.services, 'screen_recorder'):
        device.services.unregister('screen_recorder')
        device.services.create_output_excerpts_all(self.current_test_info)
    self.ad.tele.telecomEndAllCalls()
    self.ad.tele.unregisterTransactionalPhoneAccount()
    if self.ad_ref_2:
      telecom_media_utils.stop_media_on_android_device(self.ad_ref_2)
    self.ad.bt_snippet.media3ClearPlaylist()
    self.ad.bt_snippet.media3Stop()
    try:
      self.ad.tele.telecomSetAudioState(
          call_audio_state.CallAudioState.get_earpiece_state()
      )
    except errors.ApiError:
      self.ad.log.exception('Could not reset audio state, skipping this error.')
    time.sleep(3)
    self.ad.tele.stopCallAudio()
    self.ad.services.create_output_excerpts_all(self.current_test_info)
    if self.recorded_audio_file:
      for audio_file in self.recorded_audio_file:
        logging.info(
            'Moving recorded audio file %s to %s',
            audio_file,
            self.current_test_info.output_path,
        )
        try:
          new_path = shutil.move(audio_file, self.current_test_info.output_path)
          logging.info('Successfully moved to %s', new_path)
        except (shutil.Error, OSError) as e:
          logging.warning(
              'Failed to move recorded audio file %s: %s',
              audio_file,
              e,
          )
    self.recorded_audio_file = []
    if self._REQUIRE_BLUETOOTH:
      self.bt_device.create_output_excerpts(self.current_test_info)

  def on_fail(self, record: records.TestResultRecord) -> None:
    android_device.take_bug_reports(
        self.devices,
        destination=self.current_test_info.output_path,
    )

  def teardown_class(self):
    if self._REQUIRE_BLUETOOTH:
      bluetooth_utils.clear_saved_devices(self.ad)
    self.ad.log.info('Removing pushed audio files from device...')
    paths_to_delete = [self.media_file_path]

    # Only delete the file under _PLAYLIST_PATHS
    for device_path in paths_to_delete:
      self.ad.adb.shell(['rm', '-f', device_path])
      self.ad.log.info('Removed %s', device_path)
    self.ad.log.info('Resetting default dialer...')
    mobly_utils.concurrent_exec(
        telecom_utils.reset_default_dialer,
        [[d] for d in self.devices],
        raise_on_exception=True,
    )
