"""Unit tests for netrr.platform; they must pass on any host (macOS included)."""

import os
import stat
import tempfile
import unittest
from unittest import mock

from netrr import platform as nplatform
from netrr.platform import (
    OPENCV_GSTREAMER_FIX,
    PlatformInfo,
    camera_backend_for,
    detect_platform,
    opencv_has_gstreamer,
    read_text,
)


def _info(name, pi=False, jetson=False):
    return PlatformInfo(name=name, is_raspberry_pi=pi, is_jetson=jetson,
                        arch="x", python_version="3.0.0")


class TestCameraBackendFor(unittest.TestCase):
    def test_raspberry_pi_uses_picamera2(self):
        self.assertEqual(camera_backend_for(_info("raspberry_pi", pi=True)), "picamera2")

    def test_jetson_uses_gstreamer(self):
        self.assertEqual(camera_backend_for(_info("jetson", jetson=True)), "jetson_gstreamer")

    def test_everything_else_uses_opencv(self):
        for name in ("linux", "macos", "windows", "unknown"):
            self.assertEqual(camera_backend_for(_info(name)), "opencv", name)

    def test_pi_wins_if_both_flags_set(self):
        self.assertEqual(camera_backend_for(_info("raspberry_pi", pi=True, jetson=True)), "picamera2")

    def test_matches_detect_platform(self):
        self.assertEqual(camera_backend_for(detect_platform("Raspberry Pi 4", "", False, "Linux")), "picamera2")
        self.assertEqual(camera_backend_for(detect_platform("", "", True, "Linux")), "jetson_gstreamer")
        self.assertEqual(camera_backend_for(detect_platform("", "", False, "Darwin")), "opencv")

    def test_deterministic(self):
        info = _info("jetson", jetson=True)
        self.assertEqual(camera_backend_for(info), camera_backend_for(info))


class TestDetectPlatform(unittest.TestCase):
    def test_raspberry_pi_from_device_tree_model(self):
        info = detect_platform(model="Raspberry Pi 5 Model B Rev 1.0\x00",
                               cpuinfo="", has_tegra_release=False, system="Linux")
        self.assertEqual(info.name, "raspberry_pi")
        self.assertTrue(info.is_raspberry_pi)
        self.assertFalse(info.is_jetson)

    def test_raspberry_pi_from_cpuinfo(self):
        info = detect_platform(model="", cpuinfo="Hardware\t: BCM2835\nModel\t\t: Raspberry Pi 4 Model B",
                               has_tegra_release=False, system="Linux")
        self.assertEqual(info.name, "raspberry_pi")
        self.assertTrue(info.is_raspberry_pi)

    def test_jetson_from_device_tree_model(self):
        info = detect_platform(model="NVIDIA Jetson Orin Nano Developer Kit",
                               cpuinfo="", has_tegra_release=False, system="Linux")
        self.assertEqual(info.name, "jetson")
        self.assertTrue(info.is_jetson)
        self.assertFalse(info.is_raspberry_pi)

    def test_jetson_from_tegra_release_file(self):
        info = detect_platform(model="", cpuinfo="", has_tegra_release=True, system="Linux")
        self.assertEqual(info.name, "jetson")
        self.assertTrue(info.is_jetson)

    def test_generic_linux(self):
        info = detect_platform(model="", cpuinfo="model name : Intel", has_tegra_release=False, system="Linux")
        self.assertEqual(info.name, "linux")
        self.assertFalse(info.is_raspberry_pi)
        self.assertFalse(info.is_jetson)

    def test_macos_and_windows_and_unknown(self):
        self.assertEqual(detect_platform("", "", False, "Darwin").name, "macos")
        self.assertEqual(detect_platform("", "", False, "Windows").name, "windows")
        self.assertEqual(detect_platform("", "", False, "Plan9").name, "unknown")

    def test_monkeypatched_file_reads(self):
        """Simulate a Pi by patching the file reader instead of passing args."""
        def fake_read(path):
            return "Raspberry Pi Zero 2 W" if path == nplatform.DEVICE_TREE_MODEL else ""

        with mock.patch.object(nplatform, "read_text", side_effect=fake_read), \
                mock.patch.object(nplatform, "file_exists", return_value=False):
            info = detect_platform(system="Linux")
        self.assertEqual(info.name, "raspberry_pi")

    def test_live_detection_never_raises(self):
        info = detect_platform()
        self.assertIsInstance(info, PlatformInfo)
        self.assertIn(info.name, {"raspberry_pi", "jetson", "linux", "macos", "windows", "unknown"})
        self.assertIsInstance(info.arch, str)
        self.assertRegex(info.python_version, r"^\d+\.\d+\.\d+$")


