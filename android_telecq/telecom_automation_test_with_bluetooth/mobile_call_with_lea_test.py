"""Voice Call Tests with LEA Headset."""

import datetime
import time

from mobly import test_runner

from android_telecq.bluetooth.utils import bluetooth_utils
from android_telecq.bluetooth.utils import call_utils
from android_telecq.bluetooth.utils import test_utils
from android_telecq import call_audio_state
from android_telecq import telecom_base_test
from android_telecq.utils import media_utils as telecom_media_utils
from android_telecq.utils import telecom_utils

_CallAudioState = call_audio_state.CallAudioState
_CALL_DURATION_TIMEOUT = datetime.timedelta(seconds=20)
_STATUS_WAIT_TIMEOUT = datetime.timedelta(seconds=30)
_AUDIO_ROUTE_SWITCH_TIMEOUT = datetime.timedelta(seconds=10)
_AUDIO_PLAYBACK_DURATION_TIMEOUT = datetime.timedelta(seconds=10)

_MEDIA_LOCAL_PARENT_PATH = '/sdcard/Download'
_MEDIA_FILE_NAME = 'sine_tone.wav'
_CALL_AUDIO_FILE_NAME = 'telecom_test_call_audio.ogg'
_MEDIA_FILE_PATH = f'{_MEDIA_LOCAL_PARENT_PATH}/{_MEDIA_FILE_NAME}'
_CALL_AUDIO_FILE_PATH = f'{_MEDIA_LOCAL_PARENT_PATH}/{_CALL_AUDIO_FILE_NAME}'


