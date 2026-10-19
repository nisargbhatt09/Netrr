#!/usr/bin/env python3
"""
Netrr environment doctor
========================

Prints a readable report of the host environment so a user can see, before
starting the glasses, what will and will not work:

- Python version and detected platform
- which optional runtime dependencies import
- camera, microphone and speaker availability
- whether the API keys are set

Each check prints one line marked OK, WARN or FAIL. The process exits
non-zero only when a hard failure (FAIL) is found. Heavy modules are
imported inside their own check, never at module import time.
"""

import importlib
import importlib.util
import os
import sys

OK = "OK"
WARN = "WARN"
FAIL = "FAIL"

MIN_PYTHON = (3, 10)


def _line(status, label, detail=""):
    """Format one report line."""
    text = f"[{status:<4}] {label}"
    if detail:
        text += f": {detail}"
    return text


# ---------------------------------------------------------------------------
# Individual checks. Each returns a list of (status, label, detail) tuples.
# ---------------------------------------------------------------------------

def check_python():
    version = "%d.%d.%d" % sys.version_info[:3]
    if sys.version_info[:2] >= MIN_PYTHON:
        return [(OK, "Python", f"{version} ({sys.executable})")]
    return [(FAIL, "Python", f"{version} found, need {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+")]


def check_platform():
    try:
        from netrr.platform import detect_platform
        info = detect_platform()
    except Exception as e:
        return [(WARN, "Platform", f"detection failed: {e}")]
    detail = f"{info.name} ({info.system or 'unknown'}, {info.arch})"
    if info.model:
        detail += f" - {info.model}"
    return [(OK, "Platform", detail)]


def _try_import(module_name):
    """Import a module in isolation and return (ok, detail)."""
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        return False, f"not installed ({e})"
    except Exception as e:  # broken native libs, etc.
        return False, f"import error ({type(e).__name__}: {e})"
    version = getattr(module, "__version__", None)
    return True, f"version {version}" if version else "importable"


def _spec_present(module_name):
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def check_dependencies(platform_info=None):
    """Report which optional runtime dependencies are usable."""
    results = []
    for label, module_name in [
        ("cv2 (OpenCV)", "cv2"),
        ("numpy", "numpy"),
        ("ultralytics", "ultralytics"),
        ("pyaudio", "pyaudio"),
        ("pyttsx3", "pyttsx3"),
        ("google-genai", "google.genai"),
    ]:
        ok, detail = _try_import(module_name)
        results.append((OK if ok else WARN, label, detail))

    # Platform-only packages: only look for them, do not import (they can
    # touch hardware at import time).
    for label, module_name, wanted_on in [
        ("picamera2", "picamera2", "raspberry_pi"),
        ("jetson-stats", "jtop", "jetson"),
    ]:
        present = _spec_present(module_name)
        if present:
            results.append((OK, label, "found"))
        elif platform_info is not None and platform_info.name == wanted_on:
            results.append((WARN, label, f"not found; install with: pip install -e '.[{'pi' if wanted_on == 'raspberry_pi' else 'jetson'}]'"))
        else:
            results.append((OK, label, "not found (not needed on this platform)"))
    return results


def check_face_recognition():
    """Report whether the optional face recognition stack is usable.

    `face_recognition` depends on `dlib`, a native library that is often not
    installed. When it is missing the glasses still start; only the face
    features are disabled. The import happens here, not at module load.
    """
    ok, detail = _try_import("face_recognition")
    if ok:
        return [(OK, "Face recognition", f"face_recognition {detail}")]
    return [(WARN, "Face recognition",
             f"{detail}; requires the dlib and face_recognition packages "
             "(pip install -e '.[face]'). Face features will be disabled")]


def check_opencv_gstreamer(platform_info=None):
    """Report whether the installed OpenCV was built with GStreamer support.

    The Jetson CSI camera is only reachable through a GStreamer pipeline
    (nvarguscamerasrc), so on a Jetson an OpenCV without GStreamer means no
    camera. The pip wheels lack it; the JetPack `python3-opencv` has it.
    Returns an empty list (check skipped) when cv2 cannot be imported, since
    check_dependencies already reports that.
    """
    try:
        import cv2
    except Exception:
        return []

    from netrr.platform import OPENCV_GSTREAMER_FIX, opencv_has_gstreamer

    try:
        build_info = cv2.getBuildInformation()
    except Exception as e:
        return [(WARN, "OpenCV GStreamer", f"could not read cv2 build information ({e})")]

    if opencv_has_gstreamer(build_info):
        return [(OK, "OpenCV GStreamer", "built with GStreamer support")]

    detail = "cv2 is built without GStreamer (pip wheels do not include it)"
    if platform_info is not None and platform_info.is_jetson:
        detail += f"; the Jetson CSI camera needs it. Fix: {OPENCV_GSTREAMER_FIX}"
    else:
        detail += "; only needed for the Jetson CSI camera"
    return [(WARN, "OpenCV GStreamer", detail)]


