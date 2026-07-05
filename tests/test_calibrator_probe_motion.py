import unittest

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


if __name__ == "__main__":
    unittest.main()