class MobileCallWithLeaTest(telecom_base_test.TelecomBaseTest):
  """Mobile Call with LEA Headset Tests.

  Test predictions:
  1. 3 Android devices with SIM cards.
  2. 1 pair of TWS devices(primary and secondary).
  """

  _BLUETOOTH_MODE = telecom_base_test.TelecomBaseState.LEA

  def setup_test(self):
    """Sets up the test environment before each test method."""
    # Determines whether to apply the audio_source parameter.
    # This configuration is valid only after the call has been established. If
    # the recording begins prior to call connection (e.g., capturing a
    # ringtone), the default setting (full-conversation) must be used;
    # otherwise, the test will crash.
    before_call_accepted_tests = [
        'test_incoming_call_ringtone_through_lea_headset',
        'test_outgoing_call_through_lea_headset_during_media_playback',
        'test_incoming_call_through_lea_headset_during_media_playback',
    ]
    if self.current_test_info.name in before_call_accepted_tests:
      self.record_timing = telecom_base_test.RecordTiming.BEFORE_CALL_ACCEPTED
    else:
      self.record_timing = telecom_base_test.RecordTiming.AFTER_CALL_ACCEPTED
    super().setup_test()

  def test_outgoing_call_through_lea_headset(self):
    """Test outgoing call through LEA headset.

    Objective:
      To verify an outgoing call can be successfully established and audio is
      routed through the LEA headset.

    Test Predictions:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. DUT initiates a call to REF, and REF answers the call.
      2. REF2 plays audio to simulate voice from far-end.
      3. DUT ends the call.

    Pass Criteria:
      1. The call can be established and audio is routed through the LEA
         headset, verifed via BES Audio Recorder.
      2. The call state is STATE_DISCONNECTED via the onStateChanged callback
         after call is terminated.
    """
    # Originates a call from DUT to the REF number.
    self.ad.log.info('Originating call to %s', self.ad_ref_phone_number)
    self.ad.tele.telecomPlaceCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to place call to {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is placed', self.ad_ref_phone_number)

    # Wait for a call from DUT to REF number ringing.
    self.ad.log.info(
        'Waiting for call from %s to start ringing on REF', self.ad_phone_number
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad_ref} Failed to receive call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call from %s is ringing on REF', self.ad_phone_number)

    # Accepts a call from DUT to the REF number.
    self.ad.log.info('Accepting call from %s on REF', self.ad_phone_number)
    self.ad_ref.tele.telecomAcceptRingingCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_ACTIVE,
        error_msg=(
            f'{self.ad_ref} Failed to accept call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call from %s is accepted on REF', self.ad_phone_number)
    # Waits for the call audio state to be bluetooth.
    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
    try:
      telecom_media_utils.play_media_on_android_device(
          self.ad_ref_2, _CALL_AUDIO_FILE_PATH
      )
    finally:
      telecom_media_utils.stop_media_on_android_device(self.ad_ref_2)

    # Ends the call from DUT to the REF number.
    self.ad.log.info('Ending call with %s', self.ad_ref_phone_number)
    self.ad.tele.telecomEndCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to end the ongoing call with'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ended', self.ad_ref_phone_number)

  def test_outgoing_call_through_lea_headset_during_media_playback(self):
    """Test outgoing call through LEA headset during media playback.

    Objective:
      To verify an outgoing call can correctly preempts and resumes media which
      is routed through the LEA headset.

    Test Predictions:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. DUT plays a local media.
      2. DUT initiates a call to REF, and REF answers the call.
      3. REF2 plays audio to simulate voice from far-end.
      4. DUT ends the call.

    Pass Criteria:
      1. Local media is played through the LEA headset before the call, verifed
         by a2dp state and BES Audio Recorder.
      2. The call can be established and local media is paused, verified by
         isMusicActive and BES Audio Recorder.
      3. Call audio is routed through the LEA headset, verifed via BES Audio
         Recorder.
      4. The call state is STATE_DISCONNECTED via the onStateChanged callback
         after call is terminated.
      5. Local media is resumed after the call, verifed by a2dp state,
         isMusicActive and BES Audio Recorder.
    """
    telecom_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.isAudioFocusGranted,
        error_msg='Audio focus is not granted.',
        timeout=_STATUS_WAIT_TIMEOUT,
    )
    telecom_media_utils.play_media_on_android_device(self.ad, _MEDIA_FILE_PATH)
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_address_primary
        ),
        error_msg='Media is not playing on LEA.',
        timeout=_STATUS_WAIT_TIMEOUT,
    )
    # Originates a call from DUT to the REF number.
    self.ad.log.info('Originating call to %s', self.ad_ref_phone_number)
    self.ad.tele.telecomPlaceCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to place call to {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is placed', self.ad_ref_phone_number)

    # Wait for a call from DUT to REF number ringing.
    self.ad.log.info(
        'Waiting for call from %s to start ringing on REF', self.ad_phone_number
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad_ref} Failed to receive call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call from %s is ringing on REF', self.ad_phone_number)

    # Accepts a call from DUT to REF number.
    self.ad.log.info('Accepting call from %s on REF', self.ad_phone_number)
    self.ad_ref.tele.telecomAcceptRingingCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_ACTIVE,
        error_msg=(
            f'{self.ad_ref} Failed to accept call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call from %s is accepted on REF', self.ad_phone_number)
    telecom_media_utils.wait_for_media3_playing_state(
        self.ad, expected_media3_playing_state=False
    )
    telecom_media_utils.wait_for_music_active_state(
        self.ad, expected_music_state=False
    )
    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
    try:
      telecom_media_utils.play_media_on_android_device(
          self.ad_ref_2, _CALL_AUDIO_FILE_PATH
      )
    finally:
      telecom_media_utils.stop_media_on_android_device(self.ad_ref_2)

    # Ends the call from DUT to REF number.
    self.ad.log.info('Ending call with %s', self.ad_ref_phone_number)
    self.ad.tele.telecomEndCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to end the ongoing call with'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ended', self.ad_ref_phone_number)
    telecom_media_utils.wait_for_media3_playing_state(
        self.ad, expected_media3_playing_state=True
    )
    telecom_media_utils.wait_for_music_active_state(
        self.ad, expected_music_state=True
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_address_primary
        ),
        error_msg='Media is not playing on LEA.',
        timeout=_STATUS_WAIT_TIMEOUT,
    )

  def test_incoming_call_ringtone_through_lea_headset(self):
    """Test incoming call ringtone through LEA headset.

    Objective:
      To verify an incoming call can be successfully routed ringtone through the
      LEA headset.

    Test Predictions:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. REF initiates a call to DUT
      2. After DUT start ringing, REF ends the call

    Pass Criteria:
      1. DUT is STATE_RINGING after REF initiates a call.
      2. Ringtone streams to BT device, verified by BES Audio Recorder.
      3. REF is STATE_DISCONNECTED after ends the call.
    """
    # Originates a call from REF to the DUT number.
    self.ad.log.info('Originating call to %s from REF', self.ad_phone_number)
    self.ad_ref.tele.telecomPlaceCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad_ref} Failed to place call to {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call to %s is placed on REF', self.ad_phone_number)

    # Wait for a call from REF to DUT number ringing.
    self.ad.log.info(
        'Waiting for call with %s to start ringing', self.ad_ref_phone_number
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad} Failed to receive call from {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', self.ad_ref_phone_number)

    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())

    # Ends the call from REF to the DUT number.
    self.ad.log.info('Ending call from %s on REF', self.ad_phone_number)
    self.ad_ref.tele.telecomEndCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to end the ongoing call with'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call from %s is ended on REF', self.ad_phone_number)

  def test_incoming_call_through_lea_headset(self):
    """Test incoming call through LEA headset.

    Objective:
      To verify an incoming call can be successfully established and audio is
      routed through the LEA headset.

    Prediction:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. REF initiates a call to DUT, and DUT answers the call.
      2. REF2 plays audio to simulate voice from far-end.
      3. REF ends the call.

    Pass Criteria:
      1. The call can be established and call audio is routed through the LEA
         headset, verifed via BES Audio Recorder.
      2. REF is STATE_DISCONNECTED after ends the call.
    """
    # Originates a call from REF to the DUT number.
    self.ad.log.info('Originating call to %s from REF', self.ad_phone_number)
    self.ad_ref.tele.telecomPlaceCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad_ref} Failed to place call to {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call to %s is placed on REF', self.ad_phone_number)

    # Wait for a call from REF to DUT number ringing.
    self.ad.log.info(
        'Waiting for call with %s to start ringing on REF',
        self.ad_ref_phone_number,
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad} Failed to receive call from {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', self.ad_ref_phone_number)

    # Accepts a call from DUT to the REF number.
    self.ad.log.info('Accepting call with %s', self.ad_ref_phone_number)
    self.ad.tele.telecomAcceptRingingCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_ACTIVE,
        error_msg=(
            f'{self.ad} Failed to accept call from {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is accepted', self.ad_ref_phone_number)
    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
    try:
      telecom_media_utils.play_media_on_android_device(
          self.ad_ref_2, _CALL_AUDIO_FILE_PATH
      )
    finally:
      telecom_media_utils.stop_media_on_android_device(self.ad_ref_2)

    # Ends the call from REF to the DUT number.
    self.ad.log.info('Ending call with %s on REF', self.ad_phone_number)
    self.ad_ref.tele.telecomEndCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to end the ongoing call with'
            f' {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call from %s is ended on REF', self.ad_phone_number)

  def test_incoming_call_through_lea_headset_during_media_playback(self):
    """Test incoming call through LEA headset during media playback.

    Objective:
      To verify an incoming call can correctly preempts and resumes media which
      is routed through the LEA headset.

    Prediction:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. DUT plays a local media.
      2. REF initiates a call to DUT, and DUT answers the call.
      3. REF2 plays audio to simulate voice from far-end.
      4. REF ends the call.

    Pass Prediction:
      1. Local media is played through the LEA headset before the call, verifed
         by a2dp state and BES Audio Recorder.
      2. The call can be established and local media is paused, verified by
         isMusicActive and BES Audio Recorder.
      3. Call audio is routed through the LEA headset, verifed via BES Audio
         Recorder.
      4. The call state is STATE_DISCONNECTED via the onStateChanged callback
         after call is terminated.
      5. Local media is resumed after the call, verifed by a2dp state,
         isMusicActive and BES Audio Recorder.
    """
    telecom_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.isAudioFocusGranted,
        error_msg='Audio focus is not granted.',
        timeout=_STATUS_WAIT_TIMEOUT,
    )
    telecom_media_utils.play_media_on_android_device(self.ad, _MEDIA_FILE_PATH)
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_address_primary
        ),
        error_msg='Media is not playing on LEA.',
        timeout=_STATUS_WAIT_TIMEOUT,
    )

    # Originates a call from REF to the DUT number.
    self.ad.log.info('Originating call to %s from REF', self.ad_phone_number)
    self.ad_ref.tele.telecomPlaceCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad_ref} Failed to place call to {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call to %s is placed on REF', self.ad_phone_number)
    # Wait for a call from REF to DUT number ringing.
    self.ad.log.info(
        'Waiting for call with %s to start ringing', self.ad_ref_phone_number
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad} Failed to receive call from {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', self.ad_ref_phone_number)

    # Accepts a call from DUT to the REF number.
    self.ad.log.info('Accepting call with %s', self.ad_ref_phone_number)
    self.ad.tele.telecomAcceptRingingCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_ACTIVE,
        error_msg=(
            f'{self.ad} Failed to accept call from {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is accepted', self.ad_ref_phone_number)

    telecom_media_utils.wait_for_media3_playing_state(
        self.ad, expected_media3_playing_state=False
    )
    telecom_media_utils.wait_for_music_active_state(
        self.ad, expected_music_state=False
    )
    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
    try:
      telecom_media_utils.play_media_on_android_device(
          self.ad_ref_2, _CALL_AUDIO_FILE_PATH
      )
    finally:
      telecom_media_utils.stop_media_on_android_device(self.ad_ref_2)

    # Ends the call from REF to the DUT number.
    self.ad.log.info('Ending call from %s on REF', self.ad_phone_number)
    self.ad_ref.tele.telecomEndCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to end the ongoing call with'
            f' {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call from %s is ended on REF', self.ad_phone_number)

    telecom_media_utils.wait_for_media3_playing_state(
        self.ad, expected_media3_playing_state=True
    )
    telecom_media_utils.wait_for_music_active_state(
        self.ad, expected_music_state=True
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_address_primary
        ),
        error_msg='Media is not playing on LEA.',
        timeout=_STATUS_WAIT_TIMEOUT,
    )
  # lea state.
  def _test_reject_incoming_call_through_lea_headset(self):
    """Test reject incoming call through LEA headset.

    Objective:
      To verify an incoming call can be successfully rejected through the LEA
      headset.

    Precondition:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. REF initiates a call to DUT
      2. BT device rejects the call

    Pass Criteria:
      1. DUT is STATE_RINGING after REF initiates a call.
      2. DUT is STATE_DISCONNECTED after REF rejects the call.
    """
    # Originates a call from REF to the DUT number.
    self.ad.log.info('Originating call to %s from REF', self.ad_phone_number)
    self.ad_ref.tele.telecomPlaceCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad_ref} Failed to place call to {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call to %s is placed on REF', self.ad_phone_number)
    # Wait for a call from REF to DUT number ringing.
    self.ad.log.info(
        'Waiting for call with %s to start ringing', self.ad_ref_phone_number
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad} Failed to receive call from {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', self.ad_ref_phone_number)

    # Ends the call from bluetooth device and verifies the call state.
    self.ad.log.info(
        'Ending call from %s via bluetooth device', self.ad_ref_phone_number
    )
    # call_decline self.bt_device.call_decline()
    call_utils.end_call(self.ad)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Bluetooth device failed to decline call from'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info(
        'Call from %s is ended from bluetooth device',
        self.ad_ref_phone_number,
    )
  # lea state.
  def _test_end_dialing_outgoing_call_through_lea_headset(self):
    """Test end dialing outgoing call through LEA headset.

    Objective:
      To verify a dialing outgoing call can be successfully ended through the
      LEA headset.

    Test Predictions:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. DUT initiates a call to REF, do not answer from REF.
      2. BT device ends the ongoing call.

    Pass Criteria:
      1. DUT is STATE_DIALING after initiates a call to REF.
      2. DUT is STATE_DISCONNECTED after REF rejects the call.
    """

    # Originates a call from DUT to the REF number.
    self.ad.log.info('Originating call to %s', self.ad_ref_phone_number)
    self.ad.tele.telecomPlaceCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to place call to {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call from %s is placed', self.ad_ref_phone_number)

    # Wait for a call from DUT to REF number ringing.
    self.ad.log.info(
        'Waiting for call with %s to start ringing', self.ad_phone_number
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad_ref} Failed to receive call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing on REF', self.ad_phone_number)

    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())

    # Ends the call from bluetooth device and verifies the call state.
    self.ad.log.info(
        'Ending call to %s via bluetooth device', self.ad_ref_phone_number
    )
    # self.bt_device.call_end()
    call_utils.end_call(self.ad)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Bluetooth device failed to end call to'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info(
        'Call with %s is ended from bluetooth device',
        self.ad_ref_phone_number,
    )
  # lea state.
  def _test_end_ongoing_outgoing_call_through_lea_headset(self):
    """Test end ongoing outgoing call through LEA headset.

    Objective:
      To verify an ongoing outgoing call can be successfully ended through the
      LEA headset.

    Test Predictions:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. DUT initiates a call to REF, and REF answers the call.
      2. BT device ends the ongoing call.

    Pass Criteria:
      1. The call can be established.
      2. DUT is STATE_DISCONNECTED after REF rejects the call.
    """

    # Originates a call from DUT to the REF number.
    self.ad.log.info('Originating call to %s', self.ad_ref_phone_number)
    self.ad.tele.telecomPlaceCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to place call to {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call from %s is placed', self.ad_ref_phone_number)

    # Wait for a call from DUT to REF number ringing.
    self.ad.log.info(
        'Waiting for call with %s to start ringing', self.ad_phone_number
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad_ref} Failed to receive call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing on REF', self.ad_phone_number)

    # Accepts a call from DUT to REF number.
    self.ad.log.info('Accepting call with %s on REF', self.ad_phone_number)
    self.ad_ref.tele.telecomAcceptRingingCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_ACTIVE,
        error_msg=(
            f'{self.ad_ref} Failed to accept call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is accepted on REF', self.ad_phone_number)

    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())

    # Ends the call from bluetooth device and verifies the call state.
    self.ad.log.info(
        'Ending call to %s via bluetooth device', self.ad_ref_phone_number
    )
    # self.bt_device.call_decline()
    call_utils.end_call(self.ad)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Bluetooth device failed to end call to'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info(
        'Call with %s is ended from bluetooth device', self.ad_ref_phone_number
    )
  # lea state.
  def _test_end_ongoing_incoming_call_through_lea_headset(self):
    """Test end ongoing incoming call through LEA headset.

    Objective:
      To verify an ongoing incoming call can be successfully ended through the
      LEA headset.

    Prediction:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps
      1. REF initiates a call to DUT, and DUT answers the call.
      2. BT device ends the ongoing call.

    Pass Criteria:
      1. The call can be established.
      2. Verify call audio streams to LEA device.
      3. DUT is STATE_DISCONNECTED after REF rejects the call.
    """

    # Originates a call from REF to the DUT number.
    self.ad.log.info('Originating call to %s from REF', self.ad_phone_number)
    self.ad_ref.tele.telecomPlaceCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad_ref} Failed to place call to {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call to %s is placed from REF', self.ad_phone_number)
    # Wait for a call from REF to DUT number ringing.
    self.ad.log.info('Waiting for call from %s', self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad} Failed to receive call from {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call from %s is ringing', self.ad_ref_phone_number)

    # Accepts a call from DUT to the REF number.
    self.ad.log.info('Accepting call from %s', self.ad_ref_phone_number)
    self.ad.tele.telecomAcceptRingingCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_ACTIVE,
        error_msg=(
            f'{self.ad} Failed to accept call from {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call from %s is accepted', self.ad_ref_phone_number)

    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())

    # Ends the call from bluetooth device and verifies the call state.
    self.ad.log.info(
        'Ending call from %s via bluetooth device',
        self.ad_ref_phone_number,
    )
    # call_decline self.bt_device.call_decline()
    call_utils.end_call(self.ad)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Bluetooth device failed to end call from'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info(
        'Call from %s is ended from bluetooth device',
        self.ad_ref_phone_number,
    )
  # Bluetooth function is toggled off and on in lea mode.
  def _test_mid_call_audio_route_switch_lea_headset_power_off_on(self):
    """Test mid call route switch when LEA headset is powered off and on.

    Objective:
      To verify audio can be routed between LEA headset and phone when headset
      is powered off/on during an active call.

    Prediction:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. DUT initiates a call to REF, and REF answers the call.
      2. During the call, REF2 plays audio to simulate voice from far-end.
      3. Power off BT device.
      4. Power on BT device.
      5. DUT ends the ongoing call.

    Pass Criteria:
      1. The call can be established and call audio is routed to LEA headset.
      2. Call audio is routed to earpiece after BT device is powered off.
      3. Call audio is routed to LEA headset after BT device is powered on.
      4. DUT is STATE_DISCONNECTED after BT device ends the call.
    """
    # Originates a call from DUT to the REF number.
    self.ad.log.info('Originating call to %s', self.ad_ref_phone_number)
    self.ad.tele.telecomPlaceCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to place call to {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call to %s is placed', self.ad_ref_phone_number)

    # Wait for a call from DUT to REF number ringing.
    self.ad.log.info(
        'Waiting for call from %s to start ringing on REF',
        self.ad_phone_number,
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad_ref} Failed to receive call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call from %s is ringing on REF', self.ad_phone_number)

    # Accepts a call from DUT to REF number.
    self.ad.log.info('Accepting call from %s on REF', self.ad_phone_number)
    self.ad_ref.tele.telecomAcceptRingingCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_ACTIVE,
        error_msg=(
            f'{self.ad_ref} Failed to accept call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call from %s is accepted on REF', self.ad_phone_number)

    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
    try:
      telecom_media_utils.play_media_on_android_device(
          self.ad_ref_2, _CALL_AUDIO_FILE_PATH
      )
      self.bt_device.power_off()
      self.ad.tele.waitForAudioState(_CallAudioState.get_earpiece_state())
      self.bt_device.power_on()
      self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
      time.sleep(_STATUS_WAIT_TIMEOUT.total_seconds())
    finally:
      telecom_media_utils.stop_media_on_android_device(self.ad_ref_2)
    # Ends the call from DUT to the REF number.
    self.ad.log.info('Ending call with %s', self.ad_ref_phone_number)
    self.ad.tele.telecomEndCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to end the ongoing call with'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ended', self.ad_ref_phone_number)
  # Bluetooth function is toggled off and on in lea mode.
  def _test_mid_call_audio_route_switch_lea_headset_power_on(self):
    """Test mid call route switch when LEA headset is powered on.

    Objective:
      To verify audio can be routed from phone to LEA headset when headset is
      powered on during an active call.

    Prediction:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. Power off BT device.
      2. DUT initiates a call to REF, and REF answers the call.
      3. During the call, REF2 plays audio to simulate voice from far-end.
      4. Power on BT device.
      5. DUT ends the ongoing call.

    Pass Criteria:
      1. The call can be established and call audio is routed to LEA headset.
      2. Call audio is routed to LEA headset after BT device is powered on.
      3. DUT is STATE_DISCONNECTED after DUT ends the call.
    """
    # Power off the BT device before the test.
    self.bt_device.power_off()
    telecom_utils.wait_until_or_assert(
        lambda: not self.ad.bt_snippet.btIsLeAudioConnected(self.bt_address),
        error_msg=f'{self.bt_device} Failed to power off the bluetooth device',
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    # Originates a call from DUT to the REF number.
    self.ad.log.info('Originating call to %s', self.ad_ref_phone_number)
    self.ad.tele.telecomPlaceCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to place call to {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is placed', self.ad_ref_phone_number)

    # Wait for a call from DUT to REF number ringing.
    self.ad.log.info('Waiting for call with %s', self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad_ref} Failed to receive call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', self.ad_phone_number)

    # Accepts a call from DUT to REF number.
    self.ad.log.info('Accepting call with %s', self.ad_phone_number)
    self.ad_ref.tele.telecomAcceptRingingCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_ACTIVE,
        error_msg=(
            f'{self.ad_ref} Failed to accept call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is accepted', self.ad_phone_number)
    self.ad.tele.waitForAudioState(_CallAudioState.get_earpiece_state())
    try:
      telecom_media_utils.play_media_on_android_device(
          self.ad_ref_2, _CALL_AUDIO_FILE_PATH
      )
      self.bt_device.power_on()
      self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
    finally:
      telecom_media_utils.stop_media_on_android_device(self.ad_ref_2)
    # Ends the call from DUT to the specified number.
    self.ad.log.info('Ending call with %s', self.ad_ref_phone_number)
    self.ad.tele.telecomEndCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to end the ongoing call with'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ended', self.ad_ref_phone_number)
  # Bluetooth function is toggled off and on in lea mode.
  def _test_mid_call_audio_route_switch_bluetooth_off_on(self):
    """Test mid call route switch when bluetooth is turned off and on.

    Objective:
      To verify audio can be routed between LEA headset and phone when bluetooth
      is turned off/on during an active call.

    Prediction:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. DUT initiates a call to REF, and REF answers the call.
      2. During the call, REF2 plays audio to simulate voice from far-end.
      3. Turn off Bluetooth on DUT.
      4. Turn on Bluetooth on DUT.
      5. DUT ends the ongoing call.

    Pass Criteria:
      1. The call can be established and call audio is routed to LEA headset.
      2. Call audio is routed to earpiece after Bluetooth is turned off.
      3. Call audio is routed to LEA headset after Bluetooth is turned on.
      4. DUT is STATE_DISCONNECTED after DUT ends the call.
    """
    # Originates a voice call from DUT to REF.
    self.ad.log.info('Originating call to %s', self.ad_ref_phone_number)
    self.ad.tele.telecomPlaceCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to place call to {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is placed', self.ad_ref_phone_number)

    # Waits for the voice call from DUT ringing on REF.
    self.ad.log.info('Waiting for call with %s', self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad_ref} Failed to receive call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call from %s is ringing on REF', self.ad_phone_number)

    # Accepts the voice call from DUT on REF.
    self.ad.log.info('Accepting call with %s', self.ad_phone_number)
    self.ad_ref.tele.telecomAcceptRingingCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_ACTIVE,
        error_msg=(
            f'{self.ad_ref} Failed to accept call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is accepted', self.ad_phone_number)
    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
    try:
      telecom_media_utils.play_media_on_android_device(
          self.ad_ref_2, _CALL_AUDIO_FILE_PATH
      )
      self.ad.bt_snippet.btDisable()
      self.ad.tele.waitForAudioState(_CallAudioState.get_earpiece_state())
      self.ad.bt_snippet.btEnable()
      self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
    finally:
      telecom_media_utils.stop_media_on_android_device(self.ad_ref_2)

    # Ends the voice call with REF on DUT.
    self.ad.log.info('Ending call with %s', self.ad_ref_phone_number)
    self.ad.tele.telecomEndCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to end the ongoing call with'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ended', self.ad_ref_phone_number)

  def test_mid_call_audio_route_switch_lea_headset_to_speaker(self):
    """Test midcall audio route switch from LEA headset to speaker.

    Objective:
      To verify audio can be routed between LEA headset and phone speaker during
      an active call.

    Prediction:
      1. DUT and REF have SIM card.
      2. DUT has paired with a TWS device, under LEA mode.

    Test Steps:
      1. DUT initiates a call to REF, and REF answers the call.
      2. REF2 plays audio to simulate voice from far-end.
      3. DUT switches audio to speaker.
      4. DUT switches audio to BT device.
      5. DUT ends the call.

    Pass Criteria:
      1. The call can be established and call audio is routed through the LEA
         headset, verifed via BES Audio Recorder.
      2. Call audio is routed through the phone speaker after audio route
         switch, verifed via scrcpy.
      3. Call audio is routed through the LEA headset after audio route switch,
         verifed via BES Audio Recorder.
      4. The call state is STATE_DISCONNECTED via the onStateChanged callback
         after call is terminated.
    """
    # Originates a call from DUT to the REF number.
    self.ad.log.info('Originating call to %s', self.ad_ref_phone_number)
    self.ad.tele.telecomPlaceCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to place call to {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is placed', self.ad_ref_phone_number)

    # Wait for a call from DUT to REF number ringing.
    self.ad.log.info('Waiting for call with %s', self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=(
            f'{self.ad_ref} Failed to receive call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call from %s is ringing on REF', self.ad_phone_number)

    # Accepts a call from DUT to REF number.
    self.ad.log.info('Accepting call with %s', self.ad_phone_number)
    self.ad_ref.tele.telecomAcceptRingingCall(self.ad_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad_ref.tele.telecomGetCallState(self.ad_phone_number)
        == telecom_utils.CallState.STATE_ACTIVE,
        error_msg=(
            f'{self.ad_ref} Failed to accept call from {self.ad_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is accepted', self.ad_phone_number)

    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
    try:
      telecom_media_utils.play_media_on_android_device(
          self.ad_ref_2, _CALL_AUDIO_FILE_PATH
      )
      self.ad.log.info('Before switch audio to speaker.')
      self.ad.tele.telecomSetAudioState(_CallAudioState.get_speaker_state())
      time.sleep(_AUDIO_ROUTE_SWITCH_TIMEOUT.total_seconds())
      self.ad.tele.waitForAudioState(_CallAudioState.get_speaker_state())
      self.ad.log.info('After switch audio to speaker.')
      telecom_media_utils.restart_call_audio_on_ref2(
          self.ad_ref_2, _CALL_AUDIO_FILE_PATH
      )
      self.ad.log.info('Before switch audio to bluetooth.')
      self.ad.tele.telecomSetAudioState(_CallAudioState.get_bluetooth_state())
      time.sleep(_AUDIO_ROUTE_SWITCH_TIMEOUT.total_seconds())
      self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
      self.ad.log.info('After switch audio to bluetooth.')
      telecom_media_utils.restart_call_audio_on_ref2(
          self.ad_ref_2, _CALL_AUDIO_FILE_PATH
      )
    finally:
      telecom_media_utils.stop_media_on_android_device(self.ad_ref_2)

    # Ends the call from DUT to the REF number.
    self.ad.log.info('Ending call with %s', self.ad_ref_phone_number)
    self.ad.tele.telecomEndCall(self.ad_ref_phone_number)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetCallState(self.ad_ref_phone_number)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to end the ongoing call with'
            f' {self.ad_ref_phone_number}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ended', self.ad_ref_phone_number)


if __name__ == '__main__':
  test_runner.main()
