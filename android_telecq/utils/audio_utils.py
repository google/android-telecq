"""Audio utils for telecom tests."""

import dataclasses
import datetime
import enum
import logging
import pathlib
import time
from typing import Any
import wave

import librosa
from mobly import asserts
from mobly.controllers import android_device
import numpy as np
from scipy import signal

from android_telecq.bluetooth.platforms.bluetooth import bes_device
from android_telecq.bluetooth.platforms.bluetooth import tws_device


_AudioChannelMode = bes_device.AudioChannelMode
_AUDIO_PLAYBACK_DURATION_TIMEOUT = datetime.timedelta(seconds=10)
_AUDIO_RECORDING_FINISH_TIMEOUT = datetime.timedelta(seconds=10)
_AUDIO_RECORDER_REBOOT_TIMEOUT = datetime.timedelta(seconds=2)

_ENERGY_THRESHOLD = 0.005
_MAX_AMPLITUDE_THRESHOLD = 0.02
_CV_THRESHOLD = 0.15
_STABILITY_AMP_CEILING = 0.3
_MEAN_RMS_THRESHOLD = 0.03
_STRICT_SILENCE_THRESHOLD_AMP = 0.001
_STRICT_SILENCE_THRESHOLD_RMS = 0.0005
_RESCUE_MAX_RMS = 0.04
_ZCR_THRESHOLD_VOIP = 0.016
_ZCR_THRESHOLD_TRADITIONAL = 0.04
_RESCUE_FREQ_FLOOR = 100
_LOUD_VOLUME_THRESHOLD = 0.15
_RESCUE_POP_CREST_FACTOR = 7.0
_RESCUE_BURST_RMS_THRESHOLD = 0.1
_RESCUE_HIGH_FREQ_THRESHOLD = 1_000
_N_FFT = 2_048
_CUTOFF_FREQ = 150
_DEFAULT_SAMPLING_RATE = 16_000
_BT_AUDIO_RECORDING_SAMPLE_RATE = 48_000


@enum.unique
class CallType(enum.Enum):
  """Call type for telecom tests."""

  TRADITIONAL = enum.auto()
  VOIP = enum.auto()


@enum.unique
class AudioRoute(enum.Enum):
  """Audio route types for telecom tests."""

  ROUTE_TO_SPEAKER = enum.auto()
  ROUTE_TO_BLUETOOTH = enum.auto()
  ROUTE_FOR_RING_TONE = enum.auto()
  NO_AUDIO_TO_BOTH_SPEAKER_AND_BLUETOOTH = enum.auto()


@dataclasses.dataclass
class AudioMetrics:
  """Holds calculated audio metrics to avoid passing multiple arguments."""

  max_amp: float
  mean_rms: float
  max_rms: float
  peak_freq: float
  rms_series: np.ndarray
  filtered_data: np.ndarray
  duration: float


def get_peak_frequency(audio_data: np.ndarray, sr: int) -> float:
  """Returns the peak frequency of the given audio data.

  Args:
    audio_data: The audio time series, this is often called `y` in audio
      processing libraries like Librosa.
    sr: The sampling rate of audio_data.

  Returns:
    The peak frequency of audio_data.
  """

  fft_res = np.fft.rfft(audio_data, n=_N_FFT)
  power_spectrum = np.abs(fft_res) ** 2
  idx = power_spectrum.argmax()
  freqs = np.fft.rfftfreq(_N_FFT, d=1.0 / sr)
  return freqs[idx]


def _load_and_filter_audio(
    file_path: str | pathlib.Path,
    offset_sec: float = 0.0,
) -> tuple[np.ndarray | None, int]:
  """Loads audio file and applies high-pass filter.

  Args:
    file_path: The path to the audio file.
    offset_sec: The offset in seconds to start loading audio from.

  Returns:
    A tuple containing the filtered audio data and the sampling rate, or
    (None, 0) on failure.
  """
  try:
    audio_data, sr = librosa.load(file_path, sr=None, offset=offset_sec)
    duration_sec = librosa.get_duration(y=audio_data, sr=sr)

    if duration_sec == 0:
      logging.info('Audio file %r is empty (duration 0).', file_path)
      return None, 0

    logging.info(
        'Audio file %r has duration %f seconds.', file_path, duration_sec
    )

    if audio_data.size == 0:
      logging.info('Audio file %r is empty.', file_path)
      return None, 0

    filter_num, filter_denom = signal.butter(
        4, _CUTOFF_FREQ, btype='high', fs=sr
    )
    filtered_audio_data = signal.lfilter(filter_num, filter_denom, audio_data)

    return filtered_audio_data, sr

  except FileNotFoundError:
    logging.exception('Failed to load audio file %r', file_path)
    return None, 0


