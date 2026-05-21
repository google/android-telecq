"""Constants and classes for representing Telecom CallAudioState."""

import enum


@enum.unique
class CallAudioRoute(enum.IntEnum):
  """Encapsulates the telecom audio state.

  https://developer.android.com/reference/android/telecom/CallAudioState
  """
  EARPIECE = 1
  BLUETOOTH = 2
  WIRED_HEADSET = 4
  SPEAKER = 8
  STREAMING = 16


@enum.unique
class CallEndpoint(enum.IntEnum):
  """Encapsulates the telecom endpoint state.

  https://developer.android.com/reference/android/telecom/CallEndpoint
  """
  EARPIECE = 1
  BLUETOOTH = 2
  WIRED_HEADSET = 3
  SPEAKER = 4
  STREAMING = 5


class CallAudioState:
  """Represents audio route and endpoint state for a call."""

  @classmethod
  def get_earpiece_state(cls) -> dict[str, int]:
    return {
        'audioRoute': CallAudioRoute.EARPIECE,
        'endpointType': CallEndpoint.EARPIECE,
    }

  @classmethod
  def get_bluetooth_state(cls) -> dict[str, int]:
    return {
        'audioRoute': CallAudioRoute.BLUETOOTH,
        'endpointType': CallEndpoint.BLUETOOTH,
    }

  @classmethod
  def get_wired_headset_state(cls) -> dict[str, int]:
    return {
        'audioRoute': CallAudioRoute.WIRED_HEADSET,
        'endpointType': CallEndpoint.WIRED_HEADSET,
    }

  @classmethod
  def get_speaker_state(cls) -> dict[str, int]:
    return {
        'audioRoute': CallAudioRoute.SPEAKER,
        'endpointType': CallEndpoint.SPEAKER,
    }

  @classmethod
  def get_streaming_state(cls) -> dict[str, int]:
    return {
        'audioRoute': CallAudioRoute.STREAMING,
        'endpointType': CallEndpoint.STREAMING,
    }
