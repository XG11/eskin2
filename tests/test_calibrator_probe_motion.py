import unittest
import numpy as np

from tactile_calibration.Calibrator import Calibrator


class DummyPrinter:
    def __init__(self):
        self.commands = []

    def send_gcode(self, command):
        self.commands.append(command)


class DummySensor:
    name = "dummy"
    z_offset = 0.0
    z_clearance = 5.0
    x_offset = 0.0
    y_offset = 0.0
    max_penetration = 10.0


class CalibratorProbeMotionTests(unittest.TestCase):
    def test_safe_read_chunk_caps_large_requests(self):
        calibrator = Calibrator(DummyPrinter(), DummySensor(), DummySensor(), DummySensor())
        self.assertEqual(calibrator.get_safe_read_chunk(3000, 500), 150)

    def test_build_time_axis_uses_sample_rate(self):
        calibrator = Calibrator(DummyPrinter(), DummySensor(), DummySensor(), DummySensor())
        axis = calibrator.build_time_axis(5, 10)
        np.testing.assert_allclose(axis, np.array([0.0, 0.1, 0.2, 0.3, 0.4]))


if __name__ == "__main__":
    unittest.main()