def _compute_metrics(
    filtered_audio_data: np.ndarray, sr: int, file_path: str
) -> AudioMetrics:
  """Calculates necessary audio metrics from filtered data.

  Args:
    filtered_audio_data: The filtered audio data.
    sr: The sampling rate of the audio data.
    file_path: The path to the audio file, used for logging.

  Returns:
    An AudioMetrics object containing the calculated metrics.
  """
  max_amp = np.abs(filtered_audio_data).max()
  rms = librosa.feature.rms(y=filtered_audio_data)[0]
  mean_rms = rms.mean()
  max_rms = rms.max()
  peak_freq = get_peak_frequency(filtered_audio_data, sr)
  duration = librosa.get_duration(y=filtered_audio_data, sr=sr)

  logging.info(
      'Audio Analysis %r: MaxAmp=%.4f, MeanRMS=%.4f, MaxRMS=%.4f, Freq=%.1fHz',
      file_path,
      max_amp,
      mean_rms,
      max_rms,
      peak_freq,
  )

  return AudioMetrics(
      max_amp=max_amp,
      mean_rms=mean_rms,
      max_rms=max_rms,
      peak_freq=peak_freq,
      rms_series=rms,
      filtered_data=filtered_audio_data,
      duration=duration,
  )


def _should_rescue_low_volume_signal(metrics: AudioMetrics) -> bool:
  """Determines if a low-volume signal should be rescued (considered NOT silent).

  Args:
    metrics: The audio metrics of the signal.

  Returns:
    True if the signal should be rescued, False otherwise.
  """
  if (
      metrics.max_rms <= _RESCUE_MAX_RMS
      or metrics.peak_freq <= _RESCUE_FREQ_FLOOR
  ):
    return False

  is_rescued = (
      metrics.peak_freq > _RESCUE_HIGH_FREQ_THRESHOLD
      or metrics.max_amp < _RESCUE_BURST_RMS_THRESHOLD
      or (metrics.max_amp / metrics.max_rms) < _RESCUE_POP_CREST_FACTOR
  )

  if is_rescued:
    logging.info(
        'Audio NOT silent (Rescued). MaxRMS: %.4f, Freq: %.1fHz',
        metrics.max_rms,
        metrics.peak_freq,
    )
    return True

  return False


def _is_stable_noise(metrics: AudioMetrics) -> bool:
  """Checks if the audio is just stable background noise.

  Args:
    metrics: The audio metrics of the signal.

  Returns:
    True if the audio is stable noise, False otherwise.
  """
  if metrics.mean_rms <= 0:
    return False

  rms_cv = metrics.rms_series.std() / metrics.mean_rms
  if rms_cv < _CV_THRESHOLD and metrics.max_amp < _STABILITY_AMP_CEILING:
    logging.info('Audio silent (Stable Noise). CV: %.4f', rms_cv)
    return True

  return False


def _is_silence_by_zcr(
    metrics: AudioMetrics, call_type: CallType, file_path: str
) -> bool:
  """Final check using Zero Crossing Rate on high energy frames.

  Args:
    metrics: The audio metrics of the signal.
    call_type: The type of call (VOIP or TRADITIONAL).
    file_path: The path to the audio file, used for logging.

  Returns:
    True if the audio is silent, False otherwise.
  """
  high_energy_frames = metrics.rms_series > _ENERGY_THRESHOLD

  if not high_energy_frames.any():
    logging.info('No high energy frames in %r.', file_path)
    return True

  zcr = librosa.feature.zero_crossing_rate(y=metrics.filtered_data)[0]

  if call_type == CallType.VOIP:
    zcr_threshold = _ZCR_THRESHOLD_VOIP
  else:
    zcr_threshold = _ZCR_THRESHOLD_TRADITIONAL

  avg_zcr = zcr[high_energy_frames].mean()
  is_silent = avg_zcr <= zcr_threshold

  logging.info(
      'Audio file %r analysis (Final ZCR check): avg_zcr=%f, is_silent=%s',
      file_path,
      avg_zcr,
      is_silent,
  )
  return is_silent


