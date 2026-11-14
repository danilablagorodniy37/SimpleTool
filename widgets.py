"""Animated UI elements: cards, pills, buttons, checkboxes, indicators and notifications.

Tk's canvas draws rounded shapes jagged, so cards, pills, switches, check boxes, the segmented control and the
bars are drawn antialiased through GDI+ (raster.py) into small images with soft, partly transparent edges. The
images are cached: a color that animates is rounded to a few steps first (quantize), so an animation reuses the
images of the frames before it. Without GDI+ the canvas draws the shapes itself, as it did before.
"""
import collections
import math
import time
import tkinter as tk
import tkinter.font as tkfont

import raster
import theme
from theme import C, lerp, mix


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return t * t * (3 - 2 * t)


class Animator:
    """Frame animations on root.after (~60 frames per second). A new animation with the same key replaces
    the old one."""

    def __init__(self, root):
        self.root = root
        self.tweens = {}
        self.running = False
        self.job = None

    def animate(self, key, duration, step, done=None, ease=ease_out, delay=0.0):
        start = time.perf_counter() + delay
        self.tweens[key] = (start, duration, step, done, ease)
        if not self.running:
            self.running = True
            self.job = self.root.after(0, self._tick)

    def stop(self):
        """The window is closing: cancel the next frame, otherwise Tk calls it after the window is gone."""
        self.tweens.clear()
        if self.job:
            try:
                self.root.after_cancel(self.job)
            except tk.TclError:
                pass
        self.running = False

    def color(self, key, apply, start, end, duration=0.18, delay=0.0):
        self.animate(key, duration, lambda t: apply(lerp(start, end, t)), delay=delay)

    def cancel(self, key):
        self.tweens.pop(key, None)

    def _tick(self):
        now = time.perf_counter()
        for key, tween in list(self.tweens.items()):
            start, duration, step, done, ease = tween
            if now < start:
                continue
            t = 1.0 if duration <= 0 else min(1.0, (now - start) / duration)
            try:
                step(ease(t))
                if t >= 1.0 and self.tweens.get(key) is tween:
                    del self.tweens[key]
                    if done:
                        done()
            except tk.TclError:  # the widget is already deleted, so the animation is no longer needed
                self.tweens.pop(key, None)
        try:
            if self.tweens:
                self.job = self.root.after(15, self._tick)
            else:
                self.running = False
        except tk.TclError:
            self.running = False


SHAPES_KEPT = 1500  # antialiased shape images kept in the cache; the oldest go first
_shapes = collections.OrderedDict()  # cache keys of the shape images in theme._cache, oldest first
_gdiplus = [True]  # False after GDI+ failed once: the canvas draws from then on


def quantize(color, step=4):
    """A color with its channels rounded to steps: an animated color then needs only a few cached images, and the
    difference cannot be seen."""
    return "#%02X%02X%02X" % tuple(min(255, round(v / step) * step) for v in theme.rgb(color))


def _cached(key, make):
    """theme._cache[key], made by make() when it is not there; None if GDI+ or Tk cannot make it."""
    value = theme._cache.get(key)
    if value is not None:
        return value
    if not _gdiplus[0]:
        return None
    try:
        value = make()
    except OSError:
        _gdiplus[0] = False
        return None
    except tk.TclError:
        return None
    theme._cache[key] = value
    _shapes[key] = True
    while len(_shapes) > SHAPES_KEPT:
        theme._cache.pop(_shapes.popitem(last=False)[0], None)
    return value


def shape_image(widget, key, width, height, draw):
    """An antialiased PhotoImage of width x height with a transparent background, drawn by draw(surface) and
    cached under key (which must name everything the drawing depends on); None without GDI+."""
    width, height = max(int(width), 1), max(int(height), 1)

    def make():
        with raster.Surface(width, height, None) as surface:
            draw(surface)
            return tk.PhotoImage(master=widget, data=surface.png())

    # Images belong to one Tk interpreter: a window opened later (the tests open many) gets its own
    return _cached(("aa", id(widget.tk), width, height) + tuple(key), make)


def corner_images(widget, radius, fill, border):
    """The four corners (top left, top right, bottom left, bottom right) of a rounded card with a 1 px border, each
    radius x radius, antialiased and transparent outside; None without GDI+. The straight edges between them are
    one pixel of the border color, so canvas lines and rectangles continue them without a seam."""
    size = 2 * radius + 1

    def make():
        with raster.Surface(size, size, None) as surface:
            surface.round_rect(0, 0, size, size, radius, fill, border, 1.0)
            whole = tk.PhotoImage(master=widget, data=surface.png())
        parts = []
        for x, y in ((0, 0), (radius + 1, 0), (0, radius + 1), (radius + 1, radius + 1)):
            part = tk.PhotoImage(master=widget, width=radius, height=radius)
            part.tk.call(part, "copy", whole, "-from", x, y, x + radius, y + radius)
            parts.append(part)
        return parts

    return _cached(("aa_corners", id(widget.tk), radius, fill, border), make)


