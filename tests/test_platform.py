"""Unit tests for netrr.platform; they must pass on any host (macOS included)."""

import os
import stat
import tempfile
import unittest
from unittest import mock

from netrr import platform as nplatform
from netrr.platform import PlatformInfo, detect_platform, read_text


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
