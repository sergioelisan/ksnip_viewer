# SPDX-License-Identifier: GPL-2.0-only
import tempfile
import unittest
from pathlib import Path

import cairo

from ksnip_viewer.document import Document, Mark


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'source.png'
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 200)
        cr = cairo.Context(surface)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        surface.write_to_png(str(self.path))
        self.source_bytes = self.path.read_bytes()
        self.doc = Document.load(self.path)

    def test_export_marks_crop_and_original(self):
        self.doc.add(Mark('rectangle', [(30, 30), (120, 100)], (1, 0, 0, 1), 6))
        self.doc.set_crop((20, 20), (180, 150))
        output = Path(self.temp.name)/'marked.png'
        self.doc.save(output)
        exported = Document.load(output)
        self.assertEqual(exported.bounds, (0, 0, 160, 130))
        pixels = exported.pixbuf.get_pixels()
        stride = exported.pixbuf.get_rowstride()
        channels = exported.pixbuf.get_n_channels()
        pixel = 10*stride + 10*channels
        self.assertEqual(tuple(pixels[pixel:pixel+3]), (255, 0, 0))
        self.assertEqual(self.path.read_bytes(), self.source_bytes)

    def test_undo_redo_and_branch_dirty_state(self):
        self.doc.add(Mark('arrow', [(5, 5), (60, 80)]))
        self.doc.saved_revision = self.doc.revision
        self.doc.history()
        self.assertTrue(self.doc.dirty)
        self.doc.history(True)
        self.assertFalse(self.doc.dirty)
        self.doc.history()
        self.doc.add(Mark('text', [(20, 30)], text='Novo'))
        self.assertTrue(self.doc.dirty)
        self.assertFalse(self.doc.redo_stack)

    def test_overwrite_updates_open_file_and_keeps_jpeg_format(self):
        from PIL import Image
        for image_format, suffix in [('PNG', '.png'), ('JPEG', '.jpg')]:
            path = Path(self.temp.name)/('opened' + suffix)
            Image.new('RGB', (320, 200), 'white').save(path, format=image_format)
            document = Document.load(path)
            document.add(Mark('rectangle', [(30, 30), (120, 100)], (1, 0, 0, 1), 6))
            document.set_crop((20, 20), (180, 150))
            document.overwrite(path)
            with Image.open(path) as saved:
                self.assertEqual(saved.format, image_format)
                self.assertEqual(saved.size, (160, 130))
                red, green, blue = saved.convert('RGB').getpixel((10, 10))
                self.assertGreater(red, 180)
                self.assertLess(green, 100)
                self.assertLess(blue, 100)

    def test_crop_clamps_and_undo_restores(self):
        self.doc.set_crop((-10, -20), (500, 500))
        self.assertEqual(self.doc.bounds, (0, 0, 320, 200))
        self.doc.set_crop((100, 80), (30, 20))
        self.assertEqual(self.doc.bounds, (30, 20, 70, 60))
        self.doc.history()
        self.assertEqual(self.doc.bounds, (0, 0, 320, 200))

    def test_all_tools_render(self):
        for tool in ['arrow', 'rectangle', 'ellipse', 'pen', 'text']:
            self.doc.add(Mark(tool, [(20, 30), (100, 120)], text='Cliente'))
        self.assertEqual(self.doc.render().get_width(), 320)

    def test_number_sequence_history_and_new_image(self):
        self.doc.add_number((40, 40))
        self.doc.add(Mark('arrow', [(5, 5), (60, 80)]))
        self.doc.add_number((80, 40))
        self.assertEqual([m.number for m in self.doc.marks if m.tool == 'number'], [1, 2])
        self.doc.history()
        self.assertEqual(self.doc.next_number, 2)
        self.doc.history(True)
        self.assertEqual(self.doc.next_number, 3)
        self.doc.history()
        self.doc.add_number((120, 40))
        self.assertEqual(self.doc.marks[-1].number, 2)
        self.assertFalse(self.doc.redo_stack)
        self.assertEqual(Document.load(self.path).next_number, 1)

    def test_numbered_circles_export_with_contrast_and_multiple_digits(self):
        self.doc.add_number((60, 60), (1, 0, 0, 1))
        self.doc.add(Mark('number', [(180, 100)], (1, 1, 0, 1), number=100))
        output = Path(self.temp.name)/'numbered.png'
        self.doc.save(output)
        from PIL import Image
        with Image.open(output) as image:
            self.assertEqual(image.getpixel((48, 60))[:3], (255, 0, 0))
            region = image.crop((160, 90, 200, 110)).convert('RGB')
            self.assertTrue(any(max(pixel) < 30 for pixel in region.getdata()))
        self.assertEqual(self.path.read_bytes(), self.source_bytes)


if __name__ == '__main__':
    unittest.main()
