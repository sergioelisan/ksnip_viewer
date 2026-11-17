# SPDX-License-Identifier: GPL-2.0-only
"""Image-coordinate annotation model, shared by preview and PNG export."""
import math
from io import BytesIO
from pathlib import Path
from dataclasses import dataclass, field

import cairo
import gi

gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, GLib
from PIL import Image, ImageOps


@dataclass
class Mark:
    tool: str
    points: list
    color: tuple = (1, .28, .22, 1)
    width: float = 4
    text: str = ''
    number: int = 0


def draw_mark(cr, mark):
    cr.set_source_rgba(*mark.color)
    cr.set_line_width(mark.width)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    x, y = mark.points[0]
    ex, ey = mark.points[-1]
    if mark.tool == 'number':
        label = str(mark.number)
        cr.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(max(16, mark.width * 5))
        xb, yb, tw, th, _, _ = cr.text_extents(label)
        radius = max(14, mark.width * 4, tw / 2 + 6, th / 2 + 6)
        cr.arc(x, y, radius, 0, 2 * math.pi)
        cr.fill()
        red, green, blue, _ = mark.color
        ink = 0 if .2126 * red + .7152 * green + .0722 * blue > .6 else 1
        cr.set_source_rgb(ink, ink, ink)
        cr.move_to(x - tw / 2 - xb, y - th / 2 - yb)
        cr.show_text(label)
    elif mark.tool == 'text':
        cr.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(max(16, mark.width * 6))
        cr.move_to(x, y)
        cr.show_text(mark.text)
    elif mark.tool == 'rectangle':
        cr.rectangle(min(x, ex), min(y, ey), abs(ex-x), abs(ey-y))
        cr.stroke()
    elif mark.tool == 'ellipse':
        if abs(ex-x) < 1 or abs(ey-y) < 1:
            return
        cr.save()
        cr.translate((x+ex)/2, (y+ey)/2)
        cr.scale(abs(ex-x)/2, abs(ey-y)/2)
        cr.arc(0, 0, 1, 0, 2*math.pi)
        cr.restore()
        cr.stroke()
    else:
        cr.move_to(x, y)
        for px, py in mark.points[1:]:
            cr.line_to(px, py)
        cr.stroke()
        if mark.tool == 'arrow' and math.hypot(ex-x, ey-y) > 2:
            angle = math.atan2(ey-y, ex-x)
            size = max(14, mark.width * 4)
            cr.move_to(ex, ey)
            for offset in [-.5, .5]:
                cr.line_to(ex-size*math.cos(angle+offset), ey-size*math.sin(angle+offset))
                if offset < 0:
                    cr.move_to(ex, ey)
            cr.stroke()


@dataclass
class Document:
    pixbuf: object
    marks: list = field(default_factory=list)
    crop: tuple = None
    undo_stack: list = field(default_factory=list)
    redo_stack: list = field(default_factory=list)
    revision: int = 0
    saved_revision: int = 0
    serial: int = 0

    @classmethod
    def load(cls, path):
        # Decode in-process: recent GdkPixbuf releases delegate even PNG to
        # Glycin helpers, which are not available in every deployment.
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert('RGBA')
            width, height = image.size
            pixels = GLib.Bytes.new(image.tobytes())
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            pixels, GdkPixbuf.Colorspace.RGB, True, 8, width, height, width*4)
        return cls(pixbuf)

    @property
    def bounds(self):
        return self.crop or (0, 0, self.pixbuf.get_width(), self.pixbuf.get_height())

    @property
    def dirty(self):
        return self.revision != self.saved_revision

    def checkpoint(self):
        self.undo_stack.append((list(self.marks), self.crop, self.revision))
        self.redo_stack.clear()
        self.serial += 1
        self.revision = self.serial

    def add(self, mark):
        self.checkpoint()
        self.marks.append(mark)

    @property
    def next_number(self):
        return 1 + max((mark.number for mark in self.marks if mark.tool == 'number'), default=0)

    def add_number(self, point, color=(1, .28, .22, 1), width=4):
        self.add(Mark('number', [point], color, width, number=self.next_number))

    def set_crop(self, start, end):
        bx, by, bw, bh = self.bounds
        x = max(bx, int(min(start[0], end[0])))
        y = max(by, int(min(start[1], end[1])))
        right = min(bx+bw, int(max(start[0], end[0])))
        bottom = min(by+bh, int(max(start[1], end[1])))
        if right-x >= 2 and bottom-y >= 2:
            self.checkpoint()
            self.crop = (x, y, right-x, bottom-y)

    def history(self, redo=False):
        source, target = (self.redo_stack, self.undo_stack) if redo else (self.undo_stack, self.redo_stack)
        if source:
            target.append((list(self.marks), self.crop, self.revision))
            self.marks, self.crop, self.revision = source.pop()

    def paint(self, cr):
        Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
        cr.paint()
        for mark in self.marks:
            draw_mark(cr, mark)

    def render(self):
        x, y, width, height = self.bounds
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context(surface)
        cr.translate(-x, -y)
        self.paint(cr)
        surface.flush()
        return surface

    def save(self, path):
        self.render().write_to_png(str(path))

    def overwrite(self, path):
        with Image.open(path) as source:
            image_format = source.format
        png = BytesIO()
        self.render().write_to_png(png)
        with Image.open(BytesIO(png.getvalue())) as rendered:
            if image_format == 'JPEG':
                rgba = rendered.convert('RGBA')
                image = Image.new('RGB', rendered.size, 'white')
                image.paste(rgba, mask=rgba.getchannel('A'))
            else:
                image = rendered.copy()
            encoded = BytesIO()
            image.save(encoded, format=image_format)
        Path(path).write_bytes(encoded.getvalue())
