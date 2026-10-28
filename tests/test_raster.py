"""Antialiased drawing through GDI+: frames come out as PNGs Tk can show, with the shapes where they were drawn."""
import tkinter as tk
import unittest

import raster
import theme
import widgets


class Raster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_surface_draws_a_png_tk_can_read(self):
        with raster.Surface(40, 40, "#102030") as surface:
            surface.circle(20, 20, 14, "#FF0000", 3)
            surface.arc(20, 20, 8, 0, 90, "#00FF00", 2)
            png = surface.png()
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        image = tk.PhotoImage(data=png)
        self.assertEqual((image.width(), image.height()), (40, 40))
        self.assertEqual(image.get(2, 2), (16, 32, 48), "the background is the color asked for, red and blue in place")
        red, _, _ = image.get(20, 6)  # on the circle, at the top
        self.assertGreater(red, 200, "the circle is red where it was drawn")
        edge = image.get(20, 4)  # just outside: an antialiased edge, neither background nor pure red
        self.assertNotEqual(edge, (16, 32, 48))
        self.assertNotEqual(edge, (255, 0, 0))
        self.assertEqual(image.get(12, 20), (16, 32, 48), "nothing at 9 o'clock: the arc covers 3 to 6 o'clock only")
        self.assertGreater(image.get(25, 25)[1], 150, "the arc is green between 3 and 6 o'clock")

    def test_ring_image_is_antialiased(self):
        image = theme.ring(44, 0.32, "#2F8CF5", "#34D8A8", "#223B60", "#12294A", 4)
        self.assertEqual((image.width(), image.height()), (44, 44))
        colors = {image.get(x, 3) for x in range(16, 28)}  # across the arc at the top: shades, not two flat colors
        self.assertGreater(len(colors), 3)

    def test_smooth_frame_gives_a_photo_image(self):
        frame = widgets.smooth_frame(30, lambda surface: surface.circle(15, 15, 10, "#FFFFFF", 2), "#000000")
        self.assertIsNotNone(frame)
        self.assertEqual(frame.width(), 30)


if __name__ == "__main__":
    unittest.main()