JETPACK_BUILD_INFO = """
General configuration for OpenCV 4.5.4 =====================================
  Version control:               4.5.4

  Video I/O:
    DC1394:                      NO
    FFMPEG:                      YES
      avcodec:                   YES (58.134.100)
    GStreamer:                   YES (1.16.3)
    v4l/v4l2:                    YES (linux/videodev2.h)
"""

PIP_WHEEL_BUILD_INFO = """
General configuration for OpenCV 4.10.0 =====================================
  Video I/O:
    DC1394:                      NO
    FFMPEG:                      YES
      avcodec:                   YES (59.37.100)
    GStreamer:                   NO
    v4l/v4l2:                    YES (linux/videodev2.h)
"""


class TestOpencvHasGstreamer(unittest.TestCase):
    def test_jetpack_build_reports_yes(self):
        self.assertTrue(opencv_has_gstreamer(JETPACK_BUILD_INFO))

    def test_pip_wheel_reports_no(self):
        self.assertFalse(opencv_has_gstreamer(PIP_WHEEL_BUILD_INFO))

    def test_yes_without_version_suffix(self):
        self.assertTrue(opencv_has_gstreamer("  GStreamer:  YES\n"))

    def test_case_and_whitespace_insensitive(self):
        self.assertTrue(opencv_has_gstreamer("gstreamer :   yes (1.20.3)"))
        self.assertFalse(opencv_has_gstreamer("GSTREAMER:no"))

    def test_missing_entry_is_false(self):
        self.assertFalse(opencv_has_gstreamer("  Video I/O:\n    FFMPEG:  YES\n"))

    def test_empty_and_non_string_are_false(self):
        self.assertFalse(opencv_has_gstreamer(""))
        self.assertFalse(opencv_has_gstreamer(None))
        self.assertFalse(opencv_has_gstreamer(42))

    def test_other_yes_lines_do_not_count(self):
        """A YES on a different Video I/O line must not be mistaken for GStreamer."""
        self.assertFalse(opencv_has_gstreamer("    FFMPEG: YES\n    GStreamer: NO\n    v4l/v4l2: YES\n"))

    def test_mention_in_prose_is_not_an_entry(self):
        """Only a `GStreamer: <value>` entry counts, not the word elsewhere."""
        self.assertFalse(opencv_has_gstreamer("Built without GStreamer support: YES"))

    def test_fix_message_names_the_apt_package_and_cmake_flag(self):
        self.assertIn("sudo apt install python3-opencv", OPENCV_GSTREAMER_FIX)
        self.assertIn("WITH_GSTREAMER", OPENCV_GSTREAMER_FIX)


class TestReadText(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        self.assertEqual(read_text("/definitely/not/a/real/file"), "")

    def test_directory_returns_empty(self):
        self.assertEqual(read_text(tempfile.gettempdir()), "")

    def test_strips_nul_terminator(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            f.write(b"Raspberry Pi 4 Model B\x00")
        try:
            self.assertEqual(read_text(f.name), "Raspberry Pi 4 Model B")
        finally:
            os.unlink(f.name)

    def test_permission_error_returns_empty(self):
        with mock.patch("builtins.open", side_effect=PermissionError("denied")):
            self.assertEqual(read_text("/proc/device-tree/model"), "")

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "chmod-based test needs a non-root POSIX user")
    def test_unreadable_file_returns_empty(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            f.write(b"secret")
        try:
            os.chmod(f.name, 0)
            self.assertEqual(read_text(f.name), "")
        finally:
            os.chmod(f.name, stat.S_IRUSR | stat.S_IWUSR)
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
