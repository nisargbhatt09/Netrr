"""
Smart Glasses System for Visually Impaired
=========================================

An assistive technology system using AI-powered computer vision, voice recognition,
and natural language processing to help visually impaired users navigate and understand
their environment.

Features:
- Object detection (using YOLOE or YOLO)
- Face recognition and identification
- Text recognition and reading
- Scene analysis and description
- Voice command interface
- Currency recognition
- Color identification

Requirements:
- Python 3.10+
- OpenCV
- Ultralytics YOLO/YOLOE
- Speech recognition
- Text-to-speech (pyttsx3 or espeak)
- Various ML models (see documentation)

Importing this package is cheap: the heavy modules (OpenCV, PyAudio,
Ultralytics, google-genai, ...) are only imported when a submodule or
`main` is actually used.
"""

import importlib

__version__ = "0.2.0"

# Public names resolved lazily on first access (PEP 562).
_LAZY_ATTRS = {
    'SmartGlasses': '.base',
    'ObjectDetector': '.object_detection',
    'TextReader': '.text_recognition',
    'FaceRecognizer': '.face_recognition',
    'SceneAnalyzer': '.scene_analyzer',
    'VoiceAssistant': '.voice_assistant',
    'main': '.main',
}

__all__ = [
    'SmartGlasses',
    'ObjectDetector',
    'TextReader',
    'FaceRecognizer',
    'SceneAnalyzer',
    'VoiceAssistant',
    'main'
]


def __getattr__(name):
    """Import the submodule that provides `name` only when it is first requested."""
    module_name = _LAZY_ATTRS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