def is_audio_file_empty_or_silent(
    file_path: str | pathlib.Path,
    call_type: CallType,
    offset_sec: float = 0.0,
) -> bool:
  """Checks if an audio file is empty or completely silent.

  Args:
    file_path: The path to the audio file.
    call_type: The type of call (VOIP or TRADITIONAL).
    offset_sec: The offset in seconds to start loading audio from.

  Returns:
    True if the audio file is empty or silent, False otherwise.
  """

  filtered_data, sr = _load_and_filter_audio(file_path, offset_sec=offset_sec)
  if filtered_data is None:
    return True

  metrics = _compute_metrics(filtered_data, sr, str(file_path))

  if metrics.mean_rms < _MEAN_RMS_THRESHOLD:
    if _should_rescue_low_volume_signal(metrics):
      return False
    logging.info('Audio is silent (Low Volume / Pop Noise rejected).')
    return True

  if metrics.max_amp < _MAX_AMPLITUDE_THRESHOLD:
    logging.info('Audio file %r is silent (Low Peak Amp).', file_path)
    return True

  if (
      metrics.mean_rms > _STRICT_SILENCE_THRESHOLD_RMS
      or metrics.max_amp > _STRICT_SILENCE_THRESHOLD_AMP
  ):
    logging.info(
        'Audio is NOT silent (Signal Detected). MaxAmp: %.4f, MeanRMS: %.4f',
        metrics.max_amp,
        metrics.mean_rms,
    )
    return False

  if metrics.mean_rms > _LOUD_VOLUME_THRESHOLD:
    logging.info(
        'Audio is NOT silent (Loud Volume). MeanRMS: %.4f', metrics.mean_rms
    )
    return False

  if _is_stable_noise(metrics):
    logging.info('Audio file %r is silent (Stable Noise).', file_path)
    return True

  return _is_silence_by_zcr(metrics, call_type, str(file_path))


def fix_bes_audio_sampling_rate(
    file_path: str | pathlib.Path,
    target_sample_rate: int = _DEFAULT_SAMPLING_RATE,
) -> None:
  """Fixes the sampling rate in the header of a WAV file.

  This function modifies the WAV file header to correct the sample rate,
  number of channels, and byte rate based on the `target_sample_rate`.
  This is useful for BES recordings where the hardware might enforce a
  different sample rate than expected.

  Args:
    file_path: The path to the WAV audio file.
    target_sample_rate: The desired sample rate to write into the header.
      Defaults to 16000 Hz.
  """
  logging.info(
      'Fixing BES audio sampling rate (Header Patch) for: %r', file_path
  )
  with wave.open(str(file_path), 'rb') as src:
    params = src.getparams()
    audio_data = src.readframes(params.nframes)
  with wave.open(str(file_path), 'wb') as dst:
    dst.setparams(params)
    dst.setframerate(target_sample_rate)
    dst.writeframes(audio_data)

  logging.info('Audio file fixed successfully: %r', file_path)

  logging.info('Audio file fixed successfully: %r', file_path)


