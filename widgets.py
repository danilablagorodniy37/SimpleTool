"""Animated UI elements: cards, pills, buttons, checkboxes, indicators and notifications."""
import math
import time
import tkinter as tk
import tkinter.font as tkfont

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
        self.shape = self.backdrop.create_polygon(0, 0, 0, 0, smooth=True, fill=self.fill, outline=self.border, width=1)
        # A thin colored bar along the left edge: the status of a tweak, the severity of a finding
        self.bar = max(2, round(3 * scale))
        self.accent = self.backdrop.create_polygon(0, 0, 0, 0, smooth=True, outline="", state="hidden")
        self.body = tk.Frame(self, bg=self.fill)
        self.body.pack(fill="both", expand=True, padx=self.pad, pady=self.pad)
        self.bind("<Configure>", self._layout)

    def _layout(self, event):
        self.backdrop.coords(self.shape, *round_points(1, 1, event.width - 2, event.height - 2, self.radius))
        top = max(self.radius, self.bar)
        self.backdrop.coords(self.accent, *round_points(2, top, 2 + self.bar, event.height - top, self.bar / 2))

    def set_border(self, color):
        self.border = color
        self.backdrop.itemconfigure(self.shape, outline=color)

    def set_accent(self, color):
        """Shows the bar along the left edge in color, or hides it with None."""
        self.backdrop.itemconfigure(self.accent, fill=color or "", state="normal" if color else "hidden")


class Pill(tk.Canvas):
    """A status pill with rounded ends; color changes are animated."""

    def __init__(self, parent, font, scale, animator):
        self.bg = parent.cget("bg")
        super().__init__(parent, bg=self.bg, highlightthickness=0, bd=0, width=1, height=1)
        self.font, self.scale, self.animator = tkfont.Font(font=font), scale, animator
        self.shape = self.create_polygon(0, 0, 0, 0, smooth=True)
        self.label = self.create_text(0, 0, font=font)
        self.color = None

    def set(self, text, color, animate=True):
        pad_x, pad_y = round(10 * self.scale), round(3 * self.scale)
        width = self.font.measure(text) + 2 * pad_x
        height = self.font.metrics("linespace") + 2 * pad_y
        self.configure(width=width, height=height)
        self.coords(self.shape, *round_points(0, 0, width - 1, height - 1, height / 2))
        self.coords(self.label, width / 2, height / 2)
        self.itemconfigure(self.label, text=text)
        old, self.color = self.color, color
        if animate and old and old != color:
            self.animator.animate(("pill", id(self)), 0.35, lambda t: self._paint(lerp(old, color, t)))
        else:
            self._paint(color)

    def _paint(self, color):
        self.itemconfigure(self.shape, fill=mix(color, self.bg, 0.16), outline=mix(color, self.bg, 0.35))
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
            empty = mix(C["bg"], self.bg, 0.7)
            fill = lerp(empty, C["primary"], p)
            outline = lerp(mix(C["muted"], self.bg, 0.45), C["primary"], p)
        self.create_polygon(*round_points(1, 1, s - 1, s - 1, s * 0.3), smooth=True, fill=fill, outline=outline, width=1.5)
        if p > 0 and self.enabled:
            points = [(0.27, 0.52), (0.43, 0.68), (0.74, 0.34)]
            lengths = [math.dist(points[i], points[i + 1]) for i in range(2)]
            remaining = p * sum(lengths)
            path = [points[0]]
            for (a, b), length in zip(zip(points, points[1:]), lengths):
                part = min(1.0, remaining / length)
                path.append((a[0] + (b[0] - a[0]) * part, a[1] + (b[1] - a[1]) * part))
                remaining -= length
                if remaining <= 0:
                    break
            if len(path) > 1:
                self.create_line(*[c * s for point in path for c in point], fill=C["on_primary"],
                                 width=max(2, s / 9), capstyle="round", joinstyle="round")


class ScanRings(tk.Canvas):
    """Scan animation: expanding rings and two rotating arcs in the brand colors."""

    def __init__(self, parent, size, scale, icon, icon_font):
        self.bg = parent.cget("bg")
        super().__init__(parent, width=size, height=size, bg=self.bg, highlightthickness=0)
        self.size, self.scale, self.icon, self.icon_font = size, scale, icon, icon_font
        self.running = False

    def start(self):
        if not self.running:
            self.running = True
            self._frame()

    def stop(self):
        self.running = False

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
        for i in range(3):
            k = (t * 0.55 + i / 3) % 1.0
            r = s * 0.2 + k * s * 0.28
            self.create_oval(c - r, c - r, c + r, c + r, outline=mix(C["accent"], self.bg, (1 - k) * 0.55),
                             width=max(1, round(1.5 * self.scale)))
        for radius, speed, extent, color, width in ((0.24, 240, 120, C["grad_a"], 4), (0.17, -170, 90, C["grad_b"], 3)):
            r = s * radius
            self.create_arc(c - r, c - r, c + r, c + r, start=(t * speed) % 360, extent=extent, style="arc",
                            outline=color, width=round(width * self.scale))
        self.create_text(c, c, text=self.icon, font=self.icon_font, fill=C["text"])
        self.after(16, self._frame)