def round_points(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def fade_in(animator, key, widgets, delay=0.0, duration=0.32):
    """Fades text in: label colors go smoothly from the background color to their own."""
    items = []
    for widget in widgets:
        if isinstance(widget, tk.Label) and not widget.cget("image"):
            fg, bg = widget.cget("fg"), widget.cget("bg")
            if fg != bg:
                items.append((widget, fg, bg))
                widget.configure(fg=bg)

    def step(t):
        for widget, fg, bg in items:
            widget.configure(fg=lerp(bg, fg, t))

    animator.animate(key, duration, step, delay=delay)


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class Card(tk.Frame):
    """A card with rounded corners. The content (the body frame) sets the size, and the rounded background
    is drawn on a backdrop canvas stretched under the whole card."""

    def __init__(self, parent, scale, fill=None, border=None, radius=12, pad=6):
        self.fill = fill or C["surface"]
        self.border = border or C["border"]
        super().__init__(parent, bg=parent.cget("bg"))
        self.radius, self.pad = radius * scale, max(2, round(pad * scale))
        self.backdrop = tk.Canvas(self, bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.backdrop.place(x=0, y=0, relwidth=1, relheight=1)
        canvas = self.backdrop
        # Without GDI+: one smoothed polygon. With it: the inside and the straight edges as rectangles and lines,
        # and the four corners as antialiased images
        self.shape = canvas.create_polygon(0, 0, 0, 0, smooth=True, fill=self.fill, outline=self.border, width=1)
        self.fills = [canvas.create_rectangle(0, 0, 0, 0, fill=self.fill, outline="", state="hidden") for _ in "ab"]
        self.edges = [canvas.create_line(0, 0, 0, 0, fill=self.border, state="hidden") for _ in "tblr"]
        self.corners = [canvas.create_image(0, 0, anchor="nw", state="hidden") for _ in "1234"]
        # A thin colored bar along the left edge: the status of a tweak, the severity of a finding
        self.bar = max(2, round(3 * scale))
        self.accent = canvas.create_polygon(0, 0, 0, 0, smooth=True, outline="", state="hidden")
        self.accent_image = canvas.create_image(0, 0, anchor="nw", state="hidden")
        self.accent_color = None
        self.size = None
        self.smooth_radius = None  # the corner size the antialiased shape was drawn with, None when it is not
        self.body = tk.Frame(self, bg=self.fill)
        self.body.pack(fill="both", expand=True, padx=self.pad, pady=self.pad)
        self.bind("<Configure>", self._layout)

    def _layout(self, event):
        self.size = (event.width, event.height)
        self._draw_shape()
        self._draw_accent()

    def _draw_shape(self):
        if not self.size:
            return
        width, height = self.size
        canvas = self.backdrop
        x0, y0, x1, y1 = 1, 1, width - 1, height - 1
        r = min(round(self.radius), (x1 - x0) // 2, (y1 - y0) // 2)
        border = quantize(self.border)
        corners = corner_images(canvas, r, self.fill, border) if r >= 2 else None
        smooth = "normal" if corners else "hidden"
        self.smooth_radius = r if corners else None
        canvas.itemconfigure(self.shape, state="hidden" if corners else "normal")
        for item in self.fills + self.edges + self.corners:
            canvas.itemconfigure(item, state=smooth)
        if not corners:
            canvas.coords(self.shape, *round_points(1, 1, width - 2, height - 2, self.radius))
            canvas.itemconfigure(self.shape, outline=self.border)
            return
        # A canvas rectangle fills up to its right and bottom edge, without them, and so does a line of 1 px
        canvas.coords(self.fills[0], x0 + r, y0, x1 - r, y1)
        canvas.coords(self.fills[1], x0, y0 + r, x1, y1 - r)
        for item, points in zip(self.edges, ((x0 + r, y0, x1 - r, y0), (x0 + r, y1 - 1, x1 - r, y1 - 1),
                                             (x0, y0 + r, x0, y1 - r), (x1 - 1, y0 + r, x1 - 1, y1 - r))):
            canvas.coords(item, *points)
            canvas.itemconfigure(item, fill=border)
        for item, image, place in zip(self.corners, corners, ((x0, y0), (x1 - r, y0), (x0, y1 - r), (x1 - r, y1 - r))):
            canvas.coords(item, *place)
            canvas.itemconfigure(item, image=image)

    def _draw_accent(self):
        canvas, color = self.backdrop, self.accent_color
        if not color or not self.size:
            canvas.itemconfigure(self.accent, state="hidden")
            canvas.itemconfigure(self.accent_image, state="hidden")
            return
        top = round(max(self.radius, self.bar))
        length = self.size[1] - 2 * top
        bar = self.bar
        image = shape_image(canvas, ("bar", quantize(color)), bar, length,
                            lambda surface: surface.round_rect(0, 0, bar, length, bar / 2, fill=quantize(color))) \
            if length > bar else None
        if image:
            canvas.coords(self.accent_image, 2, top)
            canvas.itemconfigure(self.accent_image, image=image, state="normal")
            canvas.itemconfigure(self.accent, state="hidden")
        else:
            canvas.coords(self.accent, *round_points(2, top, 2 + bar, self.size[1] - top, bar / 2))
            canvas.itemconfigure(self.accent, fill=color, state="normal")
            canvas.itemconfigure(self.accent_image, state="hidden")

    def set_border(self, color):
        """Called on every frame of a border animation: only the colors change, not the layout."""
        self.border = color
        corners = corner_images(self.backdrop, self.smooth_radius, self.fill, quantize(color))             if self.smooth_radius else None
        if not corners:
            self._draw_shape()
            return
        for item in self.edges:
            self.backdrop.itemconfigure(item, fill=quantize(color))
        for item, image in zip(self.corners, corners):
            self.backdrop.itemconfigure(item, image=image)

    def set_accent(self, color):
        """Shows the bar along the left edge in color, or hides it with None."""
        self.accent_color = color or None
        self._draw_accent()


class Pill(tk.Canvas):
    """A status pill with rounded ends; color changes are animated."""

    def __init__(self, parent, font, scale, animator):
        self.bg = parent.cget("bg")
        super().__init__(parent, bg=self.bg, highlightthickness=0, bd=0, width=1, height=1)
        self.font, self.scale, self.animator = tkfont.Font(font=font), scale, animator
        self.shape = self.create_polygon(0, 0, 0, 0, smooth=True)
        self.plate = self.create_image(0, 0, anchor="nw", state="hidden")
        self.label = self.create_text(0, 0, font=font)
        self.color = None
        self.size = (1, 1)

    def set(self, text, color, animate=True):
        pad_x, pad_y = round(10 * self.scale), round(3 * self.scale)
        width = self.font.measure(text) + 2 * pad_x
        height = self.font.metrics("linespace") + 2 * pad_y
        self.configure(width=width, height=height)
        self.size = (width, height)
        self.coords(self.shape, *round_points(0, 0, width - 1, height - 1, height / 2))
        self.coords(self.label, width / 2, height / 2)
        self.itemconfigure(self.label, text=text)
        old, self.color = self.color, color
        if animate and old and old != color:
            self.animator.animate(("pill", id(self)), 0.35, lambda t: self._paint(lerp(old, color, t)))
        else:
            self._paint(color)

    def _paint(self, color):
        fill, outline = quantize(mix(color, self.bg, 0.16)), quantize(mix(color, self.bg, 0.35))
        width, height = self.size
        image = shape_image(self, ("pill", fill, outline), width, height,
                            lambda surface: surface.round_rect(0, 0, width, height, height / 2, fill, outline))
        if image:
            self.itemconfigure(self.plate, image=image, state="normal")
            self.itemconfigure(self.shape, state="hidden")
        else:
            self.itemconfigure(self.shape, fill=fill, outline=outline, state="normal")
            self.itemconfigure(self.plate, state="hidden")
        self.itemconfigure(self.label, fill=color)


class GradientButton(tk.Canvas):
    """A button: the primary one has the brand gradient and a hover glow, the secondary one is flat.
    A danger button is red: for an action the user takes against SimpleTool's advice."""

    STEPS = 6  # glow steps, so the images are cached
    DANGER = ("#E5484D", "#C2373C")  # the same red in every theme: white text stays readable on it

    def __init__(self, parent, text, command, font, scale, animator, primary=True, pad=(20, 8), danger=False):
        self.bg = parent.cget("bg")
        measure = tkfont.Font(font=font)
        self.w = measure.measure(text) + 2 * round(pad[0] * scale)
        self.h = measure.metrics("linespace") + 2 * round(pad[1] * scale)
        super().__init__(parent, width=self.w, height=self.h, bg=self.bg, highlightthickness=0, bd=0, cursor="hand2")
        self.command, self.animator, self.primary, self.danger = command, animator, primary, danger
        self.radius = round(10 * scale)
        self.enabled, self.hover, self.level = True, 0.0, None
        self.image = self.create_image(0, 0, anchor="nw")
        self.text = self.create_text(self.w / 2, self.h / 2, text=text, font=font)
        self.bind("<Enter>", lambda e: self._hover_to(1.0))
        self.bind("<Leave>", lambda e: self._hover_to(0.0))
        self.bind("<Button-1>", self._click)
        self._draw(force=True)

    def _click(self, event):
        if self.enabled:
            self.command()

    def _hover_to(self, target):
        start = self.hover
        if not self.enabled:
            return
        self.animator.animate(("btn", id(self)), 0.2, lambda t: self._set_hover(start + (target - start) * t))

    def _set_hover(self, value):
        self.hover = value
        self._draw()

    def _draw(self, force=False):
        level = round(self.hover * self.STEPS) / self.STEPS if self.enabled else -1
        if level == self.level and not force:
            return
        self.level = level
        if not self.enabled:
            fill = mix(C["raised"], self.bg, 0.6)
            image = theme.gradient_pill(self.w, self.h, self.radius, fill, fill, self.bg)
            text = C["dim"]
        elif self.primary or self.danger:
            start, end = self.DANGER if self.danger else (C["grad_a"], C["grad_b"])
            image = theme.gradient_pill(self.w, self.h, self.radius, start, end, self.bg, glow=level * 0.22)
            text = C["on_primary"]
        else:
            fill = lerp(C["raised"], mix(C["accent"], C["raised"], 0.3), level)
            image = theme.gradient_pill(self.w, self.h, self.radius, fill, fill, self.bg)
            text = C["text"]
        self.itemconfigure(self.image, image=image)
        self.itemconfigure(self.text, fill=text)

    def set_enabled(self, enabled):
        if enabled != self.enabled:
            self.enabled = enabled
            self.hover = 0.0
            self.configure(cursor="hand2" if enabled else "arrow")
            self._draw(force=True)


class CheckBox(tk.Canvas):
    """A checkbox: the fill and the check mark are drawn with an animation."""

    def __init__(self, parent, size, animator):
        self.bg = parent.cget("bg")
        super().__init__(parent, width=size, height=size, bg=self.bg, highlightthickness=0)
        self.size, self.animator = size, animator
        self.progress, self.enabled = 0.0, True
        self._draw(0.0)

    def set(self, checked, enabled, animate=True):
        target = 1.0 if checked else 0.0
        changed_enabled = enabled != self.enabled
        self.enabled = enabled
        if animate and target != self.progress:
            start = self.progress
            self.animator.animate(("check", id(self)), 0.22,
                                  lambda t: self._draw(start + (target - start) * t))
        elif changed_enabled or target != self.progress:
            self._draw(target)

    def _draw(self, p):
        self.progress = p
        self.delete("all")
        s = self.size
        if not self.enabled:
            fill, outline = self.bg, mix(C["border"], self.bg, 0.8)
        else:
            p = round(p * 24) / 24  # the frames of the animation are cached
            empty = mix(C["bg"], self.bg, 0.7)
            fill = lerp(empty, C["primary"], p)
            outline = lerp(mix(C["muted"], self.bg, 0.45), C["primary"], p)
        fill, outline = quantize(fill), quantize(outline)
        path = self._check_path(p) if p > 0 and self.enabled else []
        mark, line = C["on_primary"], max(2, s / 9)

        def draw(surface):
            # Tk drew the 1.5 px outline 2 px wide: the same weight, centred on the same square
            surface.round_rect(0, 0, s, s, s * 0.3 + 1, fill, outline, 2.0)
            if len(path) > 1:
                surface.polyline([(x * s, y * s) for x, y in path], mark, line)

        image = shape_image(self, ("check", fill, outline, mark, tuple(path)), s, s, draw)
        if image:
            self.create_image(0, 0, anchor="nw", image=image)
            return
        self.create_polygon(*round_points(1, 1, s - 1, s - 1, s * 0.3), smooth=True, fill=fill, outline=outline, width=1.5)
        if len(path) > 1:
            self.create_line(*[c * s for point in path for c in point], fill=mark, width=line, capstyle="round",
                             joinstyle="round")

    @staticmethod
    def _check_path(p):
        """The part of the check mark drawn at progress p, in fractions of the box."""
        points = [(0.27, 0.52), (0.43, 0.68), (0.74, 0.34)]
        lengths = [math.dist(points[i], points[i + 1]) for i in range(2)]
        remaining = p * sum(lengths)
        path = [points[0]]
        for (a, b), length in zip(zip(points, points[1:]), lengths):
            part = min(1.0, remaining / length)
            path.append((round(a[0] + (b[0] - a[0]) * part, 4), round(a[1] + (b[1] - a[1]) * part, 4)))
            remaining -= length
            if remaining <= 0:
                break
        return path


def smooth_frame(size, draw, background):
    """An antialiased PhotoImage of size × size drawn by draw(surface) through GDI+, or None if that is not
    available (then the caller draws on the canvas as Tk can)."""
    try:
        with raster.Surface(size, size, background) as surface:
            draw(surface)
            return tk.PhotoImage(data=surface.png())
    except (OSError, tk.TclError):
        return None


class ScanRings(tk.Canvas):
    """Scan animation: expanding rings and two rotating arcs in the brand colors.

    The frames are drawn antialiased through GDI+ (raster.py) and kept while the animation runs: it repeats every
    PERIOD seconds, so after the first cycle no frame is drawn twice. Without GDI+ the canvas draws them itself."""

    FPS = 30
    PERIOD = 3.6  # the rings expand twice and the arcs make two and one turns, so the loop joins seamlessly

    def __init__(self, parent, size, scale, icon, icon_font):
        self.bg = parent.cget("bg")
        super().__init__(parent, width=size, height=size, bg=self.bg, highlightthickness=0)
        self.size, self.scale, self.icon, self.icon_font = size, scale, icon, icon_font
        self.running = False
        self.frames = {}
        self.smooth = True

    def start(self):
        if not self.running:
            self.running = True
            self._frame()

    def stop(self):
        self.running = False
        self.frames = {}

    def _draw(self, surface, t):
        c, s = self.size / 2, self.size
        for i in range(3):
            k = (t / (self.PERIOD / 2) + i / 3) % 1.0
            surface.circle(c, c, s * 0.2 + k * s * 0.28, C["accent"], max(1.0, 1.5 * self.scale), alpha=(1 - k) * 0.55)
        for radius, turns, extent, color, width in ((0.24, 2, 120, C["grad_a"], 4), (0.17, -1, 90, C["grad_b"], 3)):
            surface.arc(c, c, s * radius, (t / self.PERIOD * 360 * turns) % 360, extent, color, width * self.scale)

    def _frame(self):
        if not self.running:
            return
        try:
            self.delete("all")
        except tk.TclError:
            self.running = False
            return
        t = time.perf_counter()
        c, s = self.size / 2, self.size
        if self.smooth:
            index = int((t % self.PERIOD) * self.FPS)
            if index not in self.frames:
                self.frames[index] = smooth_frame(self.size, lambda surface: self._draw(surface, index / self.FPS), self.bg)
            frame = self.frames[index]
            if frame is None:
                self.smooth = False  # no GDI+: the canvas draws the rest of the frames
            else:
                self.create_image(0, 0, anchor="nw", image=frame)
        if not self.smooth:
            for i in range(3):
                k = (t * 0.55 + i / 3) % 1.0
                r = s * 0.2 + k * s * 0.28
                self.create_oval(c - r, c - r, c + r, c + r, outline=mix(C["accent"], self.bg, (1 - k) * 0.55),
                                 width=max(1, round(1.5 * self.scale)))
            for radius, speed, extent, color, width in ((0.24, 240, 120, C["grad_a"], 4),
                                                        (0.17, -170, 90, C["grad_b"], 3)):
                r = s * radius
                self.create_arc(c - r, c - r, c + r, c + r, start=(t * speed) % 360, extent=extent, style="arc",
                                outline=color, width=round(width * self.scale))
        self.create_text(c, c, text=self.icon, font=self.icon_font, fill=C["text"])
        self.after(1000 // self.FPS if self.smooth else 16, self._frame)


class Spinner(tk.Canvas):
    """A small activity indicator in the footer: a ring with an arc that turns once a second. Drawn antialiased
    through GDI+ when it is there, one turn of frames kept while it runs."""

    FPS = 30

    def __init__(self, parent, size, scale):
        self.bg = parent.cget("bg")
        super().__init__(parent, width=size, height=size, bg=self.bg, highlightthickness=0)
        self.size, self.scale, self.running = size, scale, False
        self.frames = {}
        self.smooth = True

    def start(self):
        if not self.running:
            self.running = True
            self._frame()

    def stop(self):
        self.running = False
        self.frames = {}
        try:
            self.delete("all")
        except tk.TclError:
            pass

    def _draw(self, surface, angle):
        s, w = self.size, max(2.0, 2 * self.scale)
        c, r = s / 2, s / 2 - w
        surface.circle(c, c, r, C["accent"], w, alpha=0.2)
        surface.arc(c, c, r, angle, 100, C["accent"], w)

    def _frame(self):
        if not self.running:
            return
        try:
            self.delete("all")
        except tk.TclError:
            self.running = False
            return
        s, w = self.size, max(2, round(2 * self.scale))
        angle = (time.perf_counter() * 360) % 360
        if self.smooth:
            index = int(angle / 360 * self.FPS)
            if index not in self.frames:
                self.frames[index] = smooth_frame(self.size, lambda surface: self._draw(surface, index * 360 / self.FPS),
                                                  self.bg)
            frame = self.frames[index]
            if frame is None:
                self.smooth = False
            else:
                self.create_image(0, 0, anchor="nw", image=frame)
        if not self.smooth:
            self.create_oval(w, w, s - w, s - w, outline=mix(C["accent"], self.bg, 0.2), width=w)
            self.create_arc(w, w, s - w, s - w, start=angle, extent=100, style="arc", outline=C["accent"], width=w)
        self.after(1000 // self.FPS if self.smooth else 16, self._frame)


class Toast:
    """A notification that slides in at the bottom right and hides itself."""

    def __init__(self, root, animator, scale, fonts):
        self.root, self.animator, self.scale, self.fonts = root, animator, scale, fonts
        self.card = None

    def show(self, text, color, icon, margin=None, seconds=4.0):
        """margin is the distance from the right edge of the window, so the notification lines up with
        the content column."""
        self.hide(now=True)
        px = lambda n: round(n * self.scale)
        card = Card(self.root, self.scale, fill=C["surface"], border=mix(color, C["surface"], 0.6), radius=12, pad=6)
        card.configure(bg=C["bg"])
        card.backdrop.configure(bg=C["bg"])
        tk.Label(card.body, text=icon, font=self.fonts["icon"], fg=color, bg=C["surface"]).pack(
            side="left", padx=(px(12), px(8)), pady=px(10))
        tk.Label(card.body, text=text, font=self.fonts["body"], fg=C["text"], bg=C["surface"], justify="left",
                 wraplength=px(340)).pack(side="left", padx=(0, px(14)), pady=px(10))
        card.update_idletasks()
        self.card = card
        margin, height = (px(24) if margin is None else margin), card.winfo_reqheight()
        start, end = height + margin, -px(86)
        card.place(relx=1.0, rely=1.0, x=-margin, y=start, anchor="se")
        self.animator.animate(("toast", id(card)), 0.45, lambda t: card.place_configure(y=start + (end - start) * t))
        self.root.after(int(seconds * 1000), lambda: self.hide(card=card))

    def hide(self, card=None, now=False):
        card = card or self.card
        if card is None or not card.winfo_exists():
            return
        if now:
            card.destroy()
            return
        start = int(card.place_info().get("y", 0))
        end = start + card.winfo_height() + round(140 * self.scale)
        self.animator.animate(("toast", id(card)), 0.35, lambda t: card.place_configure(y=start + (end - start) * t),
                              done=card.destroy)


class Toggle(tk.Canvas):
    """A switch: the knob slides with an animation. command(on) is called after a click."""

    def __init__(self, parent, scale, animator, on=False, command=None):
        self.bg = parent.cget("bg")
        self.w, self.h = round(40 * scale), round(22 * scale)
        super().__init__(parent, width=self.w, height=self.h, bg=self.bg, highlightthickness=0, cursor="hand2")
        self.animator, self.command = animator, command
        self.on, self.pos = on, 1.0 if on else 0.0
        self.track = self.create_polygon(0, 0, 0, 0, smooth=True)
        self.knob = self.create_oval(0, 0, 0, 0, outline="")
        self.image = self.create_image(0, 0, anchor="nw", state="hidden")
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        off = mix(C["dim"], self.bg, 0.55)
        pos = round(self.pos * 32) / 32  # the frames of the slide are cached
        color = quantize(lerp(off, C["primary"], pos))
        w, h = self.w, self.h
        pad = round(h * 0.18)
        size = h - 2 * pad
        x = pad + pos * (w - h)

        def draw(surface):
            surface.round_rect(1, 1, w - 2, h - 2, (h - 2) / 2, fill=color)
            surface.fill_circle(x + size / 2, pad + size / 2, size / 2, "#FFFFFF")

        image = shape_image(self, ("toggle", pos, color), w, h, draw)
        if image:
            self.itemconfigure(self.image, image=image, state="normal")
            self.itemconfigure(self.track, state="hidden")
            self.itemconfigure(self.knob, state="hidden")
            return
        self.itemconfigure(self.track, fill=color, state="normal")
        self.coords(self.track, *round_points(1, 1, w - 1, h - 1, h / 2))
        self.coords(self.knob, x, pad, x + size, pad + size)
        self.itemconfigure(self.knob, fill="#FFFFFF", state="normal")

    def set(self, on, animate=True):
        self.on = on
        start, end = self.pos, 1.0 if on else 0.0

        def step(t):
            self.pos = start + (end - start) * t
            self._draw()

        if animate:
            self.animator.animate(("toggle", id(self)), 0.22, step)
        else:
            step(1.0)

    def _click(self, event):
        self.set(not self.on)
        if self.command:
            self.command(self.on)


class Segmented(tk.Canvas):
    """Choose one option out of several; the highlight slides to the selected one."""

    def __init__(self, parent, options, value, font, scale, animator, command=None):
        self.bg = parent.cget("bg")
        measure = tkfont.Font(font=font)
        pad_x, pad_y = round(12 * scale), round(4 * scale)
        self.options = options
        self.widths = [measure.measure(label) + 2 * pad_x for _, label in options]
        self.h = measure.metrics("linespace") + 2 * pad_y
        super().__init__(parent, width=sum(self.widths) + 4, height=self.h + 4, bg=self.bg, highlightthickness=0,
                         cursor="hand2")
        self.animator, self.command = animator, command
        total = sum(self.widths)
        fill, border = quantize(mix(C["raised"], self.bg, 0.8)), quantize(C["border"])
        plate = shape_image(self, ("segments", fill, border), total + 4, self.h + 4,
                            lambda surface: surface.round_rect(1, 1, total + 2, self.h + 2, (self.h + 2) / 2, fill,
                                                               border))
        self.shape = self.create_polygon(*round_points(1, 1, total + 3, self.h + 3, (self.h + 2) / 2), smooth=True,
                                         fill=fill, outline=border, state="hidden" if plate else "normal")
        if plate:
            self.create_image(0, 0, anchor="nw", image=plate)
        self.thumb = self.create_polygon(0, 0, 0, 0, smooth=True, fill=C["primary"], outline="")
        self.thumb_image = self.create_image(0, 0, anchor="nw", state="hidden")
        self.labels = []
        x = 2
        for width, (_, label) in zip(self.widths, options):
            self.labels.append(self.create_text(x + width / 2, 2 + self.h / 2, text=label, font=font))
            x += width
        self.index = next((i for i, (v, _) in enumerate(options) if v == value), 0)
        self.pos = float(self.index)
        self.bind("<Button-1>", self._click)
        self._draw()

    def _span(self, pos):
        """Left edge and width of the highlight for a fractional position between options."""
        lefts = [2 + sum(self.widths[:i]) for i in range(len(self.widths))]
        i = min(int(pos), len(self.widths) - 1)
        j, frac = min(i + 1, len(self.widths) - 1), pos - i
        return lefts[i] + (lefts[j] - lefts[i]) * frac, self.widths[i] + (self.widths[j] - self.widths[i]) * frac

    def _draw(self):
        left, width = self._span(self.pos)
        thumb_w, thumb_h, color = round(width - 2), self.h - 2, quantize(C["primary"])
        image = shape_image(self, ("thumb", color), thumb_w, thumb_h,
                            lambda surface: surface.round_rect(0, 0, thumb_w, thumb_h, thumb_h / 2, fill=color))
        if image:
            self.coords(self.thumb_image, round(left + 1), 3)
            self.itemconfigure(self.thumb_image, image=image, state="normal")
            self.itemconfigure(self.thumb, state="hidden")
        else:
            self.coords(self.thumb, *round_points(left + 1, 3, left + width - 1, self.h + 1, (self.h - 2) / 2))
        for i, label in enumerate(self.labels):
            self.itemconfigure(label, fill=C["on_primary"] if abs(self.pos - i) < 0.5 else C["muted"])

    def _click(self, event):
        x, index = 2, 0
        for i, width in enumerate(self.widths):
            if event.x < x + width:
                index = i
                break
            x += width
        else:
            index = len(self.widths) - 1
        if index == self.index:
            return
        start, self.index = self.pos, index

        def step(t):
            self.pos = start + (index - start) * t
            self._draw()

        self.animator.animate(("segment", id(self)), 0.24, step)
        if self.command:
            self.command(self.options[index][0])


def bar_image(widget, width, height, color):
    """A bar with round ends, antialiased; None without GDI+."""
    color = quantize(color)
    return shape_image(widget, ("bar", color), width, height,
                       lambda surface: surface.round_rect(0, 0, width, height, height / 2, fill=color))


class Meter(tk.Canvas):
    """A "used / limit" bar: teal when fine, orange near the limit, red above it."""

    def __init__(self, parent, scale, animator):
        self.bg = parent.cget("bg")
        self.h = max(4, round(6 * scale))
        super().__init__(parent, height=self.h, bg=self.bg, highlightthickness=0)
        self.animator, self.ratio, self.shown = animator, 0.0, 0.0
        self.track = self.create_polygon(0, 0, 0, 0, smooth=True, fill=mix(C["raised"], self.bg, 0.9))
        self.track_image = self.create_image(0, 0, anchor="nw", state="hidden")
        self.fill = self.create_polygon(0, 0, 0, 0, smooth=True)
        self.fill_image = self.create_image(0, 0, anchor="nw", state="hidden")
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        w = self.winfo_width()
        if w <= 1:
            return
        ratio = min(self.shown, 1.0)
        color = C["ok"] if self.ratio < 0.85 else C["warn"] if self.ratio <= 1.0 else C["bad"]
        fill_w = max(self.h, round(w * ratio))
        track = bar_image(self, w, self.h, mix(C["raised"], self.bg, 0.9))
        bar = bar_image(self, fill_w, self.h, color)
        if track and bar:
            self.itemconfigure(self.track_image, image=track, state="normal")
            self.itemconfigure(self.fill_image, image=bar, state="normal" if ratio > 0 else "hidden")
            self.itemconfigure(self.track, state="hidden")
            self.itemconfigure(self.fill, state="hidden")
            return
        self.coords(self.track, *round_points(0, 0, w, self.h, self.h / 2))
        self.itemconfigure(self.track, state="normal")
        self.itemconfigure(self.fill, fill=color, state="normal" if ratio > 0 else "hidden")
        self.coords(self.fill, *round_points(0, 0, fill_w, self.h, self.h / 2))

    def set(self, ratio, animate=True):
        start, self.ratio = self.shown, max(0.0, ratio)

        def step(t):
            self.shown = start + (self.ratio - start) * t
            self._draw()

        if animate:
            self.animator.animate(("meter", id(self)), 0.5, step)
        else:
            step(1.0)


class ProgressBar(tk.Canvas):
    """A thin bar filled with the brand gradient up to a share: how much of a page is applied. The gradient runs
    over the whole bar, so the filled part ends in the color the full bar would have there."""

    def __init__(self, parent, scale, animator, height=6):
        self.bg = parent.cget("bg")
        self.h = max(4, round(height * scale))
        super().__init__(parent, height=self.h, bg=self.bg, highlightthickness=0)
        self.animator, self.ratio, self.shown = animator, 0.0, 0.0
        self.track_color = mix(C["raised"], self.bg, 0.9)
        self.track = self.create_polygon(0, 0, 0, 0, smooth=True, fill=self.track_color)
        self.track_image = self.create_image(0, 0, anchor="nw", state="hidden")
        self.fill = self.create_image(0, 0, anchor="nw", state="hidden")
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        w = self.winfo_width()
        if w <= 1:
            return
        track = bar_image(self, w, self.h, self.track_color)
        if track:
            self.itemconfigure(self.track_image, image=track, state="normal")
            self.itemconfigure(self.track, state="hidden")
        else:
            self.coords(self.track, *round_points(0, 0, w, self.h, self.h / 2))
        width = round(w * max(0.0, min(self.shown, 1.0)))
        if width < self.h:
            self.itemconfigure(self.fill, state="hidden")
            return
        end = lerp(C["grad_a"], C["grad_b"], width / w)
        image = theme.gradient_pill(width, self.h, self.h / 2, C["grad_a"], end, self.track_color)
        self.itemconfigure(self.fill, image=image, state="normal")

    def set(self, ratio, animate=True):
        start, self.ratio = self.shown, max(0.0, min(ratio, 1.0))

        def step(t):
            self.shown = start + (self.ratio - start) * t
            self._draw()

        if animate:
            self.animator.animate(("progress", id(self)), 0.7, step, delay=0.15)
        else:
            step(1.0)


class Ring(tk.Canvas):
    """A share of a whole as a ring: a track, an arc in the brand gradient that grows clockwise from the top, and
    the percentage inside. The gradient runs around the whole circle, so the arc ends in the color a full ring
    would have there. The ring is an antialiased image (theme.ring): Tk's own arcs are jagged."""

    def __init__(self, parent, size, scale, animator, font):
        self.bg = parent.cget("bg")
        super().__init__(parent, width=size, height=size, bg=self.bg, highlightthickness=0)
        self.size, self.scale, self.animator, self.font = size, scale, animator, font
        self.ratio = self.shown = 0.0
        self.image = self.create_image(0, 0, anchor="nw")
        self.label = self.create_text(size / 2, size / 2, font=font, fill=C["text"])
        self._draw()

    def _draw(self):
        width = max(3, round(4.5 * self.scale))
        track = mix(C["text"], self.bg, 0.14)
        self.itemconfigure(self.image, image=theme.ring(self.size, self.shown, C["grad_a"], C["grad_b"], track, self.bg,
                                                        width))
        self.itemconfigure(self.label, text=f"{round(100 * min(self.shown, 1.0))}%")

    def set(self, ratio, animate=True, delay=0.0):
        start, self.ratio = self.shown, max(0.0, min(ratio, 1.0))

        def step(t):
            self.shown = start + (self.ratio - start) * t
            self._draw()

        if animate:
            self.animator.animate(("ring", id(self)), 0.9, step, delay=delay)
        else:
            step(1.0)


class Stepper(tk.Frame):
    """A value with − and + buttons that step it through the values ladder."""

    def __init__(self, parent, value, values, fmt, font, scale, command=None):
        super().__init__(parent, bg=parent.cget("bg"))
        self.value, self.values, self.fmt, self.command = value, values, fmt, command
        px = lambda n: round(n * scale)
        self.buttons = []
        for text, sign in (("−", -1), ("+", 1)):
            button = tk.Label(self, text=text, font=font, fg=C["text"], bg=C["raised"], width=2, cursor="hand2")
            button.bind("<Button-1>", lambda e, s=sign: self.change(s))
            button.bind("<Enter>", lambda e, b=button: b.configure(bg=mix(C["accent"], C["raised"], 0.3)))
            button.bind("<Leave>", lambda e, b=button: b.configure(bg=C["raised"]))
            self.buttons.append(button)
        self.label = tk.Label(self, text=fmt(value), font=font, fg=C["text"], bg=parent.cget("bg"), width=8)
        self.buttons[0].pack(side="left", ipady=px(1))
        self.label.pack(side="left", padx=px(4))
        self.buttons[1].pack(side="left", ipady=px(1))

    def change(self, sign):
        if sign > 0:
            value = next((v for v in self.values if v > self.value), self.value)
        else:
            value = next((v for v in reversed(self.values) if v < self.value), self.value)
        if value != self.value:
            self.value = value
            self.label.configure(text=self.fmt(value))
            if self.command:
                self.command(value)


class Flow(tk.Frame):
    """Lays out child widgets in rows from left to right and wraps what does not fit."""

    def __init__(self, parent, gap_x, gap_y):
        super().__init__(parent, bg=parent.cget("bg"), height=1)
        self.gap_x, self.gap_y = gap_x, gap_y
        self.items = []
        self.bind("<Configure>", lambda e: self.arrange())

    def add(self, widget):
        self.items.append(widget)
        self.after_idle(self.arrange)

    def arrange(self):
        width = self.winfo_width()
        if width <= 1:
            return
        x = y = row = 0
        for widget in self.items:
            w, h = widget.winfo_reqwidth(), widget.winfo_reqheight()
            if x and x + w > width:
                x, y, row = 0, y + row + self.gap_y, 0
            widget.place(x=x, y=y)
            x += w + self.gap_x
            row = max(row, h)
        height = y + row
        if height and int(self.cget("height")) != height:
            self.configure(height=height)
