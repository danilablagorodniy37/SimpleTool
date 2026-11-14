"""Antialiased drawing for what Tk's canvas draws jagged: circles and arcs of the animations, rounded cards,
pills, switches and check boxes.

Tk 8.6 draws lines, ovals and arcs without antialiasing, so a spinner looks like it was drawn in the nineties.
Windows' own GDI+ (gdiplus.dll, through ctypes, no third-party library) draws them smoothly into a bitmap; the
bitmap is written as a PNG, which Tk reads into a PhotoImage. A 150-pixel frame takes a few milliseconds.

Colors are passed to GDI+ with red and blue swapped on purpose: its bitmaps are stored as BGRA, so the raw bytes
then read as RGBA and go straight into the PNG without a conversion loop in Python.
"""
import ctypes
import struct
import zlib
from ctypes import wintypes

from theme import rgb

REAL = ctypes.c_float
ARGB = ctypes.c_uint32
PIXEL_FORMAT_32BPP_ARGB = 0x26200A
SMOOTHING_ANTIALIAS = 4
PIXEL_OFFSET_HALF = 4
UNIT_PIXEL = 2
LINE_CAP_ROUND = 2
LINE_JOIN_ROUND = 2
FILL_MODE_ALTERNATE = 0
LOCK_READ = 1


class _StartupInput(ctypes.Structure):
    _fields_ = [("GdiplusVersion", ctypes.c_uint32), ("DebugEventCallback", ctypes.c_void_p),
                ("SuppressBackgroundThread", wintypes.BOOL), ("SuppressExternalCodecs", wintypes.BOOL)]


class _Rect(ctypes.Structure):
    _fields_ = [("X", ctypes.c_int), ("Y", ctypes.c_int), ("Width", ctypes.c_int), ("Height", ctypes.c_int)]


class _PointF(ctypes.Structure):
    _fields_ = [("X", REAL), ("Y", REAL)]


class _BitmapData(ctypes.Structure):
    _fields_ = [("Width", ctypes.c_uint), ("Height", ctypes.c_uint), ("Stride", ctypes.c_int),
                ("PixelFormat", ctypes.c_int), ("Scan0", ctypes.c_void_p), ("Reserved", ctypes.c_size_t)]


_gdiplus = None
_token = ctypes.c_size_t()


def _library():
    """gdiplus.dll, started once. Raises OSError if GDI+ cannot be used."""
    global _gdiplus
    if _gdiplus is not None:
        return _gdiplus
    lib = ctypes.WinDLL("gdiplus")
    lib.GdiplusStartup.argtypes = [ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(_StartupInput), ctypes.c_void_p]
    lib.GdipCreateBitmapFromScan0.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                              ctypes.POINTER(ctypes.c_void_p)]
    lib.GdipGetImageGraphicsContext.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    lib.GdipSetSmoothingMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipSetPixelOffsetMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipGraphicsClear.argtypes = [ctypes.c_void_p, ARGB]
    lib.GdipCreatePen1.argtypes = [ARGB, REAL, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
    lib.GdipSetPenStartCap.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipSetPenEndCap.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipDrawEllipse.argtypes = [ctypes.c_void_p, ctypes.c_void_p, REAL, REAL, REAL, REAL]
    lib.GdipDrawArc.argtypes = [ctypes.c_void_p, ctypes.c_void_p, REAL, REAL, REAL, REAL, REAL, REAL]
    lib.GdipBitmapLockBits.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Rect), ctypes.c_uint, ctypes.c_int,
                                       ctypes.POINTER(_BitmapData)]
    lib.GdipBitmapUnlockBits.argtypes = [ctypes.c_void_p, ctypes.POINTER(_BitmapData)]
    lib.GdipDeletePen.argtypes = [ctypes.c_void_p]
    lib.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
    lib.GdipDisposeImage.argtypes = [ctypes.c_void_p]
    lib.GdipCreatePath.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
    lib.GdipAddPathArc.argtypes = [ctypes.c_void_p, REAL, REAL, REAL, REAL, REAL, REAL]
    lib.GdipClosePathFigure.argtypes = [ctypes.c_void_p]
    lib.GdipDeletePath.argtypes = [ctypes.c_void_p]
    lib.GdipCreateSolidFill.argtypes = [ARGB, ctypes.POINTER(ctypes.c_void_p)]
    lib.GdipDeleteBrush.argtypes = [ctypes.c_void_p]
    lib.GdipFillPath.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    lib.GdipDrawPath.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    lib.GdipFillEllipse.argtypes = [ctypes.c_void_p, ctypes.c_void_p, REAL, REAL, REAL, REAL]
    lib.GdipDrawLines.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_PointF), ctypes.c_int]
    lib.GdipSetPenLineJoin.argtypes = [ctypes.c_void_p, ctypes.c_int]
    if lib.GdiplusStartup(ctypes.byref(_token), ctypes.byref(_StartupInput(1, None, False, False)), None):
        raise OSError("GDI+ did not start")
    _gdiplus = lib
    return lib