class Spinner(tk.Canvas):
    """A small activity indicator in the footer."""

    def __init__(self, parent, size, scale):
        self.bg = parent.cget("bg")
        super().__init__(parent, width=size, height=size, bg=self.bg, highlightthickness=0)
        self.size, self.scale, self.running = size, scale, False

    def start(self):
        if not self.running:
            self.running = True
            self._frame()

    def stop(self):
        self.running = False
        try:
            self.delete("all")
        except tk.TclError:
            pass

    def _frame(self):
        if not self.running:
            return
        try:
            self.delete("all")
        except tk.TclError:
            self.running = False
            return
        s, w = self.size, max(2, round(2 * self.scale))
        self.create_oval(w, w, s - w, s - w, outline=mix(C["accent"], self.bg, 0.2), width=w)
        self.create_arc(w, w, s - w, s - w, start=(time.perf_counter() * 360) % 360, extent=100, style="arc",
                        outline=C["accent"], width=w)
        self.after(16, self._frame)


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
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        off = mix(C["dim"], self.bg, 0.55)
        self.itemconfigure(self.track, fill=lerp(off, C["primary"], self.pos))
        self.coords(self.track, *round_points(1, 1, self.w - 1, self.h - 1, self.h / 2))
        pad = round(self.h * 0.18)
        size = self.h - 2 * pad
        x = pad + self.pos * (self.w - self.h)
        self.coords(self.knob, x, pad, x + size, pad + size)
        self.itemconfigure(self.knob, fill="#FFFFFF")

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
        self.shape = self.create_polygon(*round_points(1, 1, sum(self.widths) + 3, self.h + 3, (self.h + 2) / 2),
                                         smooth=True, fill=mix(C["raised"], self.bg, 0.8), outline=C["border"])
        self.thumb = self.create_polygon(0, 0, 0, 0, smooth=True, fill=C["primary"], outline="")
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


class Meter(tk.Canvas):
    """A "used / limit" bar: teal when fine, orange near the limit, red above it."""

    def __init__(self, parent, scale, animator):
        self.bg = parent.cget("bg")
        self.h = max(4, round(6 * scale))
        super().__init__(parent, height=self.h, bg=self.bg, highlightthickness=0)
        self.animator, self.ratio, self.shown = animator, 0.0, 0.0
        self.track = self.create_polygon(0, 0, 0, 0, smooth=True, fill=mix(C["raised"], self.bg, 0.9))
        self.fill = self.create_polygon(0, 0, 0, 0, smooth=True)
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        w = self.winfo_width()
        if w <= 1:
            return
        self.coords(self.track, *round_points(0, 0, w, self.h, self.h / 2))
        ratio = min(self.shown, 1.0)
        color = C["ok"] if self.ratio < 0.85 else C["warn"] if self.ratio <= 1.0 else C["bad"]
        self.itemconfigure(self.fill, fill=color, state="normal" if ratio > 0 else "hidden")
        self.coords(self.fill, *round_points(0, 0, max(self.h, w * ratio), self.h, self.h / 2))

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
        self.fill = self.create_image(0, 0, anchor="nw", state="hidden")
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        w = self.winfo_width()
        if w <= 1:
            return
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
    would have there."""

    SEGMENTS = 48  # the arc is drawn in pieces, each in its own shade

    def __init__(self, parent, size, scale, animator, font):
        self.bg = parent.cget("bg")
        super().__init__(parent, width=size, height=size, bg=self.bg, highlightthickness=0)
        self.size, self.scale, self.animator, self.font = size, scale, animator, font
        self.ratio = self.shown = 0.0
        self._draw()

    def _draw(self):
        self.delete("all")
        s, w = self.size, max(3, round(4 * self.scale))
        pad = w / 2 + 1
        box = (pad, pad, s - pad, s - pad)
        self.create_oval(*box, outline=mix(C["raised"], self.bg, 0.9), width=w)
        extent = 360 * max(0.0, min(self.shown, 1.0))
        if extent > 0:
            steps = max(1, round(self.SEGMENTS * extent / 360))
            part = extent / steps
            for i in range(steps):
                # Tk arcs run counterclockwise from 3 o'clock; a piece from angle a to a + part clockwise from
                # 12 o'clock is drawn from 90 - (a + part). The pieces overlap a little so no seams show
                a = part * i
                shade = lerp(C["grad_a"], C["grad_b"], (a + part / 2) / 360)
                self.create_arc(*box, start=90 - (a + part), extent=part + (0.8 if i else 0), style="arc",
                                outline=shade, width=w)
        self.create_text(s / 2, s / 2, text=f"{round(100 * min(self.shown, 1.0))}%", font=self.font, fill=C["text"])

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
