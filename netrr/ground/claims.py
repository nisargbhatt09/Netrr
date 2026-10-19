"""Claim, grounding grades, and the escalation policy for Netrr.

This module is intentionally stdlib-only so it can be imported and unit-tested
on any machine without OpenCV, Ultralytics, audio, or camera hardware. It is the
single source of truth for the research vocabulary in plan v2, section 4:

    Claim (text, kind, subject, evidence, grade, harm)
    -> grade from evidence already computed (presence / spatial / ...)
    -> choose_action(grade, harm) -> state / hedge / abstain / retake
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# --- Vocabulary (single source of truth) ---

CLAIM_KINDS = ("presence", "attribute", "spatial", "distance", "count", "text", "identity")
GRADES = ("supported", "uncertain", "unsupported")
HARMS = ("dangerous", "inconvenient", "cosmetic")


# --- The unit of analysis ---


@dataclass
class Claim:
    text: str
    kind: str
    subject: str = ""
    evidence: List[str] = field(default_factory=list)
    grade: str = "ungraded"
    harm: str = "unknown"

    def __post_init__(self):
        if self.kind not in CLAIM_KINDS:
            raise ValueError(f"unknown claim kind: {self.kind!r}")
        if self.grade not in ("ungraded",) + GRADES:
            raise ValueError(f"unknown grade: {self.grade!r}")
        if self.harm not in ("unknown",) + HARMS:
            raise ValueError(f"unknown harm: {self.harm!r}")


# --- Grid position (pure; mirrors smart_glasses.base.get_grid_position) ---


def get_grid_position(x, y, frame_width, frame_height):
    """Return the 3x3 grid cell containing point (x, y)."""
    if x < frame_width / 3:
        if y < frame_height / 3:
            return "upper left"
        if y < 2 * frame_height / 3:
            return "middle left"
        return "lower left"
    if x < 2 * frame_width / 3:
        if y < frame_height / 3:
            return "upper center"
        if y < 2 * frame_height / 3:
            return "center"
        return "lower center"
    if y < frame_height / 3:
        return "upper right"
    if y < 2 * frame_height / 3:
        return "middle right"
    return "lower right"


# --- Grading rules (cheap, from evidence already computed) ---


def grade_presence(subject, detected_subjects, confidences, conf_threshold=0.5):
    """Presence claim: supported iff a detection of `subject` exceeds threshold."""
    if subject in detected_subjects:
        idx = detected_subjects.index(subject)
        if confidences[idx] >= conf_threshold:
            return "supported"
        return "uncertain"
    return "unsupported"


def grade_spatial(claimed_position, box_center, frame_width, frame_height):
    """Spatial claim: supported iff the claimed grid cell matches the box's cell."""
    actual = get_grid_position(box_center[0], box_center[1], frame_width, frame_height)
    return "supported" if claimed_position == actual else "unsupported"


# --- Escalation policy (DKP vocabulary: state / hedge / abstain / retake) ---


def choose_action(grade, harm, verifier_available=True):
    """Map (grade, harm) to a speaking action, per plan v2 section 4."""
    if harm == "dangerous" and not verifier_available:
        # Without a verifier we cannot vouch for any claim about a hazard.
        return "fallback_detector_only"
    if grade == "supported":
        return "state"
    if grade == "uncertain":
        return "hedge_reconfirm" if harm == "dangerous" else "hedge"
    if grade == "unsupported":
        return "abstain_retake" if harm == "dangerous" else "abstain"
    # Ungraded / unknown: be conservative.
    return "abstain"
