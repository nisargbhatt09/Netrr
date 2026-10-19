"""Platform-aware camera capture.

`Camera` picks a capture backend from `netrr.platform` and drives it behind a
tiny uniform interface (`is_available`, `backend`, `read()`, `close()`):

* Raspberry Pi: picamera2.
* NVIDIA Jetson: OpenCV reading a GStreamer pipeline built on
  `nvarguscamerasrc` and `nvvidconv` (a plain `cv2.VideoCapture(0)` cannot
  open the CSI camera on a Jetson).
* Everywhere else: a plain `cv2.VideoCapture(index)`.

Every import and open call is guarded so that a failure falls through to the
next backend. If nothing works the camera simply reports `is_available` as
False and `read()` returns None. Constructing a `Camera` never raises.

OpenCV and picamera2 are imported lazily, inside the backends, so this
module can be imported (and unit tested) on a machine without either.
"""

import logging

from netrr.platform import (
    CAMERA_BACKEND_JETSON_GSTREAMER,
    CAMERA_BACKEND_OPENCV,
    CAMERA_BACKEND_PICAMERA2,
    camera_backend_for,
    detect_platform,
)

logger = logging.getLogger(__name__)

DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480

# Sensor mode requested from the Jetson CSI camera before nvvidconv scales it
# down to the output size. 1280x720 is supported by every common Jetson
# camera module (IMX219, IMX477, ...).
JETSON_SENSOR_WIDTH = 1280
JETSON_SENSOR_HEIGHT = 720
JETSON_FRAMERATE = 30


def jetson_gstreamer_pipeline(width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT,
                              sensor_id=0, framerate=JETSON_FRAMERATE,
                              flip_method=0, sensor_width=JETSON_SENSOR_WIDTH,
                              sensor_height=JETSON_SENSOR_HEIGHT):
    """Return the GStreamer pipeline string used to read a Jetson CSI camera.

    Pure: it only formats a string, so it is safe to call anywhere.
    """
    return (
        "nvarguscamerasrc sensor-id=%d ! "
        "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, "
        "format=(string)NV12, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! video/x-raw, format=(string)BGR ! "
        "appsink drop=true max-buffers=1"
        % (sensor_id, sensor_width, sensor_height, framerate, flip_method,
           width, height)
    )


def _import_cv2():
    """Import OpenCV lazily; return None if it is not installed."""
    try:
        import cv2
    except Exception as e:  # ImportError, or a broken native build
        logger.warning("OpenCV not available: %s", e)
        return None
    return cv2


class _Picamera2Backend:
    """Raspberry Pi camera via picamera2."""

    name = CAMERA_BACKEND_PICAMERA2

    def __init__(self, width, height, index):
        from picamera2 import Picamera2  # guarded by Camera._open_backend

        self._picam = Picamera2(index)
        self._picam.preview_configuration.main.size = (width, height)
        self._picam.preview_configuration.main.format = "RGB888"
        self._picam.preview_configuration.align()
        self._picam.configure("preview")
        self._picam.start()

    def read(self):
        return self._picam.capture_array()

    def close(self):
        self._picam.stop()


class _OpenCVBackend:
    """Any source cv2.VideoCapture can open: a device index or a pipeline."""

    name = CAMERA_BACKEND_OPENCV

    def __init__(self, width, height, index):
        cv2 = _import_cv2()
        if cv2 is None:
            raise RuntimeError("OpenCV is not installed")
        self._capture = cv2.VideoCapture(index)
        if not self._capture.isOpened():
            self._release()
            raise RuntimeError("cv2.VideoCapture(%r) could not be opened" % (index,))
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def read(self):
        ok, frame = self._capture.read()
        if not ok:
            return None
        return frame

    def _release(self):
        try:
            self._capture.release()
        except Exception as e:
            logger.debug("Error releasing capture: %s", e)

    def close(self):
        self._release()


