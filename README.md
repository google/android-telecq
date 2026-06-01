# Telephony Compliance Quality Suite (android-telecq)

## What is android-telecq?

android-telecq is an automated test suite for validating Android voice calling
functionality over Bluetooth Classic (HFP) and LE Audio (LEA) profiles by
executing critical user journeys (CUJs).

The primary goal of this project is to provide a comprehensive, automated
testing solution that ensures cellular and VoIP calling features, audio routing,
call preemption, and connection stability are robust and reliable across a wide
range of Android devices.

This is not an officially supported Google product. This project is not eligible
for the
[Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).

## What is Tested?

The test suite covers key cellular mobile call and Voice over IP (VoIP) call
scenarios when connected to Bluetooth Classic HFP or LE Audio (LEA) headsets.
The tests validate call establishment, bidirectional audio routing, call
preemption during active media playback, call rejection, and mid-call audio
route switching.

The following sections provide a detailed breakdown of the features under test
for each category.

### Cellular Mobile Call Tests (SIM Required)

*   **`MobileCallWithClassicHfpTest`** (Classic HFP):
    *   **Call Control**: Make and answer incoming/outgoing cellular calls;
        verify call rejection and correct call termination from the HFP headset
        during dialing and active states.
    *   **Ringtone Routing**: Verify incoming call ringtone is correctly routed
        to the HFP headset.
    *   **Call Preemption**: Verify incoming and outgoing cellular calls
        correctly pause active media playback and resume media streaming
        afterward.
    *   **Audio Route Switching**: Verify mid-call audio route switching
        between the HFP headset and the phone earpiece/speaker.
    *   **Link Re-establishment**: Verify call audio automatically restores to
        the HFP headset when the headset is powered off and back on, or when
        the phone's Bluetooth is toggled off and on during a call.
*   **`MobileCallWithLeaTest`** (LE Audio):
    *   **Call Control**: Make, answer, and end incoming/outgoing cellular
        calls through the LE Audio headset.
    *   **Ringtone Routing**: Verify incoming call ringtone is correctly routed
        to the LE Audio headset.
    *   **Call Preemption**: Verify incoming and outgoing cellular calls
        correctly pause active media playback on LE Audio and resume media
        streaming afterward.
    *   **Audio Route Switching**: Verify mid-call audio route switching
        between the LE Audio headset and the phone speaker during an active
        call.

### Voice over IP (VoIP) Call Tests (No SIM Required)

*   **`VoipCallWithHfpHeadsetTest`** (Classic HFP):
    *   **Call Control**: Initiate, answer, reject, and end self-managed VoIP
        calls through the HFP headset, including active and dialing states.
    *   **Ringtone Routing**: Verify incoming VoIP call ringtone is correctly
        routed to the HFP headset.
    *   **Audio Route Switching**: Verify mid-call audio route switching
        between the HFP headset and the phone speaker/earpiece.
    *   **Link Re-establishment**: Verify call audio automatically restores to
        the HFP headset when the headset is powered off/on or when the phone's
        Bluetooth is toggled during an active VoIP call.
*   **`VoipCallWithLeaHeadsetTest`** (LE Audio):
    *   **Call Control**: Initiate, answer, and end self-managed VoIP calls
        through the LE Audio headset.
    *   **Ringtone Routing**: Verify incoming VoIP call ringtone is correctly
        routed to the LE Audio headset.
    *   **Call Preemption**: Verify incoming and outgoing VoIP calls correctly
        pause active media playback on the LE Audio headset and resume media
        afterward.
    *   **Audio Route Switching**: Verify mid-call audio route switching
        between the LE Audio headset and the phone earpiece/speaker.

## Hardware Requirements

To run the full test suite, you will need the following hardware:

*   **Mobly Host**: A Linux desktop computer.
*   **Android Devices**: **Three** Android devices.
    -   **DUT (Device Under Test)**: The primary phone whose Bluetooth and
        telecom calling functionality is being evaluated.
    -   **REF (Reference Phone)**: The second phone used as the far-end device
        during cellular call tests (placing calls to or receiving calls from the
        DUT).
    -   **REF2 (Media Player Phone)**: The third phone used to play test audio
        (e.g., voice recording audio files) into the REF phone's microphone
        during an active call to simulate far-end speech and verify end-to-end
        audio transmission.
    -   **[Important Note] Build Type**: A `userdebug` build on the DUT is
        recommended for full automation. `userdebug` builds allow tests to
        automatically switch between LE Audio and Classic profiles during a test
        run. If you require this level of automation, a `userdebug` build is
        necessary. If you are using a `user` build, you need to manually set the
        profile before testing: enable LE Audio in Developer Options to run LEA
        tests, or disable it to run Classic tests. Note: This manual toggle
        option may not be available on all devices (e.g., Samsung).
*   **SIM Cards**: **Two** active SIM cards are required for testing cellular
    mobile call features (installed on DUT and REF). REF2 does not require a SIM
    card. If either DUT or REF lacks an active SIM card, cellular mobile call
    tests will be skipped. (Note: VoIP call tests use self-managed phone
    accounts and do not require SIM cards).
