"""Voice Call Tests with HFP Headset."""

import datetime
import time

from mobly import asserts
from mobly import test_runner

from android_beat import call_audio_state
from android_beat import telecom_base_test
from android_beat.utils import media_utils as telecom_media_utils
from android_beat.utils import telecom_utils

_CallAudioState = call_audio_state.CallAudioState
_BLUETOOTH_ENDPOINT_TYPE = _CallAudioState.get_bluetooth_state()['endpointType']
_SPEAKER_ENDPOINT_TYPE = _CallAudioState.get_speaker_state()['endpointType']
_EARPIECE_ENDPOINT_TYPE = _CallAudioState.get_earpiece_state()['endpointType']
_AUDIO_PLAYBACK_TIME = datetime.timedelta(seconds=10)
_AUDIO_SWITCH_TIME = datetime.timedelta(seconds=3)
_TEST_DIAL_NUMBER = '5551212'


class VoipCallWithHfpHeadsetTest(telecom_base_test.TelecomBaseTest):
  """Voice over IP call test with HFP headset."""

  _DEVICE_NUM = telecom_base_test.TelecomBaseDeviceNum.SINGLE_DEVICE
  _IS_VOIP_TEST = True

  def test_voip_outgoing_call_through_hfp_headset(self):
    """Test outgoing VoIP call through HFP headset.

    Objective:
    To verify an outgoing VoIP call can be successfully established.

    Test Steps:
    1. DUT registers a self-managed account for VoIP call.
    2. DUT initiates an outgoing VoIP call to its own number.
    3. DUT plays audio with USAGE_VOICE_COMMUNICATION.
    4. DUT ends the call.

    Pass Criteria:
    1. The call state becomes STATE_ACTIVE after initiating the call.
    2. The call count for self-managed calls is 1 during the call.
    3. The call audio is routed to HFP headset.
    4. The call is outgoing.
    5. The call state becomes STATE_DISCONNECTED after call is terminated.
    """

    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()
    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Originates a VoIP call to the DUT number.
    self.ad.log.info('Originating VoIP call to %s', _TEST_DIAL_NUMBER)
    call_id = self.ad.tele.addTransactionalCall(_TEST_DIAL_NUMBER)
    self.ad.log.info('Call added successfully, call_id: %s', call_id)
    # Verify the call state is STATE_DIALING.
    self.ad.log.info(
        'Verify the call state is STATE_DIALING, call_id: %s', call_id
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DIALING}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Set the call to active state.
    self.ad.tele.setCallActive(call_id)
    # Verify the call state is STATE_ACTIVE and the call direction is
    # outgoing.
    telecom_utils.verify_voip_call_active(
        self.ad, call_id, telecom_utils.CallAttributes.DIRECTION_OUTGOING
    )
    # Starts the call audio.
    self.ad.log.info(
        'VoIP Call is ACTIVE. Internal Snippet audio is now playing.'
    )
    self.ad.tele.startCallAudio()
    self.ad.log.info(
        'Call audio is now playing for %s seconds.',
        _AUDIO_PLAYBACK_TIME.total_seconds(),
    )
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())

    # Stops the call audio.
    self.ad.tele.stopCallAudio()
    # Ends the VoIP call.
    self.ad.log.info('Ending the VoIP call with %s.', _TEST_DIAL_NUMBER)
    self.ad.tele.hangupTransactionalCall(call_id)

    # Verifies the call state is STATE_DISCONNECTED.
    self.ad.log.info(
        'Verification: Call state is'
        f' {self.ad.tele.getTransactionCallState(call_id)}'
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DISCONNECTED}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('VoIP call to %s is ended', _TEST_DIAL_NUMBER)

  def test_voip_outgoing_call_through_hfp_headset_during_media_playback(self):
    """Test outgoing VoIP call through HFP headset during media playback.

    Objective:
    To verify an outgoing VoIP call can be successfully established during
    media playback and media playback resumes after call ends.

    Test Steps:
    1. DUT starts media playback.
    2. DUT registers a self-managed account for VoIP call.
    3. DUT initiates an outgoing VoIP call to its own number during media
       playback.
    4. DUT plays audio with USAGE_VOICE_COMMUNICATION.
    5. DUT ends the call.

    Pass Criteria:
    1. Local media is played through the HFP headset before the call, verifed by
       a2dp state and BES Audio Recorder.
    2. The call can be established and local media is paused, verified by
       isMusicActive and BES Audio Recorder.
    3. Call audio is routed through the HFP headset, verifed via BES Audio
       Recorder.
    4. The call state is STATE_DISCONNECTED via the onStateChanged callback
       after call is terminated.
    5. Local media is resumed after the call, verifed by a2dp state,
       isMusicActive and BES Audio Recorder.
    """
    # Play media on the DUT.
    telecom_media_utils.play_media_on_android_device(
        self.ad, self.media_file_path
    )
    telecom_media_utils.wait_for_a2dp_state(
        self.ad, self.bt_address_primary, expected_a2dp_state=True
    )
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()
    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Originates a VoIP call to the DUT number.
    self.ad.log.info('Originating VoIP call to %s', _TEST_DIAL_NUMBER)
    call_id = self.ad.tele.addTransactionalCall(_TEST_DIAL_NUMBER)
    self.ad.log.info('Call added successfully, call_id: %s', call_id)
    # Verify the call state is STATE_DIALING.
    self.ad.log.info(
        'Verify the call state is STATE_DIALING, call_id: %s', call_id
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DIALING}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Set the call to active state.
    self.ad.tele.setCallActive(call_id)
    self.ad.log.info('Set the call state to STATE_ACTIVE, call_id: %s', call_id)
    # Verify the call state is STATE_ACTIVE and the call direction is
    # outgoing.
    telecom_utils.verify_voip_call_active(
        self.ad, call_id, telecom_utils.CallAttributes.DIRECTION_OUTGOING
    )
    telecom_media_utils.wait_for_media3_playing_state(
        self.ad, expected_media3_playing_state=False
    )
    telecom_media_utils.wait_for_music_active_state(
        self.ad, expected_music_state=False
    )
    self.ad.tele.waitForAudioState(_CallAudioState.get_bluetooth_state())
    # Starts the call audio.
    self.ad.log.info(
        'VoIP Call is ACTIVE. Internal Snippet audio is now playing.'
    )
    self.ad.tele.startCallAudio()
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Stops the call audio.
    self.ad.tele.stopCallAudio()
    self.ad.log.info(
        'Call duration simulated for %s seconds.',
        _AUDIO_PLAYBACK_TIME.total_seconds(),
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.telecomGetAudioState(
            _CallAudioState.get_bluetooth_state()
        ),
        error_msg=(
            f'{self.ad} Failed to get the audio state to'
            f' {_CallAudioState.get_bluetooth_state()}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Ends the VoIP call.
    self.ad.log.info('Ending the VoIP call with %s.', _TEST_DIAL_NUMBER)
    self.ad.tele.hangupTransactionalCall(call_id)
    # Verifies the call state is STATE_DISCONNECTED.
    self.ad.log.info(
        'Verification: Call state is'
        f' {self.ad.tele.getTransactionCallState(call_id)}'
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DISCONNECTED}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('VoIP call to %s is ended', _TEST_DIAL_NUMBER)
    telecom_media_utils.wait_for_media3_playing_state(
        self.ad, expected_media3_playing_state=True
    )
    telecom_media_utils.wait_for_music_active_state(
        self.ad, expected_music_state=True
    )
    telecom_media_utils.wait_for_a2dp_state(
        self.ad, self.bt_address_primary, expected_a2dp_state=True
    )

  def test_incoming_call_ringtone_through_hfp_headset(self):
    """Test incoming VoIP call lifecycle and disconnection.

    Objective:
      To verify a fake incoming VoIP call can be received and correctly
      disconnected, verifying the STATE_DISCONNECTED callback.

    Test Steps:
      1. DUT registers a self-managed account.
      2. DUT simulates an incoming VoIP call.
      3. DUT ends the call.

    Pass Criteria:
      1. The call count for self-managed calls is 1 during the call.
      2. The call is correctly identified as incoming.
      3. The call audio is routed to HFP headset.
      4. The call state becomes STATE_DISCONNECTED after call is terminated.
    """
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()

    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Initiates a fake incoming call.
    self.ad.log.info(
        'Adding a fake incoming VoIP call to %s', _TEST_DIAL_NUMBER
    )
    call_id = self.ad.tele.addIncomingVoipCall(_TEST_DIAL_NUMBER)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=f'{self.ad} Failed to receive call from {_TEST_DIAL_NUMBER}',
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', _TEST_DIAL_NUMBER)
    # Waits for the call audio state to be bluetooth.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallEndpointType(call_id)
        == _BLUETOOTH_ENDPOINT_TYPE,
        error_msg=(
            f'{self.ad} Failed to get the call endpoint type to'
            f' {_BLUETOOTH_ENDPOINT_TYPE}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Ends the VoIP call.
    self.ad.log.info('Ending the VoIP call with %s.', _TEST_DIAL_NUMBER)
    self.ad.tele.hangupTransactionalCall(call_id)
    # Verifies the call state is STATE_DISCONNECTED.
    self.ad.log.info(
        'Verification: Call state is'
        f' {self.ad.tele.getTransactionCallState(call_id)}'
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DISCONNECTED}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('VoIP call to %s is ended', _TEST_DIAL_NUMBER)

  def test_incoming_call_through_hfp_headset(self):
    """Test incoming VoIP call lifecycle and disconnection.

    Objective:
      To verify a fake incoming VoIP call can be received, answered, and
      correctly disconnected.

    Test Steps:
      1. DUT registers a self-managed account.
      2. DUT simulates an incoming VoIP call.
      3. DUT confirms the call is answered and becomes ACTIVE.
      4. DUT starts the call audio.
      5. DUT stops the call audio.
      6. DUT ends the call.

    Pass Criteria:
      1. The call count for self-managed calls is 1 during the call.
      2. The call is correctly identified as incoming.
      3. Call audio is played through HFP headset.
      3. The call state becomes STATE_ACTIVE after call is answered.
      4. Audio is played through HFP headset.
      5. The call state becomes STATE_DISCONNECTED after call is terminated.
    """
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()

    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Initiates a fake incoming call.
    self.ad.log.info(
        'Adding a fake incoming VoIP call to %s', _TEST_DIAL_NUMBER
    )
    call_id = self.ad.tele.addIncomingVoipCall(_TEST_DIAL_NUMBER)

    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=f'{self.ad} Failed to receive call from {_TEST_DIAL_NUMBER}',
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', _TEST_DIAL_NUMBER)
    # Answers the incoming VoIP call.
    self.ad.log.info(
        'Answering the incoming VoIP call from %s', _TEST_DIAL_NUMBER
    )
    self.ad.tele.answerTransactionalCall(
        call_id, telecom_utils.CallMediaType.AUDIO_CALL
    )
    # Verify the call state is STATE_ACTIVE and the call direction is
    # incoming.
    telecom_utils.verify_voip_call_active(
        self.ad, call_id, telecom_utils.CallAttributes.DIRECTION_INCOMING
    )
    # Starts the call audio.
    self.ad.log.info(
        'VoIP Call is ACTIVE. Internal Snippet audio is now playing.'
    )
    self.ad.tele.startCallAudio()
    self.ad.log.info(
        'Call audio is now playing for %s seconds.',
        _AUDIO_PLAYBACK_TIME.total_seconds(),
    )
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Stops the call audio.
    self.ad.tele.stopCallAudio()
    # Ends the VoIP call.
    self.ad.log.info('Ending the VoIP call with %s.', _TEST_DIAL_NUMBER)
    self.ad.tele.hangupTransactionalCall(call_id)

    # Verifies the call state is STATE_DISCONNECTED.
    self.ad.log.info(
        'Verification: Call state is'
        f' {self.ad.tele.getTransactionCallState(call_id)}'
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DISCONNECTED}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('VoIP call to %s is ended', _TEST_DIAL_NUMBER)

  def test_incoming_call_through_hfp_headset_during_media_playback(self):
    """Test incoming VoIP call through HFP headset during media playback.

    Objective:
      To verify an incoming VoIP call can be successfully established during
      media playback and media playback resumes after call ends.

    Test Steps:
      1. DUT starts media playback.
      2. DUT registers a self-managed account for VoIP call.
      3. DUT simulates an incoming VoIP call.
      4. DUT answers the incoming call.
      5. DUT ends the call.

    Pass Criteria:
      1. Local media is played through the HFP headset before the call,
         verifed by A2DP state.
      2. The call can be established and local media is paused, verified by
         isMusicActive.
      3. Call audio is routed through the HFP headset.
      4. The call state is STATE_DISCONNECTED via the onStateChanged callback
         after call is terminated.
      5. Local media is resumed after the call, verifed by A2DP state,
         isMusicActive.
    """
    # Play media on the DUT.
    telecom_media_utils.play_media_on_android_device(
        self.ad, self.media_file_path
    )
    telecom_media_utils.wait_for_a2dp_state(
        self.ad, self.bt_address_primary, expected_a2dp_state=True
    )
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()
    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Initiates a fake incoming call.
    self.ad.log.info(
        'Adding a fake incoming VoIP call from %s', _TEST_DIAL_NUMBER
    )
    call_id = self.ad.tele.addIncomingVoipCall(_TEST_DIAL_NUMBER)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=f'{self.ad} Failed to receive call from {_TEST_DIAL_NUMBER}',
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', _TEST_DIAL_NUMBER)
    # Answers the incoming VoIP call.
    self.ad.log.info(
        'Answering the incoming VoIP call from %s', _TEST_DIAL_NUMBER
    )
    self.ad.tele.answerTransactionalCall(
        call_id, telecom_utils.CallMediaType.AUDIO_CALL
    )
    # Verify the call state is STATE_ACTIVE and the call direction is
    # incoming.
    telecom_utils.verify_voip_call_active(
        self.ad, call_id, telecom_utils.CallAttributes.DIRECTION_INCOMING
    )
    # Verifies the media playback state is paused.
    telecom_media_utils.wait_for_media3_playing_state(
        self.ad, expected_media3_playing_state=False
    )
    telecom_media_utils.wait_for_music_active_state(
        self.ad, expected_music_state=False
    )
    # Ends the VoIP call.
    self.ad.log.info('Ending the VoIP call with %s.', _TEST_DIAL_NUMBER)
    self.ad.tele.hangupTransactionalCall(call_id)
    # Verifies the call state is STATE_DISCONNECTED.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DISCONNECTED}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('VoIP call to %s is ended', _TEST_DIAL_NUMBER)
    # Verifies the media playback state is active.
    telecom_media_utils.wait_for_media3_playing_state(
        self.ad, expected_media3_playing_state=True
    )
    telecom_media_utils.wait_for_music_active_state(
        self.ad, expected_music_state=True
    )
    telecom_media_utils.wait_for_a2dp_state(
        self.ad, self.bt_address_primary, expected_a2dp_state=True
    )

  def test_mid_call_audio_route_switch_hfp_headset_to_speaker(self):
    """Test mid call audio route switch from HFP headset to speaker.

    Objective:
      To verify that the audio route can be switched between the HFP headset
      and the device speaker during an active VoIP call.

    Test Steps:
      1. DUT registers a self-managed account for VoIP call.
      2. DUT initiates an outgoing VoIP call.
      3. DUT verifies the call is active and audio is routed to the HFP headset.
      4. DUT switches the audio route to the device speaker.
      5. DUT switches the audio route back to the HFP headset.
      6. DUT ends the call.

    Pass Criteria:
      1. The call becomes active and audio is initially routed to the HFP
         headset.
      2. The audio route successfully switches to the device speaker.
      3. The audio route successfully switches back to the HFP headset.
      4. The call state becomes STATE_DISCONNECTED after the call is terminated.
    """
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()
    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Originates a VoIP call to the DUT number.
    self.ad.log.info('Originating VoIP call to %s', _TEST_DIAL_NUMBER)
    call_id = self.ad.tele.addTransactionalCall(_TEST_DIAL_NUMBER)
    self.ad.log.info('Call added successfully, call_id: %s', call_id)
    # Verify the call state is STATE_DIALING.
    self.ad.log.info(
        'Verify the call state is STATE_DIALING, call_id: %s', call_id
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DIALING}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Set the call to active state.
    self.ad.tele.setCallActive(call_id)
    self.ad.log.info('Set the call state to STATE_ACTIVE, call_id: %s', call_id)
    # Verify the call state is STATE_ACTIVE and the call direction is
    # outgoing.
    telecom_utils.verify_voip_call_active(
        self.ad, call_id, telecom_utils.CallAttributes.DIRECTION_OUTGOING
    )
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Starts the call audio.
    self.ad.log.info(
        'VoIP Call is ACTIVE. Internal Snippet audio is now playing.'
    )
    self.ad.tele.startCallAudio()
    self.ad.log.info('Switching audio to SPEAKER')
    self.ad.tele.switchAudioToEndpointType(call_id, _SPEAKER_ENDPOINT_TYPE)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallEndpointType(call_id)
        == _SPEAKER_ENDPOINT_TYPE,
        error_msg=(
            f'{self.ad} Failed to get the call endpoint type to'
            f' {_SPEAKER_ENDPOINT_TYPE}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Switches audio to BLUETOOTH.
    self.ad.log.info('Switching audio to BLUETOOTH')
    self.ad.tele.switchAudioToEndpointType(call_id, _BLUETOOTH_ENDPOINT_TYPE)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallEndpointType(call_id)
        == _BLUETOOTH_ENDPOINT_TYPE,
        error_msg=(
            f'{self.ad} Failed to get the call endpoint type to'
            f' {_BLUETOOTH_ENDPOINT_TYPE}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Stops the call audio.
    self.ad.tele.stopCallAudio()
    # Ends the VoIP call.
    self.ad.log.info('Ending the VoIP call with %s.', _TEST_DIAL_NUMBER)
    self.ad.tele.hangupTransactionalCall(call_id)
    # Verifies the call state is STATE_DISCONNECTED.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DISCONNECTED}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('VoIP call to %s is ended', _TEST_DIAL_NUMBER)

  def test_mid_call_audio_route_switch_hfp_headset_power_off_on(self):
    """Test mid call audio route switch from HFP headset to speaker.

    Objective:
      To verify that the audio route can be switched from the HFP headset to
      the device earpiece during an active VoIP call when the HFP headset is
      powered off and back to the HFP headset when it is powered back on.

    Test Steps:
      1. DUT registers a self-managed account for VoIP call.
      2. DUT initiates an outgoing VoIP call.
      3. DUT verifies the call is active and audio is routed to the HFP headset.
      4. Power off the HFP headset.
      5. DUT verifies the audio route successfully switches to the earpiece.
      6. Power on the HFP headset.
      7. DUT verifies the audio route successfully switches back to the HFP
         headset.
      8. DUT ends the call.

    Pass Criteria:
      1. The call becomes active and audio is initially routed to the HFP
         headset.
      2. The audio route successfully switches to the earpiece after the HFP
         headset is powered off.
      3. The audio route successfully switches back to the HFP headset after
         the HFP headset is powered on.
      4. The call state becomes STATE_DISCONNECTED after the call is terminated.
    """
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()
    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Originates a VoIP call to the DUT number.
    self.ad.log.info('Originating VoIP call to %s', _TEST_DIAL_NUMBER)
    call_id = self.ad.tele.addTransactionalCall(_TEST_DIAL_NUMBER)
    self.ad.log.info('Call added successfully, call_id: %s', call_id)
    # Verify the call state is STATE_DIALING.
    self.ad.log.info(
        'Verify the call state is STATE_DIALING, call_id: %s', call_id
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DIALING}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Set the call to active state.
    self.ad.tele.setCallActive(call_id)
    self.ad.log.info('Set the call state to STATE_ACTIVE, call_id: %s', call_id)
    # Verify the call state is STATE_ACTIVE and the call direction is
    # outgoing.
    telecom_utils.verify_voip_call_active(
        self.ad, call_id, telecom_utils.CallAttributes.DIRECTION_OUTGOING
    )
    # Starts the call audio.
    self.ad.log.info(
        'VoIP Call is ACTIVE. Internal Snippet audio is now playing.'
    )
    self.ad.tele.startCallAudio()
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Power off the HFP headset.
    self.bt_device.power_off()
    # Verify the call audio state is earpiece.
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallEndpointType(call_id)
        == _EARPIECE_ENDPOINT_TYPE,
        error_msg=(
            f'{self.ad} Failed to get the call endpoint type to'
            f' {_EARPIECE_ENDPOINT_TYPE}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Power on the HFP headset.
    self.bt_device.power_on()
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Verify the call audio state is bluetooth.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallEndpointType(call_id)
        == _BLUETOOTH_ENDPOINT_TYPE,
        error_msg=(
            f'{self.ad} Failed to get the call endpoint type to'
            f' {_BLUETOOTH_ENDPOINT_TYPE}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Stops the call audio.
    self.ad.tele.stopCallAudio()
    # Ends the VoIP call.
    self.ad.log.info('Ending the VoIP call with %s.', _TEST_DIAL_NUMBER)
    self.ad.tele.hangupTransactionalCall(call_id)
    # Verifies the call state is STATE_DISCONNECTED.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DISCONNECTED}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('VoIP call to %s is ended', _TEST_DIAL_NUMBER)

  def test_mid_call_audio_route_switch_hfp_headset_power_on(self):
    """Test mid call audio route switch from speaker to HFP headset.

    Objective:
      To verify that the audio route can be switched from the device speaker to
      the HFP headset during an active VoIP call when the HFP headset is
      powered on.

    Test Steps:
      1. Power off the HFP headset.
      2. DUT registers a self-managed account for VoIP call.
      3. DUT initiates an outgoing VoIP call.
      4. DUT verifies the call is active and audio is routed to the earpiece.
      5. Powers on the HFP headset.
      6. DUT verifies the audio route successfully switches to the HFP headset.
      7. DUT ends the call.

    Pass Criteria:
      1. The call becomes active and audio is initially routed to the earpiece.
      2. The audio route successfully switches to the HFP headset after the
         HFP headset is powered on.
      3. The call state becomes STATE_DISCONNECTED after the call is terminated.
    """
    # Power off the HFP headset.
    self.bt_device.power_off()
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()
    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Originates a VoIP call to the DUT number.
    self.ad.log.info('Originating VoIP call to %s', _TEST_DIAL_NUMBER)
    call_id = self.ad.tele.addTransactionalCall(_TEST_DIAL_NUMBER)
    self.ad.log.info('Call added successfully, call_id: %s', call_id)
    # Verify the call state is STATE_DIALING.
    self.ad.log.info(
        'Verify the call state is STATE_DIALING, call_id: %s', call_id
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DIALING}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Set the call to active state.
    self.ad.tele.setCallActive(call_id)
    self.ad.log.info('Set the call state to STATE_ACTIVE, call_id: %s', call_id)
    # Verify the call state is STATE_ACTIVE and the call direction is
    # outgoing.
    telecom_utils.verify_voip_call_active(
        self.ad,
        call_id,
        telecom_utils.CallAttributes.DIRECTION_OUTGOING,
        endpoint_type=_EARPIECE_ENDPOINT_TYPE,
    )
    # Starts the call audio.
    self.ad.log.info(
        'VoIP Call is ACTIVE. Internal Snippet audio is now playing from'
        ' earpiece.'
    )
    self.ad.tele.startCallAudio()
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Power on the HFP headset.
    self.bt_device.power_on()
    # Verify the call audio state is bluetooth.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallEndpointType(call_id)
        == _BLUETOOTH_ENDPOINT_TYPE,
        error_msg=(
            f'{self.ad} Failed to get the call endpoint type to'
            f' {_BLUETOOTH_ENDPOINT_TYPE}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Stops the call audio.
    self.ad.tele.stopCallAudio()
    # Ends the VoIP call.
    self.ad.log.info('Ending the VoIP call with %s.', _TEST_DIAL_NUMBER)
    self.ad.tele.hangupTransactionalCall(call_id)
    # Verifies the call state is STATE_DISCONNECTED.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DISCONNECTED}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('VoIP call to %s is ended', _TEST_DIAL_NUMBER)

  def test_reject_incoming_call_through_hfp_headset(self):
    """Test reject incoming VoIP call through HFP headset.

    Objective:
      To verify an incoming VoIP call can be successfully rejected through the
      HFP headset.

    Test Steps:
      1. DUT registers a self-managed account.
      2. DUT simulates an incoming VoIP call.
      3. BT device rejects the call.

    Pass Criteria:
      1. The call count for self-managed calls is 1 during ringing.
      2. The call is correctly identified as incoming and ringing.
      3. The call audio is routed to HFP headset during ringing.
      4. The call state becomes STATE_DISCONNECTED after BT device rejects
         the call.
    """
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()

    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Initiates a fake incoming call.
    self.ad.log.info(
        'Adding a fake incoming VoIP call to %s', _TEST_DIAL_NUMBER
    )
    call_id = self.ad.tele.addIncomingVoipCall(_TEST_DIAL_NUMBER)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=f'{self.ad} Failed to receive call from {_TEST_DIAL_NUMBER}',
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', _TEST_DIAL_NUMBER)
    # Waits for the call audio state to be bluetooth.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallEndpointType(call_id)
        == _CallAudioState.get_bluetooth_state()['endpointType'],
        error_msg=(
            f'{self.ad} Failed to get the call endpoint type to'
            f' {_CallAudioState.get_bluetooth_state()["endpointType"]}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )

    # Declines the call from bluetooth device and verifies the call state.
    self.ad.log.info('Rejecting call from bluetooth device...')
    self.bt_device.call_decline()
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Bluetooth device failed to decline call from'
            f' {_TEST_DIAL_NUMBER}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info(
        'Call from %s is declined from bluetooth device', _TEST_DIAL_NUMBER
    )

  def test_mid_call_audio_route_switch_bluetooth_off_on(self):
    """Test mid call audio route switch when Bluetooth is turned off and on.

    Objective:
      To verify that the audio route can be switched from the HFP headset to
      the device earpiece during an active VoIP call when bluetooth is turned
      off and back to the HFP headset when it is turned back on.

    Test Steps:
      1. DUT registers a self-managed account for VoIP call.
      2. DUT initiates an outgoing VoIP call.
      3. DUT verifies the call is active and audio is routed to the HFP headset.
      4. Turn off bluetooth on DUT.
      5. DUT verifies the audio route successfully switches to the earpiece.
      6. Turn on bluetooth on DUT.
      7. DUT verifies the audio route successfully switches back to the HFP
         headset.
      8. DUT ends the call.

    Pass Criteria:
      1. The call becomes active and audio is initially routed to the HFP
         headset.
      2. The audio route successfully switches to the earpiece after Bluetooth
         is turned off.
      3. The audio route successfully switches back to the HFP headset after
         Bluetooth is turned on.
      4. The call state becomes STATE_DISCONNECTED after the call is terminated.
    """
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()
    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Originates a VoIP call to the DUT number.
    self.ad.log.info('Originating VoIP call to %s', _TEST_DIAL_NUMBER)
    call_id = self.ad.tele.addTransactionalCall(_TEST_DIAL_NUMBER)
    self.ad.log.info('Call added successfully, call_id: %s', call_id)
    # Verify the call state is STATE_DIALING.
    self.ad.log.info(
        'Verify the call state is STATE_DIALING, call_id: %s', call_id
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DIALING}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Set the call to active state.
    self.ad.tele.setCallActive(call_id)
    self.ad.log.info('Set the call state to STATE_ACTIVE, call_id: %s', call_id)
    # Verify the call state is STATE_ACTIVE and the call direction is
    # outgoing.
    telecom_utils.verify_voip_call_active(
        self.ad, call_id, telecom_utils.CallAttributes.DIRECTION_OUTGOING
    )
    # Starts the call audio.
    self.ad.log.info(
        'VoIP Call is ACTIVE. Internal Snippet audio is now playing.'
    )
    self.ad.tele.startCallAudio()
    # Turn off the Bluetooth.
    self.ad.bt_snippet.btDisable()
    # Verify the call audio state is earpiece.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallEndpointType(call_id)
        == _EARPIECE_ENDPOINT_TYPE,
        error_msg=(
            f'{self.ad} Failed to get the call endpoint type to'
            f' {_EARPIECE_ENDPOINT_TYPE}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Turn on the Bluetooth.
    self.ad.bt_snippet.btEnable()
    # Verify the call audio state is bluetooth.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallEndpointType(call_id)
        == _BLUETOOTH_ENDPOINT_TYPE,
        error_msg=(
            f'{self.ad} Failed to get the call endpoint type to'
            f' {_BLUETOOTH_ENDPOINT_TYPE}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    # Stops the call audio.
    self.ad.tele.stopCallAudio()
    # Ends the VoIP call.
    self.ad.log.info('Ending the VoIP call with %s.', _TEST_DIAL_NUMBER)
    self.ad.tele.hangupTransactionalCall(call_id)
    # Verifies the call state is STATE_DISCONNECTED.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DISCONNECTED}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('VoIP call to %s is ended', _TEST_DIAL_NUMBER)

  def test_end_ongoing_outgoing_call_through_hfp_headset(self):
    """Test end ongoing outgoing call through HFP headset.

    Objective:
      To verify an ongoing outgoing call can be successfully ended through the
      HFP headset.

    Test Steps:
      1. DUT registers a self-managed account for VoIP call.
      2. DUT initiates an outgoing VoIP call to test number and activates it.
      3. BT device ends the ongoing call.

    Pass Criteria:
      1. DUT is STATE_ACTIVE after call initiated and activated.
      2. The call audio is routed to HFP headset during active call.
      3. DUT is STATE_DISCONNECTED after BT device ends the call.
    """

    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()
    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Initiates a fake outgoing call.
    self.ad.log.info(
        'Adding a fake outgoing VoIP call to %s', _TEST_DIAL_NUMBER
    )
    call_id = self.ad.tele.addTransactionalCall(_TEST_DIAL_NUMBER)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=f'{self.ad} Failed to receive call from {_TEST_DIAL_NUMBER}',
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', _TEST_DIAL_NUMBER)
    # Set the call to active state.
    self.ad.tele.setCallActive(call_id)
    self.ad.log.info('Set the call state to STATE_ACTIVE, call_id: %s', call_id)
    # Verify the call state is STATE_ACTIVE and the call direction is
    # outgoing.
    telecom_utils.verify_voip_call_active(
        self.ad, call_id, telecom_utils.CallAttributes.DIRECTION_OUTGOING
    )
    # Starts the call audio.
    self.ad.tele.startCallAudio()
    self.ad.log.info(
        'Call audio is now playing for %s seconds.',
        _AUDIO_PLAYBACK_TIME.total_seconds(),
    )
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Stops the call audio.
    self.ad.tele.stopCallAudio()
    # Declines the call from bluetooth device and verifies the call state.
    self.ad.log.info('Rejecting call from bluetooth device...')
    self.bt_device.call_decline()
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Bluetooth device failed to decline call to'
            f' {_TEST_DIAL_NUMBER}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info(
        'Call to %s is declined from bluetooth device', _TEST_DIAL_NUMBER
    )

  def test_end_ongoing_incoming_call_through_hfp_headset(self):
    """Test end ongoing incoming call through HFP headset.

    Objective:
      To verify an ongoing incoming call can be successfully ended through the
      HFP headset.

    Test Steps:
      1. DUT registers a self-managed account.
      2. DUT simulates an incoming VoIP call and answers it.
      3. BT device ends the ongoing call.

    Pass Criteria:
      1. The call is correctly identified as incoming and becomes STATE_ACTIVE.
      2. The call audio is routed to HFP headset during active call.
      3. The call state becomes STATE_DISCONNECTED after BT device ends
         the call.
    """
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()

    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Initiates a fake incoming call.
    self.ad.log.info(
        'Adding a fake incoming VoIP call to %s', _TEST_DIAL_NUMBER
    )
    call_id = self.ad.tele.addIncomingVoipCall(_TEST_DIAL_NUMBER)

    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_RINGING,
        error_msg=f'{self.ad} Failed to receive call from {_TEST_DIAL_NUMBER}',
        timeout=telecom_utils.WAIT_CALL_RINGING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is ringing', _TEST_DIAL_NUMBER)
    # Answers the incoming VoIP call.
    self.ad.log.info(
        'Answering the incoming VoIP call from %s', _TEST_DIAL_NUMBER
    )
    self.ad.tele.answerTransactionalCall(
        call_id, telecom_utils.CallMediaType.AUDIO_CALL
    )
    # Verify the call state is STATE_ACTIVE and the call direction is
    # incoming.
    telecom_utils.verify_voip_call_active(
        self.ad, call_id, telecom_utils.CallAttributes.DIRECTION_INCOMING
    )
    self.ad.log.info(
        'VoIP Call is ACTIVE. Internal Snippet audio is now playing.'
    )
    # Starts the call audio.
    self.ad.tele.startCallAudio()
    self.ad.log.info(
        'Call audio is now playing for %s seconds.',
        _AUDIO_PLAYBACK_TIME.total_seconds(),
    )
    time.sleep(_AUDIO_SWITCH_TIME.total_seconds())
    # Stops the call audio.
    self.ad.tele.stopCallAudio()
    # Ends the VoIP call.
    self.ad.log.info(
        'Ending the VoIP call with %s via bluetooth device.', _TEST_DIAL_NUMBER
    )
    self.bt_device.call_decline()
    # Verifies the call state is STATE_DISCONNECTED.
    self.ad.log.info(
        'Verification: Call state is'
        f' {self.ad.tele.getTransactionCallState(call_id)}'
    )
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Failed to get the call state to'
            f' {telecom_utils.CallState.STATE_DISCONNECTED}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )
    self.ad.log.info('VoIP call to %s is ended', _TEST_DIAL_NUMBER)
  # calls while in the 'DIALING' state. Therefore we set it as a private
  # function for now, and will enable it once the call can be ended under
  # 'DIALING' state.
  def _test_end_outgoing_call_through_hfp_headset(self):
    """Test end outgoing VoIP call through HFP headset.

    Objective:
      To verify an outgoing VoIP call can be successfully ended through the
      HFP headset.

    Test Steps:
      1. DUT registers a self-managed account.
      2. DUT simulates an outgoing VoIP call.
      3. BT device ends the call.

    Pass Criteria:
      1. The call is correctly identified as outgoing and becomes STATE_DIALING.
      2. The call audio is routed to HFP headset during ringing.
      3. The call state becomes STATE_DISCONNECTED after BT device ends
         the call.
    """
    # Registers a self-managed account for VoIP call.
    self.ad.tele.registerTransactionalPhoneAccount()

    asserts.assert_true(
        self.ad.tele.isTransactionalTestAccountEnabled(),
        f'{self.ad} Transactional test account is not enabled.',
    )
    # Initiates a fake outgoing call.
    self.ad.log.info(
        'Adding a fake outgoing VoIP call to %s', _TEST_DIAL_NUMBER
    )
    call_id = self.ad.tele.addTransactionalCall(_TEST_DIAL_NUMBER)
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DIALING,
        error_msg=f'{self.ad} Failed to place call to {_TEST_DIAL_NUMBER}',
        timeout=telecom_utils.WAIT_CALL_DAILING_TIMEOUT,
    )
    self.ad.log.info('Call with %s is dailing', _TEST_DIAL_NUMBER)
    # Waits for the call audio state to be bluetooth.
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallEndpointType(call_id)
        == _CallAudioState.get_bluetooth_state()['endpointType'],
        error_msg=(
            f'{self.ad} Failed to get the call endpoint type to'
            f' {_CallAudioState.get_bluetooth_state()["endpointType"]}'
        ),
        timeout=telecom_utils.WAIT_CALL_CONNECTED_TIMEOUT,
    )

    # Declines the call from bluetooth device and verifies the call state.
    self.ad.log.info('Ending call from bluetooth device...')
    self.bt_device.call_decline()
    telecom_utils.wait_until_or_assert(
        lambda: self.ad.tele.getTransactionCallState(call_id)
        == telecom_utils.CallState.STATE_DISCONNECTED,
        error_msg=(
            f'{self.ad} Bluetooth device failed to decline call from'
            f' {_TEST_DIAL_NUMBER}'
        ),
        timeout=telecom_utils.WAIT_CALL_DISCONNECTED_TIMEOUT,
    )
    self.ad.log.info(
        'Call from %s is declined from bluetooth device', _TEST_DIAL_NUMBER
    )


if __name__ == '__main__':
  test_runner.main()
