"""Unit tests for the platform-specific temperature reading in performance_monitor."""

import os
import tempfile
import unittest

from netrr.platform import PlatformInfo

try:
    from smart_glasses.performance_monitor import read_cpu_temperature
    HAVE_PSUTIL = True
except ImportError:  # performance_monitor needs psutil
    HAVE_PSUTIL = False


def _info(name, pi=False, jetson=False):
    return PlatformInfo(name=name, is_raspberry_pi=pi, is_jetson=jetson,
                        arch="x", python_version="3.0.0")


@unittest.skipUnless(HAVE_PSUTIL, "psutil not installed")
class TestReadCpuTemperature(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _zone(self, n, temp, zone_type=None):
        d = os.path.join(self.tmp.name, "thermal_zone%d" % n)
        os.makedirs(d)
        with open(os.path.join(d, "temp"), "w") as f:
            f.write(str(temp))
        if zone_type is not None:
            with open(os.path.join(d, "type"), "w") as f:
                f.write(zone_type + "\n")
        return os.path.join(d, "temp")

    def _glob(self):
        return os.path.join(self.tmp.name, "thermal_zone*", "temp")

    def test_pi_reads_single_zone(self):
        path = self._zone(0, "48234\n")
        self.assertAlmostEqual(read_cpu_temperature(_info("raspberry_pi", pi=True), pi_path=path), 48.234)

    def test_pi_missing_zone_is_none(self):
        self.assertIsNone(read_cpu_temperature(_info("raspberry_pi", pi=True),
                                               pi_path=os.path.join(self.tmp.name, "nope")))

    def test_jetson_prefers_cpu_zone(self):
        self._zone(0, "41000", "AO-therm")
        self._zone(1, "52500", "CPU-therm")
        self._zone(2, "60000", "GPU-therm")
        self.assertAlmostEqual(read_cpu_temperature(_info("jetson", jetson=True), jetson_glob=self._glob()), 52.5)

    def test_jetson_falls_back_to_first_sane_zone(self):
        self._zone(0, "-256000", "PMIC-Die")  # disconnected sensor
        self._zone(1, "39000", "GPU-therm")
        self.assertAlmostEqual(read_cpu_temperature(_info("jetson", jetson=True), jetson_glob=self._glob()), 39.0)

    def test_jetson_without_zones_is_none(self):
        self.assertIsNone(read_cpu_temperature(_info("jetson", jetson=True), jetson_glob=self._glob()))

    def test_other_platforms_are_none(self):
        path = self._zone(0, "48000")
        for name in ("linux", "macos", "windows", "unknown"):
            self.assertIsNone(read_cpu_temperature(_info(name), pi_path=path, jetson_glob=self._glob()), name)


if __name__ == "__main__":
    unittest.main()
