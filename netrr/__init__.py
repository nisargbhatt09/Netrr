"""Netrr: calibrated, provenance-aware narration for assistive wearables.

The `netrr` package holds the dependency-free research core — grounding grades,
the escalation policy, and evaluation — so it can be imported and tested on any
machine (CI, headless eval) without pulling in OpenCV, Ultralytics, audio, or
camera hardware. The legacy `smart_glasses` package keeps the hardware-coupled
prototype.
"""

__version__ = "0.1.0"
