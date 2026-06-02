# OpenCV H.264 Video Recording Troubleshooting & Source Compilation Guide

## 1. Bug Symptoms & Root Cause

### 1.1 Bug Symptoms
During automation testing involving device screen recording or video processing,
the test suite crashes with a fatal `FileNotFoundError` when attempting to
collect or move `.mp4` video files:

```text
FileNotFoundError: [Errno 2] No such file or directory: 'path/to/output/video.mp4'
```

### 1.2 Root Cause
The standard pre-compiled `opencv-python` package distributed via `pip`
intentionally omits H.264 (x264) encoding support due to licensing and
commercial royalty obligations. When a framework attempts to initialize
`cv2.VideoWriter` with H.264 codecs, the underlying encoder silently fails
in the background without generating a physical output container.

---

## 2. Solution: Custom OpenCV Compilation with Native H.264 Support

To resolve this issue, OpenCV must be compiled from source on the local Linux
machine with `libx264-dev` explicitly linked.

### Step 1: Install Linux System Dependencies and Python Headers

```bash
sudo apt update
sudo apt install -y build-essential cmake git pkg-config \
libjpeg-dev libpng-dev libtiff-dev \
libavcodec-dev libavformat-dev libswscale-dev libv4l-dev \
libxvidcore-dev libx264-dev \
libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
python3-dev
```

### Step 2: Clone and Align OpenCV 4.9.0 Source Repositories

```bash
# Clean up old residues before cloning
rm -rf opencv opencv_contrib
git clone https://github.com/opencv/opencv.git
git clone https://github.com/opencv/opencv_contrib.git

# Lock both repositories to the 4.9.0 stable release tag
cd opencv && git checkout 4.9.0
cd ../opencv_contrib && git checkout 4.9.0
```

### Step 3: Configure the CMake Matrix with Precise Routing

Navigate to the build directory and inject the `-D WITH_FFMPEG=ON` flag. Ensure
the Python interpreter, system header paths, and packages directory match your
target environment:

```bash
cd ../opencv
mkdir build && cd build

cmake -D CMAKE_BUILD_TYPE=RELEASE \
      -D CMAKE_INSTALL_PREFIX=/usr/local \
      -D OPENCV_EXTRA_MODULES_PATH=$(pwd)/../../opencv_contrib/modules \
      -D WITH_FFMPEG=ON \
      -D BUILD_opencv_python3=ON \
      -D PYTHON3_EXECUTABLE=$(which python3) \
      -D PYTHON3_INCLUDE_DIR=/usr/include/python3.11 \
      -D PYTHON3_PACKAGES_PATH=.venv/lib/python3.11/site-packages \
      -D BUILD_EXAMPLES=OFF ..
```

### Step 4: Parallel Compilation and System-Level Installation

```bash
# Max out CPU utilization for multi-threaded compilation
make -j$(nproc)

# Install the compiled binaries to system standard libraries
sudo make install
sudo ldconfig
```

### Step 5: Prune the Dangling Symlink and Manual Deploy `cv2.so`

Remove any pre-existing broken or dangling `cv2.so` symlinks in your virtual
environment, then deploy the freshly compiled binary:

```bash
# Delete the old symlink from the target virtual environment
rm -f .venv/lib/python3.11/site-packages/cv2.so

# Locate and copy the newly compiled H.264-enabled library
cp $(find lib/ -name "cv2*.so") .venv/lib/python3.11/site-packages/cv2.so
```

---

## 3. Verification

Run the following verification command inside your virtual environment to
ensure the library is properly bound and supporting the codec:

```bash
python3 -c "import cv2; print('Library Path:', cv2.__file__); print('H.264 FourCC Check:', cv2.VideoWriter_fourcc(*'X264'))"
```

**Expected Successful Output Status:**

* **Library Path:** Points to your local workspace virtual environment
  site-packages folder.
* **H.264 FourCC Check:** Returns a non-zero integer (e.g., `875967064`)
  without throwing any Codec or initialization exceptions.

---

## 4. Crucial Success Output Signs

When your test framework initializes the media pipeline and invokes
`cv2.VideoWriter`, the build configuration is validated **ONLY** if the
following two fallback lines appear in your runtime execution logs:

```text
OpenCV: FFMPEG: tag 0x34363248/'H264' is not supported with codec id 27 and format 'mp4 / MP4 (MPEG-4 Part 14)'
OpenCV: FFMPEG: fallback to use tag 0x31637661/'avc1'
```

### Technical Context: Why is this the definitive success marker?

* **Line 1:** Confirms that the custom-linked FFMPEG engine inside OpenCV has
  successfully intercepted and decoded the native H.264 raw bitstream (Codec
  ID `27` structurally maps to `AV_CODEC_ID_H264`). It evaluates that the strict
  literal tag `H264` is non-standard for the MP4 container spec.
* **Line 2 (The Fix):** FFMPEG automatically and safely negotiates a fallback
  behavior to use **`avc1`** (the official registration tag for H.264 payloads
  wrapped inside standard ISO/IEC MP4 containers).

**Conclusion:** The appearance of these log entries guarantees that OpenCV,
FFMPEG, and `libx264` have established an active encoding pipeline. Video
streams are being encoded to disk via hardware-accelerated H.264, resolving the
video-missing errors.