def record_and_check_recorded_audio_file_silent(
    ad: android_device.AndroidDevice,
    bt_device: tws_device.TwsDevice,
    test_info: Any,
    call_type: CallType = CallType.TRADITIONAL,
    playback_duration: datetime.timedelta | None = None,
) -> dict[str, bool]:
  """Records audio from BT device and phone speaker, and checks for silence.

  Note: Need to register screen_recorder service with "start_service=False"
  status on the Android device before using this function.

  Args:
    ad: Android device.
    bt_device: TWS device.
    test_info: The test info object, used for output path.
    call_type: The call type, used to determine the ZCR threshold.
    playback_duration: The duration to record audio for. If None,
      _AUDIO_PLAYBACK_DURATION_TIMEOUT is used.

  Returns:
    A dictionary containing the silence check results:
      - 'is_speaker_silent': bool | None, True if the recorded speaker audio is
        silent, False otherwise. None if expect_speaker_silent was None.
      - 'is_bt_silent': bool | None, True if the recorded BT audio is silent,
        False otherwise. None if expect_bt_silent was None or no BT audio was
        recorded.
  """
  duration = (
      playback_duration
      if playback_duration is not None
      else _AUDIO_PLAYBACK_DURATION_TIMEOUT
  )
  is_speaker_silent = True
  is_bt_silent = True

  if ad.services.screen_recorder.is_alive:
    ad.services.screen_recorder.stop()
    time.sleep(_AUDIO_RECORDER_REBOOT_TIMEOUT.total_seconds())
  # Start recording the audio from the phone speaker.
  ad.services.screen_recorder.start()

  # Starts the audio recording from the BT device.
  bt_device.start_audio_recording(
      channels=_AudioChannelMode.STEREO,
      sample_rate=_BT_AUDIO_RECORDING_SAMPLE_RATE,
  )

  # Waits for the minimum intentional duration needed for the test.
  # If the test crashes here, the 'finally' ensures stop/cleanup occurs.
  time.sleep(duration.total_seconds())

  # Stops the audio recording from the BT device.
  recorded_bluetooth_audio_on_host = bt_device.stop_audio_recording(
      test_info.output_path
  )

  if recorded_bluetooth_audio_on_host:
    for path in recorded_bluetooth_audio_on_host:
      fix_bes_audio_sampling_rate(path)

  # Retrieve the recorded audios after the recorders stopped.
  recorded_speaker_played_audio_on_host = (
      ad.services.screen_recorder.create_output_excerpts(test_info)
  )
  ad.log.info(
      'Recorded ROUTE_SPEAKER audio file: %s',
      recorded_speaker_played_audio_on_host,
  )

  ad.log.info(
      'Recorded ROUTE_BLUETOOTH audio file, when audio is playing on'
      ' bluetooth: %s',
      recorded_bluetooth_audio_on_host,
  )
  time.sleep(_AUDIO_RECORDING_FINISH_TIMEOUT.total_seconds())

  # Verifies phone speaker recording silence.
  if recorded_speaker_played_audio_on_host:
    is_speaker_silent = is_audio_file_empty_or_silent(
        recorded_speaker_played_audio_on_host[1],
        call_type,
    )
    ad.log.info(
        'Phone speaker silence check result: silent=%s.', is_speaker_silent
    )
  else:
    ad.log.warning('No audio file recorded from phone speaker.')

  # Verifies BT recording silence.
  if recorded_bluetooth_audio_on_host:
    is_bt_silent = is_audio_file_empty_or_silent(
        recorded_bluetooth_audio_on_host[0],
        call_type,
    )
    ad.log.info('Bluetooth silence check result: silent=%s.', is_bt_silent)
  else:
    ad.log.warning('No audio file recorded from Bluetooth device.')

  return {'is_speaker_silent': is_speaker_silent, 'is_bt_silent': is_bt_silent}


def check_audio_route(
    ad: android_device.AndroidDevice,
    bt_device: tws_device.TwsDevice,
    test_info: Any,
    *,
    expected_route: AudioRoute,
    call_type: CallType = CallType.TRADITIONAL,
    playback_duration: datetime.timedelta | None = None,
) -> None:
  """Records audio and asserts for the expected audio route.

  Args:
    ad: Android device.
    bt_device: TWS device.
    test_info: The test info object, used for output path.
    expected_route: The expected audio route, either "expect_route_to_speaker"
      or "expect_route_to_bluetooth".
    call_type: The call type, used to determine the ZCR threshold.
    playback_duration: The duration to record audio for.
  """
  results = record_and_check_recorded_audio_file_silent(
      ad,
      bt_device,
      test_info,
      call_type,
      playback_duration,
  )

  if expected_route == AudioRoute.ROUTE_TO_SPEAKER:
    asserts.assert_equal(
        results['is_speaker_silent'],
        False,
        'Audio was expected to be routed to the speaker, but speaker audio was'
        ' silent.',
    )
    asserts.assert_equal(
        results['is_bt_silent'],
        True,
        'Audio was expected to be routed to the speaker, but audio was also'
        ' detected in Bluetooth.',
    )

  elif expected_route == AudioRoute.ROUTE_TO_BLUETOOTH:
    asserts.assert_equal(
        results['is_bt_silent'],
        False,
        'Audio was expected to be routed to Bluetooth, but BT audio was'
        ' silent.',
    )
  # from the speaker, since scrcpy will record both route from speaker and BT.
  # After this bug is fixed, we can verify the audio is not silent from the
  # bluetooth when it's expected to be routed to the Bluetooth.
  elif expected_route == AudioRoute.ROUTE_FOR_RING_TONE:
    asserts.assert_equal(
        results['is_bt_silent'],
        True,
        'Audio was expected to be routed to Bluetooth, but BT audio was'
        ' silent.',
    )
    asserts.assert_equal(
        results['is_speaker_silent'],
        False,
        'Audio to speaker cross check failed.',
    )

  elif expected_route == AudioRoute.NO_AUDIO_TO_BOTH_SPEAKER_AND_BLUETOOTH:
    asserts.assert_equal(
        results['is_bt_silent'],
        True,
        'Audio was expected to be silent, but BT audio was not silent.',
    )
    asserts.assert_equal(
        results['is_speaker_silent'],
        True,
        'Audio to speaker cross check failed.',
    )
  else:
    asserts.fail(f'Invalid expected_route: {expected_route}.')


