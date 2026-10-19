"""Unit tests for the dependency-free grounding core (plan v2 section 4)."""

import unittest

from netrr.ground.claims import (
    Claim,
    choose_action,
    get_grid_position,
    grade_presence,
    grade_spatial,
)


class TestGridPosition(unittest.TestCase):
    def setUp(self):
        self.w, self.h = 300, 300

    def test_center(self):
        self.assertEqual(get_grid_position(150, 150, self.w, self.h), "center")

    def test_corners(self):
        self.assertEqual(get_grid_position(10, 10, self.w, self.h), "upper left")
        self.assertEqual(get_grid_position(290, 10, self.w, self.h), "upper right")
        self.assertEqual(get_grid_position(10, 290, self.w, self.h), "lower left")
        self.assertEqual(get_grid_position(290, 290, self.w, self.h), "lower right")

    def test_edges(self):
        self.assertEqual(get_grid_position(150, 10, self.w, self.h), "upper center")
        self.assertEqual(get_grid_position(150, 290, self.w, self.h), "lower center")
        self.assertEqual(get_grid_position(10, 150, self.w, self.h), "middle left")
        self.assertEqual(get_grid_position(290, 150, self.w, self.h), "middle right")


class TestPresenceGrading(unittest.TestCase):
    def test_supported(self):
        self.assertEqual(
            grade_presence("chair", ["chair", "table"], [0.9, 0.8]), "supported"
        )

    def test_low_confidence_is_uncertain(self):
        self.assertEqual(grade_presence("chair", ["chair"], [0.3]), "uncertain")

    def test_absent_is_unsupported(self):
        self.assertEqual(
            grade_presence("dog", ["chair", "table"], [0.9, 0.8]), "unsupported"
        )


class TestSpatialGrading(unittest.TestCase):
    def test_match_is_supported(self):
        self.assertEqual(grade_spatial("center", (150, 150), 300, 300), "supported")

    def test_mismatch_is_unsupported(self):
        self.assertEqual(grade_spatial("center", (10, 10), 300, 300), "unsupported")


class TestEscalationPolicy(unittest.TestCase):
    def test_state_when_supported(self):
        self.assertEqual(choose_action("supported", "dangerous"), "state")

    def test_hedge_when_uncertain_cosmetic(self):
        self.assertEqual(choose_action("uncertain", "cosmetic"), "hedge")

    def test_hedge_reconfirm_when_uncertain_dangerous(self):
        self.assertEqual(choose_action("uncertain", "dangerous"), "hedge_reconfirm")

    def test_abstain_when_unsupported_cosmetic(self):
        self.assertEqual(choose_action("unsupported", "cosmetic"), "abstain")

    def test_abstain_retake_when_unsupported_dangerous(self):
        self.assertEqual(choose_action("unsupported", "dangerous"), "abstain_retake")

    def test_fallback_when_dangerous_and_verifier_down(self):
        self.assertEqual(
            choose_action("supported", "dangerous", verifier_available=False),
            "fallback_detector_only",
        )

    def test_ungraded_is_conservative(self):
        self.assertEqual(choose_action("ungraded", "unknown"), "abstain")


class TestClaim(unittest.TestCase):
    def test_defaults(self):
        c = Claim(text="a chair to your left", kind="presence")
        self.assertEqual(c.grade, "ungraded")
        self.assertEqual(c.harm, "unknown")
        self.assertEqual(c.evidence, [])

    def test_rejects_bad_kind(self):
        with self.assertRaises(ValueError):
            Claim(text="x", kind="nonsense")

    def test_rejects_bad_grade(self):
        with self.assertRaises(ValueError):
            Claim(text="x", kind="presence", grade="definitely")


if __name__ == "__main__":
    unittest.main()
