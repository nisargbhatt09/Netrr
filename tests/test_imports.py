"""Verify the dependency-free `netrr` package imports and exposes its API.

This replaces the old import smoke test, which imported the hardware-coupled
`smart_glasses` package and could only print checkmarks, not assert anything.
"""

import unittest

import netrr
from netrr.ground.claims import Claim, choose_action, get_grid_position


class TestPackageImport(unittest.TestCase):
    def test_version_is_a_string(self):
        self.assertIsInstance(netrr.__version__, str)

    def test_public_api_is_callable(self):
        self.assertTrue(callable(get_grid_position))
        self.assertTrue(callable(choose_action))
        self.assertTrue(callable(Claim))


if __name__ == "__main__":
    unittest.main()