class _JetsonGStreamerBackend(_OpenCVBackend):
    """Jetson CSI camera through nvarguscamerasrc, read with OpenCV."""

    name = CAMERA_BACKEND_JETSON_GSTREAMER

    def __init__(self, width, height, index):
        cv2 = _import_cv2()
        if cv2 is None:
            raise RuntimeError("OpenCV is not installed")
        pipeline = jetson_gstreamer_pipeline(width, height, sensor_id=index)
        self._capture = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not self._capture.isOpened():
            self._release()
            raise RuntimeError("GStreamer pipeline could not be opened "
                               "(is OpenCV built with GStreamer support?)")


_BACKENDS = {
    CAMERA_BACKEND_PICAMERA2: _Picamera2Backend,
    CAMERA_BACKEND_JETSON_GSTREAMER: _JetsonGStreamerBackend,
    CAMERA_BACKEND_OPENCV: _OpenCVBackend,
}


def backend_order_for(info):
    """Backends to try, in order, for a platform: the preferred one then OpenCV."""
    order = [camera_backend_for(info)]
    if CAMERA_BACKEND_OPENCV not in order:
        order.append(CAMERA_BACKEND_OPENCV)
    return order


class Camera:
    """A camera that opens the right backend for the host, or no backend at all."""

    def __init__(self, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, index=0,
                 platform_info=None, backends=None):
        """Open the first working backend. Never raises.

        Args:
            width, height: output frame size; frames are resized to it.
            index: camera index (device number, or Jetson sensor-id).
            platform_info: a PlatformInfo; detected live when None.
            backends: explicit list of backend names to try, in order.
                Defaults to the platform's preferred backend then "opencv".
        """
        self.width = width
        self.height = height
        self.index = index
        self.backend = None
        self._backend = None

        try:
            if platform_info is None:
                platform_info = detect_platform()
            self.platform_info = platform_info
            if backends is None:
                backends = backend_order_for(platform_info)
        except Exception as e:
            logger.error("Platform detection failed: %s", e)
            self.platform_info = platform_info
            backends = [CAMERA_BACKEND_OPENCV]

        for name in backends:
            backend = self._open_backend(name)
            if backend is not None:
                self._backend = backend
                self.backend = backend.name
                logger.info("Camera initialised with %s backend at %dx%d",
                            self.backend, width, height)
                break
        else:
            logger.warning("No camera backend could be opened (tried: %s)",
                           ", ".join(backends))

    def _open_backend(self, name):
        cls = _BACKENDS.get(name)
        if cls is None:
            logger.warning("Unknown camera backend %r, skipping", name)
            return None
        try:
            return cls(self.width, self.height, self.index)
        except Exception as e:  # ImportError, RuntimeError, driver errors...
            logger.warning("Camera backend %s failed: %s", name, e)
            return None

    @property
    def is_available(self):
        return self._backend is not None

    def read(self):
        """Return the next frame as a numpy array, or None if unavailable."""
        if self._backend is None:
            return None
        try:
            frame = self._backend.read()
        except Exception as e:
            logger.warning("Camera read failed (%s): %s", self.backend, e)
            return None
        if frame is None:
            return None
        return self._fit(frame)

    def _fit(self, frame):
        """Resize `frame` to the configured size if the backend ignored it."""
        shape = getattr(frame, "shape", None)
        if not shape or len(shape) < 2:
            return frame
        if shape[0] == self.height and shape[1] == self.width:
            return frame
        cv2 = _import_cv2()
        if cv2 is None:
            return frame
        try:
            return cv2.resize(frame, (self.width, self.height))
        except Exception as e:
            logger.debug("Frame resize failed: %s", e)
            return frame

    def close(self):
        """Release the backend. Safe to call repeatedly or when unavailable."""
        backend, self._backend = self._backend, None
        if backend is None:
            return
        try:
            backend.close()
        except Exception as e:
            logger.warning("Error closing camera backend %s: %s", self.backend, e)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
