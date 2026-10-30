import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

import numpy as np

# spidev is Linux-only; exercise the real encoding with a fake SPI device.
spidev = ModuleType("spidev")
spidev.SpiDev = Mock()
with patch.dict(sys.modules, spidev=spidev):
    import rpi5_ws2812.ws2812 as ws2812
    from rpi5_ws2812.ws2812 import Color, WS2812SpiDriver


class StripTests(unittest.TestCase):
    def setUp(self):
        self.device = Mock()
        self.spi = patch.object(ws2812, "SpiDev", return_value=self.device)
        self.spi.start()
        self.addCleanup(self.spi.stop)

    def test_show_encodes_grb_most_significant_bit_first(self):
        driver = WS2812SpiDriver(0, 0, 2)
        strip = driver.get_strip()
        strip.set_pixel_color(0, Color(128, 64, 2))
        strip.set_pixel_color(1, Color(2, 4, 8))
        strip.set_brightness(0.5)
        strip.show()

        frame = self.device.writebytes2.call_args.args[0]
        expected = [0] * driver.PREAMBLE
        for value in (32, 64, 1, 2, 1, 4):
            expected.extend(driver.LED_ONE if value & (1 << bit) else driver.LED_ZERO for bit in range(7, -1, -1))
        np.testing.assert_array_equal(frame, expected)
        self.device.open.assert_called_once_with(0, 0)
        self.assertEqual(self.device.max_speed_hz, 6_500_000)

    def test_clear_resets_hardware_and_pixel_buffer(self):
        driver = WS2812SpiDriver(0, 0, 2)
        strip = driver.get_strip()
        strip.set_all_pixels(Color(255, 255, 255))
        strip.clear()
        cleared = self.device.writebytes2.call_args.args[0].copy()
        np.testing.assert_array_equal(cleared[:driver.PREAMBLE], 0)
        np.testing.assert_array_equal(cleared[driver.PREAMBLE:], driver.LED_ZERO)
        strip.show()
        np.testing.assert_array_equal(self.device.writebytes2.call_args.args[0], cleared)

    def test_wrong_frame_shape_does_not_write(self):
        driver = WS2812SpiDriver(0, 0, 2)
        for shape in ((1, 3), (6,), (2, 2), (0, 3)):
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                driver.write(np.zeros(shape, dtype=np.uint8))
        self.device.writebytes2.assert_not_called()

    def test_negative_led_count_does_not_open_spi(self):
        with self.assertRaises(ValueError):
            WS2812SpiDriver(0, 0, -1)
        self.device.open.assert_not_called()

    def test_empty_strip_can_show_and_clear(self):
        strip = WS2812SpiDriver(0, 0, 0).get_strip()
        strip.show()
        strip.clear()
        self.assertEqual(strip.num_pixels(), 0)


if __name__ == "__main__":
    unittest.main()