def record_and_verify_downlink_audio(
    ad: android_device.AndroidDevice,
    test_info: Any,
    duration: datetime.timedelta,
    call_type: CallType = CallType.TRADITIONAL,
    expect_silent: bool = True,
    offset_sec: float = 0.0,
) -> bool:
  """Records downlink audio from the phone and checks for silence.

  Args:
    ad: Android device.
    test_info: The test info object, used for output path.
    duration: The duration to record audio for.
    call_type: The call type, used to determine the ZCR threshold.
    expect_silent: Whether the audio is expected to be silent.
    offset_sec: The offset in seconds to start loading audio from.

  Returns:
    True if the silence check result matches `expect_silent`, False otherwise.
  """

  if ad.services.screen_recorder.is_alive:
    ad.services.screen_recorder.stop()
    time.sleep(_AUDIO_RECORDER_REBOOT_TIMEOUT.total_seconds())

  ad.log.info(
      'Starting downlink audio recording for %fs...', duration.total_seconds()
  )
  ad.services.screen_recorder.start()

  time.sleep(duration.total_seconds())

  excerpts = ad.services.screen_recorder.create_output_excerpts(test_info)

  if not excerpts or len(excerpts) < 2:
    ad.log.error('Failed to record downlink audio excerpts.')
    return False

  recorded_audio_path = excerpts[1]
  ad.log.info('Recorded audio file: %s', recorded_audio_path)

  is_silent = is_audio_file_empty_or_silent(
      recorded_audio_path, call_type, offset_sec=offset_sec
  )
  ad.log.info(
      'Silence check result: is_silent=%s, expected_silent=%s',
      is_silent,
      expect_silent,
  )

  return is_silent == expect_silent


def start_downlink_audio_recording(ad: android_device.AndroidDevice):
  """Starts downlink audio recording.

  This function should be called before making or receiving a call to ensure
  that the immediate audio is captured.

  Args:
    ad: The Android device to start recording on.
  """
  if ad.services.screen_recorder.is_alive:
    ad.log.info('Detecting ongoing recorder, stopping...')
    ad.services.screen_recorder.stop()
    time.sleep(_AUDIO_RECORDER_REBOOT_TIMEOUT.total_seconds())

  ad.log.info('Starting downlink audio recording...')
  ad.services.screen_recorder.start()


def stop_and_verify_downlink_audio(
    ad: android_device.AndroidDevice,
    test_info: Any,
    call_type: CallType = CallType.TRADITIONAL,
    expect_silent: bool = False,
) -> bool:
  """Stops downlink audio recording and verifies the audio content.

  Args:
    ad: Android device.
    test_info: The test info object, used for output path.
    call_type: The call type, used to determine the ZCR threshold.
    expect_silent: Whether the audio is expected to be silent.

  Returns:
    True if the silence check result matches `expect_silent`.
  """
  ad.log.info('Stopping downlink audio recording and extracting excerpts...')
  ad.services.screen_recorder.stop()

  excerpts = ad.services.screen_recorder.create_output_excerpts(test_info)

  if not excerpts or len(excerpts) < 2:
    ad.log.error('Failed to record downlink audio excerpts.')
    return False

  recorded_audio_path = excerpts[1]
  ad.log.info('Recorded audio file: %s', recorded_audio_path)

  is_silent = is_audio_file_empty_or_silent(recorded_audio_path, call_type)
  ad.log.info(
      'Silence check result: is_silent=%s, expected_silent=%s',
      is_silent,
      expect_silent,
  )

  return is_silent == expect_silent
