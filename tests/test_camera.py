"""Unit tests for smart_glasses.camera.

They run on any host: OpenCV and picamera2 are replaced with fakes injected
into sys.modules, so the backend selection and fall-through logic is tested
without any camera hardware or native dependency.
"""

import sys
import types
import unittest
from unittest import mock

from netrr.platform import PlatformInfo
from smart_glasses import camera as camera_mod
from smart_glasses.camera import Camera, backend_order_for, jetson_gstreamer_pipeline


def _info(name, pi=False, jetson=False):
    return PlatformInfo(name=name, is_raspberry_pi=pi, is_jetson=jetson,
                        arch="x", python_version="3.0.0")


class _FakeFrame:
    def __init__(self, h, w):
        self.shape = (h, w, 3)


class _FakeCapture:
    """Stand-in for cv2.VideoCapture recording how it was opened."""

    opened_with = []

    def __init__(self, source, api=None):
        _FakeCapture.opened_with.append((source, api))
        self.source = source
        self.released = False
        self.props = {}

    def isOpened(self):
        return _FakeCapture.should_open(self.source)

    @staticmethod
    def should_open(source):
        return True

    def set(self, prop, value):
        self.props[prop] = value

    def read(self):
        return True, _FakeFrame(480, 640)

    def release(self):
        self.released = True


def _fake_cv2(capture_cls=_FakeCapture):
    mod = types.ModuleType("cv2")
    mod.VideoCapture = capture_cls
    mod.CAP_GSTREAMER = 1800
    mod.CAP_PROP_FRAME_WIDTH = 3
    mod.CAP_PROP_FRAME_HEIGHT = 4
    mod.resize = lambda frame, size: _FakeFrame(size[1], size[0])
    return mod


class _FakePicam:
    instances = []

    def __init__(self, index):
        _FakePicam.instances.append(self)
        self.index = index
        self.started = False
        self.stopped = False
        self.preview_configuration = types.SimpleNamespace(
            main=types.SimpleNamespace(size=None, format=None), align=lambda: None)

    def configure(self, _):
        pass

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def capture_array(self):
        return _FakeFrame(480, 640)


def _fake_picamera2():
    mod = types.ModuleType("picamera2")
    mod.Picamera2 = _FakePicam
    return mod


class TestBackendOrder(unittest.TestCase):
    def test_orders(self):
        self.assertEqual(backend_order_for(_info("raspberry_pi", pi=True)), ["picamera2", "opencv"])
        self.assertEqual(backend_order_for(_info("jetson", jetson=True)), ["jetson_gstreamer", "opencv"])
        self.assertEqual(backend_order_for(_info("macos")), ["opencv"])


class TestJetsonPipeline(unittest.TestCase):
    def test_pipeline_uses_argus_and_nvvidconv(self):
        p = jetson_gstreamer_pipeline(640, 480, sensor_id=1)
        self.assertTrue(p.startswith("nvarguscamerasrc sensor-id=1"))
        self.assertIn("nvvidconv", p)
        self.assertIn("width=(int)640, height=(int)480", p)
        self.assertIn("appsink", p)