def _argb(color, alpha=1.0):
    """A GDI+ color with red and blue swapped (see the module note); None is fully transparent."""
    if color is None:
        return 0
    r, g, b = rgb(color)
    return (round(max(0.0, min(alpha, 1.0)) * 255) << 24) | (b << 16) | (g << 8) | r


def _check(status, what):
    if status:
        raise OSError(f"GDI+ {what} failed with status {status}")


def png(width, height, rgba):
    """A PNG file in memory from top-down RGBA pixels, for tk.PhotoImage(data=...)."""
    line = width * 4
    rows = b"".join(b"\x00" + rgba[y * line:(y + 1) * line] for y in range(height))

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8 bits, RGBA
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows, 1)) + chunk(b"IEND", b"")


class Surface:
    """A bitmap of a solid background color to draw antialiased shapes on; png() gives the result. With background
    None the bitmap starts transparent, and the PNG keeps the soft edges as partial transparency: Tk blends such an
    image with whatever is under it on a canvas."""

    def __init__(self, width, height, background):
        self.lib = _library()
        self.width, self.height = max(int(width), 1), max(int(height), 1)
        self.bitmap, self.graphics = ctypes.c_void_p(), ctypes.c_void_p()
        _check(self.lib.GdipCreateBitmapFromScan0(self.width, self.height, 0, PIXEL_FORMAT_32BPP_ARGB, None,
                                                  ctypes.byref(self.bitmap)), "bitmap")
        try:
            _check(self.lib.GdipGetImageGraphicsContext(self.bitmap, ctypes.byref(self.graphics)), "graphics")
            _check(self.lib.GdipSetSmoothingMode(self.graphics, SMOOTHING_ANTIALIAS), "smoothing")
            # Coordinates name pixel edges, as in Tk's images, not pixel centres
            _check(self.lib.GdipSetPixelOffsetMode(self.graphics, PIXEL_OFFSET_HALF), "pixel offset")
            _check(self.lib.GdipGraphicsClear(self.graphics, _argb(background)), "clear")
        except OSError:
            self.close()
            raise

    def _pen(self, color, width, alpha, round_caps):
        pen = ctypes.c_void_p()
        _check(self.lib.GdipCreatePen1(_argb(color, alpha), REAL(width), UNIT_PIXEL, ctypes.byref(pen)), "pen")
        if round_caps:
            self.lib.GdipSetPenStartCap(pen, LINE_CAP_ROUND)
            self.lib.GdipSetPenEndCap(pen, LINE_CAP_ROUND)
        return pen

    def circle(self, cx, cy, radius, color, width, alpha=1.0):
        pen = self._pen(color, width, alpha, False)
        try:
            _check(self.lib.GdipDrawEllipse(self.graphics, pen, cx - radius, cy - radius, 2 * radius, 2 * radius),
                   "ellipse")
        finally:
            self.lib.GdipDeletePen(pen)

    def arc(self, cx, cy, radius, start, sweep, color, width, alpha=1.0, round_caps=True):
        """An arc of a circle: start is in degrees clockwise from 3 o'clock, sweep its length in degrees."""
        pen = self._pen(color, width, alpha, round_caps)
        try:
            _check(self.lib.GdipDrawArc(self.graphics, pen, cx - radius, cy - radius, 2 * radius, 2 * radius, start,
                                        sweep), "arc")
        finally:
            self.lib.GdipDeletePen(pen)

    def _brush(self, color, alpha):
        brush = ctypes.c_void_p()
        _check(self.lib.GdipCreateSolidFill(_argb(color, alpha), ctypes.byref(brush)), "brush")
        return brush

    def round_rect(self, x, y, width, height, radius, fill=None, border=None, border_width=1.0, alpha=1.0):
        """A rectangle with rounded corners whose outer edge is (x, y, width, height), filled and/or with a border
        of border_width inside that edge; radius is the radius of the outer edge."""
        inset = border_width / 2 if border else 0.0
        x, y, width, height = x + inset, y + inset, width - 2 * inset, height - 2 * inset
        r = max(0.01, min(radius - inset, width / 2, height / 2))
        path = ctypes.c_void_p()
        _check(self.lib.GdipCreatePath(FILL_MODE_ALTERNATE, ctypes.byref(path)), "path")
        try:
            d = 2 * r
            for ax, ay, start in ((x, y, 180), (x + width - d, y, 270), (x + width - d, y + height - d, 0),
                                  (x, y + height - d, 90)):
                _check(self.lib.GdipAddPathArc(path, ax, ay, d, d, start, 90), "arc")
            _check(self.lib.GdipClosePathFigure(path), "close")
            if fill:
                brush = self._brush(fill, alpha)
                try:
                    _check(self.lib.GdipFillPath(self.graphics, brush, path), "fill")
                finally:
                    self.lib.GdipDeleteBrush(brush)
            if border:
                pen = self._pen(border, border_width, alpha, False)
                try:
                    _check(self.lib.GdipDrawPath(self.graphics, pen, path), "border")
                finally:
                    self.lib.GdipDeletePen(pen)
        finally:
            self.lib.GdipDeletePath(path)

    def fill_circle(self, cx, cy, radius, color, alpha=1.0):
        brush = self._brush(color, alpha)
        try:
            _check(self.lib.GdipFillEllipse(self.graphics, brush, cx - radius, cy - radius, 2 * radius, 2 * radius),
                   "fill ellipse")
        finally:
            self.lib.GdipDeleteBrush(brush)

    def polyline(self, points, color, width, alpha=1.0):
        """Connected lines through points [(x, y), ...] with round ends and joins."""
        pen = self._pen(color, width, alpha, True)
        try:
            self.lib.GdipSetPenLineJoin(pen, LINE_JOIN_ROUND)
            array = (_PointF * len(points))(*[_PointF(px, py) for px, py in points])
            _check(self.lib.GdipDrawLines(self.graphics, pen, array, len(points)), "lines")
        finally:
            self.lib.GdipDeletePen(pen)

    def png(self):
        """The bitmap as a PNG file in memory, for tk.PhotoImage(data=...)."""
        data = _BitmapData()
        rect = _Rect(0, 0, self.width, self.height)
        _check(self.lib.GdipBitmapLockBits(self.bitmap, ctypes.byref(rect), LOCK_READ, PIXEL_FORMAT_32BPP_ARGB,
                                           ctypes.byref(data)), "lock")
        try:
            stride, line = data.Stride, self.width * 4
            raw = ctypes.string_at(data.Scan0, stride * self.height)
        finally:
            self.lib.GdipBitmapUnlockBits(self.bitmap, ctypes.byref(data))
        return png(self.width, self.height, b"".join(raw[y * stride:y * stride + line] for y in range(self.height)))

    def close(self):
        if self.graphics:
            self.lib.GdipDeleteGraphics(self.graphics)
            self.graphics = ctypes.c_void_p()
        if self.bitmap:
            self.lib.GdipDisposeImage(self.bitmap)
            self.bitmap = ctypes.c_void_p()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