*   **BES Boards**: Two BES reference boards (one pair for TWS tests). BES board
    is a reference device from the
    [mobly-bluetooth-ref-validation](https://github.com/google/mobly-bluetooth-ref-validation)
    project.

### Test Environment

It is strongly recommended to use an RF shielding box or room for setting up the
test environment to minimize wireless signal interference and ensure test
stability and result reliability.

For test suites involving cellular phone calls, both DUT and REF Android devices
must be equipped with active SIM cards and ensure both phones have stable
cellular signal.

### Host Prerequisites

Ensure the host machine has the following software installed:

*   `arecord`
    *   You can install `arecord` on the desktop if you haven't. You can use
        `sudo apt-get install alsa-utils` to install it on Debian/Ubuntu.
*   [Android Debug Bridge (adb)](https://developer.android.com/tools/adb)
    (1.0.40+ recommended)
*   python3.11+
*   VIDEO SERVICE: The test framework uses the open-source Mobly Android
    Screen Recorder (https://github.com/google/mobly-android-screen-recorder)
    to automatically capture screen recordings and audio during tests.
    -   **Requirements**: FFMPEG 6.1.1+ with H.264 support (run `ffmpeg -codecs`
        and look for `libx264` encoder) and OpenCV in Python built with the
        H.264 encoder.
    -   **Audio Recording**: The `ffmpeg` binary must be installed and
        available in your host system's `PATH`.

### Phone Setup Instructions

**Enable Developer Options on Android Devices**:

-   On all three Android devices, enable
    [developer options](https://developer.android.com/studio/debug/dev-options)
    and turn on **USB debugging**.
-   Connect the devices to the host machine via USB and authorize the
    connection.
-   Verify the devices are connected by running `adb devices`.

### Prepare BES Device

If you use the BES Bluetooth dev board as the reference device, please follow
these steps:

**If it's your first time preparing a BES board, please
[follow this instruction](docs/[External Sharing] BES v2 Board Setup and Remote Control.pdf).**

1.  Prepare *one* pair for TWS tests.
2.  Connect the `USB-UART` port of the board with your PC/workstation using a
    USB cable.
3.  Press `PWR` button on the board if needed.
4.  Note down the serial port of the BES board. We'll need it for the
    configuration file.

#### How to Get Serial Port of the BES Board

For Linux, the serial port is something like `/dev/ttyUSB0`. Command to list the
available ports:

```bash
ls /dev/ttyUSB*
```

## Configure Testbed

1.  Modify the Mobly device config YAML file (e.g., `TelecomLocalTestbed.yaml`)
    to match your setup.
2.  Update the `serial` and `phone_number` under `AndroidDevice` with your three
    devices' serial numbers (from `adb devices`) and corresponding SIM phone
    numbers. **Note**: The order of devices under `AndroidDevice` is critical.
    The first device is assigned as the DUT, the second as REF, and the third as
    REF2 (Media Player Phone).
3.  Update `serial_port` and `bluetooth_address` for the
    `BluetoothReferenceDevice` section based on your BES device setup.

    When setting up, you need to identify the `serial_port` and `pcm_name` for
    each board. To do this correctly, connect only one BES board to the host
    machine at a time:

    *   To find its serial port, run `ls /dev/ttyUSB*`.
    *   To find its `pcm_name` for `audio_configs`, run `arecord -l`. This lists
        audio capture devices. Find the line for the BES device and note card
        number `X` and device `Y` from `card X: ..., device Y: ...`. The
        `pcm_name` is `plughw:X,Y`.

    Note down the values for the first board, then disconnect it and repeat the
    process for the second board. This ensures you can distinguish between
    boards and correctly fill in the `serial_port` and `pcm_name` for
    `left_config` and `right_config`.

    Example `TelecomLocalTestbed.yaml`:

    ```yaml
    TestBeds:
      - Name: TelecomLocalTestbed
        Controllers:
          AndroidDevice:
            - serial: 'localhost:1234'
              dimensions:
                phone_number: '1234567890'
            - serial: 'localhost:1234'
              dimensions:
                phone_number: '1234567890'
            - serial: 'localhost:1234'
              dimensions:
                phone_number: '10000000002'

          BluetoothReferenceDevice:
            - controller_name: 'TwsDevice'
              controller_type: 'BesDevice'
              primary_ear: 'RIGHT'
              left_config:
                remote_mode: false
                serial_port: '/dev/ttyUSB0'
                bluetooth_address: '11:11:22:33:33:70'
                audio_configs:
                  pcm_name: 'hw:0,0'
                  sample_rate: 8000
                  sample_format: 'S16_LE'
                  channels: 2
              right_config:
                remote_mode: false
                serial_port: '/dev/ttyUSB1'
                bluetooth_address: '11:11:22:33:33:71'
                audio_configs:
                  pcm_name: 'hw:1,0'
                  sample_rate: 8000
                  sample_format: 'S16_LE'
                  channels: 2

      MoblyParams:
        LogPath: './logs'

    ```

## Run Tests

This section explains how to set up the environment and run telecom end-to-end
tests.

### Install Dependencies

Run the following commands on your desktop computer to prepare Python
environment:

```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip3 install -r requirements.txt
```

### Run Test Suites

The telecom testcases are organized by Bluetooth profile (LE Audio vs Classic
HFP) and call type (Cellular Mobile Calls requiring SIM vs VoIP calls requiring
no SIM).

Profile \ Test Category | Cellular Mobile Calls (SIM Required) | VoIP Calls (Self-managed, No SIM Required)
:---------------------- | :----------------------------------- | :-----------------------------------------
**LE Audio (LEA)**      | `mobile_call_with_lea_test`          | `voip_call_with_lea_headset_test`
**Classic (HFP)**       | `mobile_call_with_classic_hfp_test`  | `voip_call_with_hfp_headset_test`

#### Run Cellular Mobile Call Tests (SIM Required)

Run the Bluetooth **LE Audio cellular call test suite**:

```bash
python3 -m android_telecq.telecom_automation_test_with_bluetooth.mobile_call_with_lea_test -c android_telecq/TelecomLocalTestbed.yaml
```

Run the Bluetooth **Classic HFP cellular call test suite**:

```bash
python3 -m android_telecq.telecom_automation_test_with_bluetooth.mobile_call_with_classic_hfp_test -c android_telecq/TelecomLocalTestbed.yaml
```

#### Run VoIP Call Tests (No SIM Required)

Run the Bluetooth **LE Audio VoIP call test suite**:

```bash
python3 -m android_telecq.telecom_automation_test_with_bluetooth.voip_call_with_lea_headset_test -c android_telecq/TelecomLocalTestbed.yaml
```

Run the Bluetooth **Classic HFP VoIP call test suite**:

```bash
python3 -m android_telecq.telecom_automation_test_with_bluetooth.voip_call_with_hfp_headset_test -c android_telecq/TelecomLocalTestbed.yaml
```

#### Run Specific Test Cases

For debugging purposes, you can run a single test case or a subset of tests by
adding the `--tests` flag.

+   To run a specific test case, add `--tests TestClass.test_method` to the
    execution command. For example:

    ```bash
    python3 -m android_telecq.telecom_automation_test_with_bluetooth.mobile_call_with_lea_test -c android_telecq/TelecomLocalTestbed.yaml --tests MobileCallWithLeaTest.test_outgoing_call_through_lea_headset
    ```

+   To run all tests in a specific test class, add `--tests TestClass` to the
    execution command. For example:

    ```bash
    python3 -m android_telecq.telecom_automation_test_with_bluetooth.mobile_call_with_lea_test -c android_telecq/TelecomLocalTestbed.yaml --tests MobileCallWithLeaTest
    ```

## View Results and Debug

You can upload the results to Google’s test result store, which brings 2
benefits:

-   Easily analyze the test results with the BTX viewer.
-   Easily share test results via a single URL link.

### Manually upload results

1.  If it's your first time using the result uploader:

    *   Follow the
        [Mobly Result Uploader README](https://github.com/android/mobly-android-partner-tools#first-time-setup)
        for first-time setup.
    *   Run `python3 -m pip install mobly-android-partner-tools` to install the
        result uploader.

2.  At the end of a completed test run, you'll see the final lines on the
    console output as follows. Record the folder path in the line starting with
    "Artifacts are saved in".

    ```
    Total time elapsed 961.7551812920001s
    Artifacts are saved in "/tmp/logs/mobly/TelecomLocalTestbed/10-23-2023_10-30-50-685"
    Test summary saved in "/tmp/logs/mobly/TelecomLocalTestbed/10-23-2023_10-30-50-685/test_summary.yaml"
    Test results: Error 0, Executed 12, Failed 0, Passed 12, Requested 0, Skipped 0
    ```

3.  Run the uploader command, setting the `artifacts_folder` as the path
    recorded in the previous step.

    ```bash
    results_uploader <artifacts_folder>
    ```

4.  If successful, at the end of the upload process you will get a link
    beginning with http://btx.cloud.google.com. You may view your results and
    share this link to others who wish to view your test results.

    *   If you do not see a link, consult the
        [Troubleshooting](https://github.com/android/mobly-android-partner-tools#troubleshooting)
        section.

### View your results in BTX

When you open a BTX link, you should see the following dashboard.

![target](docs/btx_target.png)

1.  Use this checkbox to show/hide test cases based on status (e.g., Failed,
    Passed, Skipped).
2.  A list of test cases along with their results: Green (passed), Red (failed),
    Grey (skipped). Click on the test case name to display the details for that
    test.
3.  Click to open the Mobly Inspector debugging UI. See more details below.
4.  A list of test artifacts (log files, bugreports, videos) recorded from the
    test case. Click to view/download the file contents.
5.  The test failure stacktrace, if the test failed.
6.  The test properties.

See
[Troubleshooting](https://github.com/android/mobly-android-partner-tools?tab=readme-ov-file#view-your-results-in-btx)
if you do not see the above elements or need more details.