class TestCameraBackends(unittest.TestCase):
    def setUp(self):
        # The fall-through paths log warnings by design; keep the test output clean.
        camera_mod.logger.disabled = True
        self.addCleanup(setattr, camera_mod.logger, "disabled", False)
        _FakeCapture.opened_with = []
        _FakeCapture.should_open = staticmethod(lambda source: True)
        _FakePicam.instances = []

    def test_opencv_backend_on_laptop(self):
        with mock.patch.dict(sys.modules, {"cv2": _fake_cv2()}):
            cam = Camera(platform_info=_info("macos"))
            self.assertTrue(cam.is_available)
            self.assertEqual(cam.backend, "opencv")
            self.assertEqual(_FakeCapture.opened_with, [(0, None)])
            frame = cam.read()
            self.assertEqual(frame.shape, (480, 640, 3))
            cam.close()
        self.assertFalse(cam.is_available)
        self.assertIsNone(cam.read())

    def test_jetson_uses_gstreamer_pipeline(self):
        with mock.patch.dict(sys.modules, {"cv2": _fake_cv2()}):
            cam = Camera(platform_info=_info("jetson", jetson=True))
            self.assertEqual(cam.backend, "jetson_gstreamer")
            source, api = _FakeCapture.opened_with[0]
            self.assertIn("nvarguscamerasrc", source)
            self.assertEqual(api, 1800)
            cam.close()

    def test_jetson_falls_back_to_opencv_when_pipeline_fails(self):
        _FakeCapture.should_open = staticmethod(lambda source: isinstance(source, int))
        with mock.patch.dict(sys.modules, {"cv2": _fake_cv2()}):
            cam = Camera(platform_info=_info("jetson", jetson=True))
            self.assertTrue(cam.is_available)
            self.assertEqual(cam.backend, "opencv")
            self.assertEqual(len(_FakeCapture.opened_with), 2)
            cam.close()

    def test_jetson_without_gstreamer_opencv_logs_the_fix(self):
        """A pip-wheel cv2 (no GStreamer) must log the apt/WITH_GSTREAMER fix and fall through."""
        _FakeCapture.should_open = staticmethod(lambda source: isinstance(source, int))
        cv2 = _fake_cv2()
        cv2.getBuildInformation = lambda: "  Video I/O:\n    GStreamer:  NO\n"
        camera_mod.logger.disabled = False
        with mock.patch.dict(sys.modules, {"cv2": cv2}), \
                self.assertLogs(camera_mod.logger, level="ERROR") as logs:
            cam = Camera(platform_info=_info("jetson", jetson=True))
        self.assertEqual(cam.backend, "opencv")
        text = "\n".join(logs.output)
        self.assertIn("sudo apt install python3-opencv", text)
        self.assertIn("WITH_GSTREAMER", text)
        cam.close()

    def test_jetson_with_gstreamer_opencv_but_no_camera_does_not_blame_the_build(self):
        _FakeCapture.should_open = staticmethod(lambda source: isinstance(source, int))
        cv2 = _fake_cv2()
        cv2.getBuildInformation = lambda: "    GStreamer:  YES (1.20.3)\n"
        camera_mod.logger.disabled = False
        with mock.patch.dict(sys.modules, {"cv2": cv2}), \
                self.assertLogs(camera_mod.logger, level="ERROR") as logs:
            cam = Camera(platform_info=_info("jetson", jetson=True))
        self.assertEqual(cam.backend, "opencv")
        text = "\n".join(logs.output)
        self.assertNotIn("python3-opencv", text)
        self.assertIn("nvargus-daemon", text)
        cam.close()

    def test_pi_uses_picamera2(self):
        with mock.patch.dict(sys.modules, {"picamera2": _fake_picamera2(), "cv2": _fake_cv2()}):
            cam = Camera(platform_info=_info("raspberry_pi", pi=True))
            self.assertEqual(cam.backend, "picamera2")
            picam = _FakePicam.instances[0]
            self.assertTrue(picam.started)
            self.assertEqual(picam.preview_configuration.main.size, (640, 480))
            self.assertEqual(_FakeCapture.opened_with, [])
            self.assertEqual(cam.read().shape, (480, 640, 3))
            cam.close()
            self.assertTrue(picam.stopped)

    def test_pi_without_picamera2_falls_back_to_opencv(self):
        with mock.patch.dict(sys.modules, {"picamera2": None, "cv2": _fake_cv2()}):
            cam = Camera(platform_info=_info("raspberry_pi", pi=True))
            self.assertEqual(cam.backend, "opencv")
            cam.close()

    def test_nothing_works_is_unavailable_and_never_raises(self):
        with mock.patch.dict(sys.modules, {"picamera2": None, "cv2": None}):
            cam = Camera(platform_info=_info("raspberry_pi", pi=True))
            self.assertFalse(cam.is_available)
            self.assertIsNone(cam.backend)
            self.assertIsNone(cam.read())
            cam.close()  # must not raise

    def test_webcam_not_opened_is_unavailable(self):
        _FakeCapture.should_open = staticmethod(lambda source: False)
        with mock.patch.dict(sys.modules, {"cv2": _fake_cv2()}):
            cam = Camera(platform_info=_info("linux"))
            self.assertFalse(cam.is_available)
            self.assertIsNone(cam.read())

    def test_backend_raising_does_not_propagate(self):
        class Boom:
            def __init__(self, *a):
                raise OSError("driver exploded")

        with mock.patch.dict(sys.modules, {"cv2": _fake_cv2(Boom)}):
            cam = Camera(platform_info=_info("linux"))
            self.assertFalse(cam.is_available)

    def test_read_resizes_to_requested_size(self):
        class BigCapture(_FakeCapture):
            def read(self):
                return True, _FakeFrame(1080, 1920)

        with mock.patch.dict(sys.modules, {"cv2": _fake_cv2(BigCapture)}):
            cam = Camera(platform_info=_info("linux"))
            self.assertEqual(cam.read().shape, (480, 640, 3))
            cam.close()

    def test_read_failure_returns_none(self):
        class DeadCapture(_FakeCapture):
            def read(self):
                return False, None

        with mock.patch.dict(sys.modules, {"cv2": _fake_cv2(DeadCapture)}):
            cam = Camera(platform_info=_info("linux"))
            self.assertTrue(cam.is_available)
            self.assertIsNone(cam.read())
            cam.close()

    def test_platform_detection_failure_still_constructs(self):
        with mock.patch.object(camera_mod, "detect_platform", side_effect=RuntimeError("no")), \
                mock.patch.dict(sys.modules, {"cv2": None}):
            cam = Camera()
            self.assertFalse(cam.is_available)


if __name__ == "__main__":
    unittest.main()