def check_camera(platform_info=None):
    """Find at least one usable camera backend."""
    if _spec_present("picamera2"):
        return [(OK, "Camera", "picamera2 backend available")]

    try:
        import cv2
    except Exception as e:
        return [(WARN, "Camera", f"no backend: cv2 unavailable ({type(e).__name__})")]

    try:
        cap = cv2.VideoCapture(0)
        opened = cap.isOpened()
        cap.release()
    except Exception as e:
        return [(WARN, "Camera", f"cv2.VideoCapture(0) failed: {e}")]

    if opened:
        return [(OK, "Camera", "cv2.VideoCapture(0) opened")]
    return [(WARN, "Camera", "cv2 present but no camera at index 0")]


def check_audio():
    """Report microphone and speaker availability."""
    results = []
    try:
        import pyaudio
    except Exception as e:
        results.append((WARN, "Audio input", f"pyaudio unavailable ({type(e).__name__})"))
    else:
        inputs = outputs = 0
        try:
            p = pyaudio.PyAudio()
            try:
                for i in range(p.get_device_count()):
                    dev = p.get_device_info_by_index(i)
                    if dev.get('maxInputChannels', 0) > 0:
                        inputs += 1
                    if dev.get('maxOutputChannels', 0) > 0:
                        outputs += 1
            finally:
                p.terminate()
        except Exception as e:
            results.append((WARN, "Audio input", f"pyaudio device scan failed: {e}"))
        else:
            results.append((OK if inputs else WARN, "Audio input",
                            f"{inputs} input device(s)" if inputs else "no input devices found"))
            results.append((OK if outputs else WARN, "Audio output (pyaudio)",
                            f"{outputs} output device(s)" if outputs else "no output devices found"))

    # Speech output: at least one of pyttsx3, edge-tts (+ a player) or espeak.
    tts = []
    if _spec_present("pyttsx3"):
        tts.append("pyttsx3")
    if _spec_present("edge_tts"):
        tts.append("edge-tts")
    import shutil
    players = [p for p in ("mpg123", "ffplay", "aplay", "afplay", "espeak") if shutil.which(p)]
    tts.extend(players)
    if tts:
        results.append((OK, "Audio output (TTS)", ", ".join(tts)))
    else:
        results.append((WARN, "Audio output (TTS)", "no pyttsx3, edge-tts, or player (mpg123/espeak) found"))
    return results


def check_api_keys():
    """Report whether the API keys are set (without printing them)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    results = []
    for key in ("GEMINI_API_KEY", "MOONDREAM_API_KEY"):
        if os.environ.get(key):
            results.append((OK, key, "set"))
        else:
            results.append((WARN, key, "not set (copy .env.example to .env and fill it in)"))
    return results


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run_doctor(stream=None):
    """Run every check, print the report, and return the number of hard failures."""
    stream = stream or sys.stdout
    print("=" * 60, file=stream)
    print("       NETRR ENVIRONMENT DOCTOR", file=stream)
    print("=" * 60, file=stream)

    platform_info = None
    try:
        from netrr.platform import detect_platform
        platform_info = detect_platform()
    except Exception:
        pass

    sections = [
        ("System", check_python() + check_platform()),
        ("Dependencies", check_dependencies(platform_info) + check_face_recognition()),
        ("Camera", check_opencv_gstreamer(platform_info) + check_camera(platform_info)),
        ("Audio", check_audio()),
        ("API keys", check_api_keys()),
    ]

    counts = {OK: 0, WARN: 0, FAIL: 0}
    for title, results in sections:
        print(f"\n--- {title} ---", file=stream)
        for status, label, detail in results:
            counts[status] += 1
            print(_line(status, label, detail), file=stream)

    print("\n" + "-" * 60, file=stream)
    print(f"{counts[OK]} ok, {counts[WARN]} warnings, {counts[FAIL]} failures", file=stream)
    if counts[FAIL]:
        print("Fix the FAIL items above before running `netrr`.", file=stream)
    elif counts[WARN]:
        print("WARN items are optional; the related feature will be disabled or degraded.", file=stream)
    else:
        print("Everything looks good. Run `netrr --mode all` to start.", file=stream)
    return counts[FAIL]


def main():
    """Console entry point for `netrr-doctor`."""
    failures = run_doctor()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
