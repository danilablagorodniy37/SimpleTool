"""Antialiased widgets: rounded shapes drawn through GDI+ into cached images, with the canvas as the fallback."""
import tkinter as tk
import types
import unittest
from unittest import mock

import raster
import theme
import widgets
from theme import C


def layout(card, width, height):
    """What Tk does when the card gets its size (the hidden test window gets no Configure events)."""
    card._layout(types.SimpleNamespace(width=width, height=height))


class Shapes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()
        cls.animator = widgets.Animator(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.animator.stop()
        cls.root.destroy()
        theme.clear_cache()

    def setUp(self):
        theme.clear_cache()
        self.frame = tk.Frame(self.root, bg=C["bg"])
        self.frame.pack()

    def tearDown(self):
        self.frame.destroy()

    def test_rounded_rectangle_is_transparent_outside_and_soft_at_the_corner(self):
        with raster.Surface(30, 20, None) as surface:
            surface.round_rect(0, 0, 30, 20, 8, "#102030", "#4080C0", 1.0)
            surface.fill_circle(15, 10, 3, "#FFFFFF")
            image = tk.PhotoImage(data=surface.png())
        self.assertTrue(image.transparency_get(0, 0), "outside the corner nothing is drawn")
        self.assertFalse(image.transparency_get(15, 0))
        self.assertEqual(image.get(15, 0), (64, 128, 192), "the border, one pixel on the straight edge")
        self.assertEqual(image.get(5, 10), (16, 32, 48), "the fill inside, red and blue in place")
        self.assertEqual(image.get(15, 10), (255, 255, 255), "the circle")
        corner = image.get(2, 2)
        self.assertNotIn(corner, ((64, 128, 192), (16, 32, 48)), "an antialiased edge at the corner")

    def test_polyline(self):
        with raster.Surface(20, 20, "#000000") as surface:
            surface.polyline([(3, 10), (8, 15), (17, 4)], "#FFFFFF", 2.5)
            image = tk.PhotoImage(data=surface.png())
        self.assertGreater(image.get(8, 14)[0], 150)
        self.assertEqual(image.get(18, 18), (0, 0, 0))

    def test_quantize(self):
        self.assertEqual(widgets.quantize("#2A4670"), "#284870")
        self.assertEqual(widgets.quantize("#FFFFFF"), "#FFFFFF")
        self.assertEqual(widgets.quantize("#FEFDFC"), "#FFFCFC", "a channel never goes past 255")

    def test_card_corners_and_edges(self):
        card = widgets.Card(self.frame, 1.0, radius=12, pad=6)
        width, height = 212, 72
        layout(card, width, height)
        canvas = card.backdrop
        self.assertEqual(canvas.itemcget(card.shape, "state"), "hidden", "the jagged polygon is not used")
        self.assertTrue(all(canvas.itemcget(item, "image") for item in card.corners))
        self.assertTrue(all(canvas.itemcget(item, "fill") == widgets.quantize(C["border"]) for item in card.edges))
        card.set_border(C["primary"])
        self.assertEqual(card.border, C["primary"])
        self.assertEqual(canvas.itemcget(card.edges[0], "fill"), widgets.quantize(C["primary"]))
        # The corners meet the edges: the top right corner ends where the right edge and the shape end
        x, y = canvas.coords(card.corners[1])
        self.assertEqual((x + 12, y), (width - 1, 1))
        self.assertEqual(canvas.coords(card.edges[3])[0], width - 2)
        self.assertEqual(canvas.coords(card.edges[1])[1], height - 2)
        card.set_accent(C["ok"])
        self.assertEqual(canvas.itemcget(card.accent_image, "state"), "normal")
        card.set_accent(None)
        self.assertEqual(canvas.itemcget(card.accent_image, "state"), "hidden")

    def test_without_gdiplus_the_canvas_draws(self):
        with mock.patch.object(widgets, "_gdiplus", [False]):
            card = widgets.Card(self.frame, 1.0)
            layout(card, 112, 52)
            toggle = widgets.Toggle(self.frame, 1.0, self.animator, on=True)
            pill = widgets.Pill(self.frame, ("Segoe UI", 9), 1.0, self.animator)
            pill.set("On", C["ok"], animate=False)
            box = widgets.CheckBox(self.frame, 20, self.animator)
            box.set(True, True, animate=False)
            self.root.update()
            self.assertEqual(card.backdrop.itemcget(card.shape, "state"), "normal")
            self.assertEqual(card.backdrop.itemcget(card.corners[0], "state"), "hidden")
            self.assertEqual(toggle.itemcget(toggle.track, "state"), "normal")
            self.assertEqual(pill.itemcget(pill.shape, "state"), "normal")
            self.assertEqual([box.type(item) for item in box.find_all()], ["polygon", "line"])

    def test_widgets_draw_images_and_keep_their_api(self):
        toggle = widgets.Toggle(self.frame, 1.25, self.animator, on=False)
        self.assertEqual(toggle.itemcget(toggle.image, "state"), "normal")
        changes = []
        toggle.command = changes.append
        toggle._click(None)
        self.assertTrue(toggle.on)
        self.assertEqual(changes, [True])
        toggle.set(True, animate=False)
        self.assertEqual(toggle.pos, 1.0)
        pill = widgets.Pill(self.frame, ("Segoe UI", 9), 1.25, self.animator)
        pill.set("Applied", C["ok"], animate=False)
        self.assertEqual(pill.itemcget(pill.label, "text"), "Applied")
        self.assertEqual(pill.itemcget(pill.plate, "state"), "normal")
        box = widgets.CheckBox(self.frame, 25, self.animator)
        box.set(True, True, animate=False)
        self.assertEqual([box.type(item) for item in box.find_all()], ["image"])
        segments = widgets.Segmented(self.frame, [("a", "Name"), ("b", "Size")], "a", ("Segoe UI", 9, "bold"),
                                     1.25, self.animator)
        self.assertEqual(segments.itemcget(segments.thumb_image, "state"), "normal")
        self.assertEqual(segments.itemcget(segments.thumb, "state"), "hidden")

    def test_animated_colors_reuse_a_bounded_cache(self):
        card = widgets.Card(self.frame, 1.0)
        layout(card, 112, 52)
        for i in range(60):  # a border fading in, as when a page opens
            card.set_border(theme.lerp(C["bg"], C["border"], i / 59))
        corners = [key for key in theme._cache if key[0] == "aa_corners"]
        self.assertLess(len(corners), 30, "quantized colors share images")
        with mock.patch.object(widgets, "SHAPES_KEPT", 10):
            for i in range(40):
                widgets.bar_image(self.frame, 50 + i, 6, C["primary"])
            self.assertLessEqual(len([key for key in theme._cache if key[0] in ("aa", "aa_corners")]), 10)


if __name__ == "__main__":
    unittest.main()
