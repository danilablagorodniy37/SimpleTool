"""Элементы интерфейса с анимациями: карточки, плашки, кнопки, флажки, индикаторы и уведомления."""
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
    """Покадровые анимации на root.after (~60 кадров в секунду). Новая анимация с тем же ключом заменяет старую."""

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
        """Окно закрывается: отменяем следующий кадр, иначе Tk вызовет его уже после закрытия."""
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
            except tk.TclError:  # виджет уже удалён — анимация больше не нужна
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
    """Проявляет текст: цвет надписей плавно идёт от цвета фона к своему."""
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
    """Карточка со скруглёнными углами. Размер задаёт содержимое (рамка body), а скруглённый фон
    рисуется на холсте-подложке, растянутом под всю карточку."""

    def __init__(self, parent, scale, fill=None, border=None, radius=12, pad=6):
        self.fill = fill or C["surface"]
        self.border = border or C["border"]
        super().__init__(parent, bg=parent.cget("bg"))
        self.radius, self.pad = radius * scale, max(2, round(pad * scale))
        self.backdrop = tk.Canvas(self, bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.backdrop.place(x=0, y=0, relwidth=1, relheight=1)
        self.shape = self.backdrop.create_polygon(0, 0, 0, 0, smooth=True, fill=self.fill, outline=self.border, width=1)
        self.body = tk.Frame(self, bg=self.fill)
        self.body.pack(fill="both", expand=True, padx=self.pad, pady=self.pad)
        self.bind("<Configure>", self._layout)

    def _layout(self, event):
        self.backdrop.coords(self.shape, *round_points(1, 1, event.width - 2, event.height - 2, self.radius))

    def set_border(self, color):
        self.border = color
        self.backdrop.itemconfigure(self.shape, outline=color)


class Pill(tk.Canvas):
    """Плашка состояния со скруглёнными краями; смена цвета анимируется."""

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
    """Кнопка: основная — с фирменным градиентом и подсветкой при наведении, второстепенная — плоская."""

    STEPS = 6  # ступени подсветки, чтобы картинки кэшировались

    def __init__(self, parent, text, command, font, scale, animator, primary=True, pad=(20, 8)):
        self.bg = parent.cget("bg")
        measure = tkfont.Font(font=font)
        self.w = measure.measure(text) + 2 * round(pad[0] * scale)
        self.h = measure.metrics("linespace") + 2 * round(pad[1] * scale)
        super().__init__(parent, width=self.w, height=self.h, bg=self.bg, highlightthickness=0, bd=0, cursor="hand2")
        self.command, self.animator, self.primary = command, animator, primary
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
        elif self.primary:
            image = theme.gradient_pill(self.w, self.h, self.radius, C["grad_a"], C["grad_b"], self.bg, glow=level * 0.22)
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
    """Флажок: заливка и галочка дорисовываются анимацией."""

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
    """Анимация сканирования: расходящиеся кольца и две вращающиеся дуги фирменных цветов."""

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
    """Маленький индикатор работы в подвале."""

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
    """Уведомление, которое выезжает снизу справа и само прячется."""

    def __init__(self, root, animator, scale, fonts):
        self.root, self.animator, self.scale, self.fonts = root, animator, scale, fonts
        self.card = None

    def show(self, text, color, icon, margin=None, seconds=4.0):
        """margin — отступ от правого края окна, чтобы уведомление стояло по краю колонки содержимого."""
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
