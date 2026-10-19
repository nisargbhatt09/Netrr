"""Unit tests for the OpenCV/GStreamer check in smart_glasses.doctor.

cv2 is replaced with a fake in sys.modules so the check runs on any host.
"""

import sys
import types
import unittest
from unittest import mock

from netrr.platform import PlatformInfo
from smart_glasses import doctor


def _info(name, jetson=False):
    return PlatformInfo(name=name, is_raspberry_pi=False, is_jetson=jetson,
                        arch="x", python_version="3.0.0")


def _fake_cv2(build_info):
    mod = types.ModuleType("cv2")
    mod.getBuildInformation = lambda: build_info
    return mod


class TestCheckOpencvGstreamer(unittest.TestCase):
    def test_skipped_cleanly_when_cv2_missing(self):
        with mock.patch.dict(sys.modules, {"cv2": None}):
            self.assertEqual(doctor.check_opencv_gstreamer(_info("jetson", jetson=True)), [])

    def test_ok_when_built_with_gstreamer(self):
        with mock.patch.dict(sys.modules, {"cv2": _fake_cv2("    GStreamer:  YES (1.16.3)\n")}):
            results = doctor.check_opencv_gstreamer(_info("jetson", jetson=True))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], doctor.OK)

    def test_warn_with_fix_on_jetson_without_gstreamer(self):
        with mock.patch.dict(sys.modules, {"cv2": _fake_cv2("    GStreamer:  NO\n")}):
            results = doctor.check_opencv_gstreamer(_info("jetson", jetson=True))
        status, _, detail = results[0]
        self.assertEqual(status, doctor.WARN)
        self.assertIn("sudo apt install python3-opencv", detail)
        self.assertIn("WITH_GSTREAMER", detail)

    def test_warn_without_jetson_fix_elsewhere(self):
        with mock.patch.dict(sys.modules, {"cv2": _fake_cv2("    GStreamer:  NO\n")}):
            results = doctor.check_opencv_gstreamer(_info("macos"))
        status, _, detail = results[0]
        self.assertEqual(status, doctor.WARN)
        self.assertNotIn("python3-opencv", detail)

    def test_build_info_failure_is_a_warning_not_a_crash(self):
        cv2 = types.ModuleType("cv2")

        def boom():
            raise RuntimeError("no build info")

        cv2.getBuildInformation = boom
        with mock.patch.dict(sys.modules, {"cv2": cv2}):
            results = doctor.check_opencv_gstreamer(_info("jetson", jetson=True))
        self.assertEqual(results[0][0], doctor.WARN)


if __name__ == "__main__":
    unittest.main()
