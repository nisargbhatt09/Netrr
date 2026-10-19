"""Standard-library-only platform detection.

Tells the rest of Netrr whether it is running on a Raspberry Pi, an NVIDIA
Jetson, a generic Linux box, macOS or Windows, without importing any
third-party package so it can be unit-tested anywhere.
"""

import os
import platform as _platform
import sys
from dataclasses import dataclass

DEVICE_TREE_MODEL = "/proc/device-tree/model"
CPUINFO = "/proc/cpuinfo"
NV_TEGRA_RELEASE = "/etc/nv_tegra_release"


@dataclass(frozen=True)
class PlatformInfo:
    """Summary of the host the software is running on."""

    name: str  # "raspberry_pi", "jetson", "linux", "macos", "windows" or "unknown"
    is_raspberry_pi: bool
    is_jetson: bool
    arch: str
    python_version: str
    system: str = ""
    model: str = ""


def read_text(path):
    """Return the contents of `path`, or "" if it is missing or unreadable.

    Never raises: a missing file, a permission error, a directory, or
    undecodable bytes all yield an empty string.
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except (OSError, ValueError):
        return ""
    # Device-tree strings are NUL terminated; strip the terminator.
    return data.decode("utf-8", errors="replace").replace("\x00", "").strip()


def file_exists(path):
    """Return True if `path` exists, swallowing any OS error."""
    try:
        return os.path.exists(path)
    except OSError:
        return False


def is_raspberry_pi(model="", cpuinfo=""):
    """True if the device-tree model or cpuinfo text names a Raspberry Pi."""
    return "raspberry pi" in model.lower() or "raspberry pi" in cpuinfo.lower()


def is_jetson(model="", has_tegra_release=False):
    """True if the device-tree model names NVIDIA/Jetson or L4T release file exists."""
    lowered = model.lower()
    return "nvidia" in lowered or "jetson" in lowered or bool(has_tegra_release)


def detect_platform(model=None, cpuinfo=None, has_tegra_release=None, system=None):
    """Detect the host platform.

    Every argument is optional and exists for testing: when left as None it
    is read from the live system (defensively, never raising).
    """
    if model is None:
        model = read_text(DEVICE_TREE_MODEL)
    if cpuinfo is None:
        cpuinfo = read_text(CPUINFO)
    if has_tegra_release is None:
        has_tegra_release = file_exists(NV_TEGRA_RELEASE)
    if system is None:
        system = _platform.system()

    pi = is_raspberry_pi(model, cpuinfo)
    jetson = is_jetson(model, has_tegra_release)

    if pi:
        name = "raspberry_pi"
    elif jetson:
        name = "jetson"
    elif system == "Linux":
        name = "linux"
    elif system == "Darwin":
        name = "macos"
    elif system == "Windows":
        name = "windows"
    else:
        name = "unknown"

    return PlatformInfo(
        name=name,
        is_raspberry_pi=pi,
        is_jetson=jetson,
        arch=_platform.machine() or "unknown",
        python_version="%d.%d.%d" % sys.version_info[:3],
        system=system,
        model=model,
    )


CAMERA_BACKEND_PICAMERA2 = "picamera2"
CAMERA_BACKEND_JETSON_GSTREAMER = "jetson_gstreamer"
CAMERA_BACKEND_OPENCV = "opencv"


def camera_backend_for(info):
    """Return the preferred camera backend name for a PlatformInfo.

    Pure and deterministic: "picamera2" on a Raspberry Pi, "jetson_gstreamer"
    on a Jetson (the CSI camera is only reachable through nvarguscamerasrc)
    and "opencv" (a plain cv2.VideoCapture) everywhere else.
    """
    if info.is_raspberry_pi:
        return CAMERA_BACKEND_PICAMERA2
    if info.is_jetson:
        return CAMERA_BACKEND_JETSON_GSTREAMER
    return CAMERA_BACKEND_OPENCV


# The one actionable fix when OpenCV on a Jetson lacks GStreamer: the pip
# wheels (opencv-python, opencv-python-headless) are built without it, the
# JetPack system package is built with it.
OPENCV_GSTREAMER_FIX = (
    "install the JetPack system OpenCV with `sudo apt install python3-opencv` "
    "(and use a venv created with --system-site-packages), or build OpenCV "
    "with WITH_GSTREAMER=ON"
)


def opencv_has_gstreamer(build_info_string):
    """True only if a cv2.getBuildInformation() string reports GStreamer: YES.

    Pure and standard-library only. The build report contains a line such as
    ``    GStreamer:                   YES (1.20.3)`` or ``    GStreamer: NO``
    under "Video I/O". Anything other than a YES value (NO, a missing line,
    an empty or non-string input) yields False.
    """
    if not isinstance(build_info_string, str):
        return False
    for line in build_info_string.splitlines():
        key, sep, value = line.partition(":")
        if not sep or key.strip().lower() != "gstreamer":
            continue
        return value.strip().upper().startswith("YES")
    return False


if __name__ == "__main__":
    print(detect_platform())
