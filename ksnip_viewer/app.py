# SPDX-License-Identifier: GPL-2.0-only
import os
from pathlib import Path
import sys

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio, GLib, Gtk

from .document import Document, Mark, draw_mark

TOOLS = [('arrow', '↗', 'Seta', 'a'), ('preview', 'view-reveal-symbolic', 'Visualizar', 'v'),
         ('rectangle', '▭', 'Retângulo', 'r'), ('ellipse', '◯', 'Elipse', 'e'),
         ('pen', '✎', 'Desenho livre', 'p'), ('text', 'T', 'Texto', 't'),
         ('number', '①', 'Círculos numerados', 'n'),
         ('crop', '⌗', 'Recortar', 'x')]
COLORS = ['#ff493d', '#ffcc33', '#47d7a0', '#58a6ff', '#ffffff', '#20242e']


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Ksnip Viewer')
        self.set_default_size(1100, 760)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.document = None
        self.path = None
        self.tool = 'arrow'
        self.pending = None
        self.transform = (1, 0, 0)
        self.zoom = None
        self.color = Gdk.RGBA()
        self.color.parse(COLORS[0])
        self.connect('delete-event', self.on_close)
        self.connect('key-press-event', self.key)
        header = Gtk.HeaderBar(title='Ksnip Viewer', subtitle='Veja. Marque. Compartilhe.')
        header.set_show_close_button(True)
        self.set_titlebar(header)
        self.button(header, 'Abrir', self.open_dialog, start=True)
        self.button(header, 'Salvar como…', self.save)
        self.button(header, 'Copiar imagem', self.copy)
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(layout)
        toolbar = Gtk.Box(spacing=6, margin=12)
        layout.pack_start(toolbar, False, False, 0)
        self.tool_buttons = {}
        group = None
        for tool, icon, label, shortcut in TOOLS:
            if tool == 'preview':
                button = Gtk.RadioButton.new_from_widget(group)
                button.add(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
            else:
                button = Gtk.RadioButton.new_with_label_from_widget(group, icon)
            group = group or button
            button.set_mode(False)
            button.set_tooltip_text(f'{label} ({shortcut.upper()})')
            button.connect('toggled', self.select_tool, tool)
            toolbar.pack_start(button, False, False, 0)
            self.tool_buttons[tool] = button
        self.tool_buttons['arrow'].set_active(True)
        toolbar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 6)
        self.color_button = Gtk.ColorButton(rgba=self.color)
        self.color_button.set_tooltip_text('Cor da anotação')
        self.color_button.connect('color-set', lambda b: setattr(self, 'color', b.get_rgba()))
        toolbar.pack_start(self.color_button, False, False, 0)
        self.width = Gtk.SpinButton.new_with_range(1, 24, 1)
        self.width.set_value(8)
        self.width.set_tooltip_text('Espessura em pixels da imagem')
        toolbar.pack_start(self.width, False, False, 0)
        self.button(toolbar, '↶', lambda *_: self.history(), tooltip='Desfazer (Ctrl+Z)')
        self.button(toolbar, '↷', lambda *_: self.history(True), tooltip='Refazer (Ctrl+Shift+Z)')
        self.button(toolbar, 'Ajustar', lambda *_: self.set_zoom(None))
        self.button(toolbar, '100%', lambda *_: self.set_zoom(1))
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_hexpand(True)
        self.scroll.set_vexpand(True)
        layout.pack_start(self.scroll, True, True, 0)
        self.canvas = Gtk.DrawingArea()
        self.canvas.set_can_focus(True)
        self.canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                               Gdk.EventMask.POINTER_MOTION_MASK)
        self.canvas.connect('draw', self.draw)
        self.canvas.connect('button-press-event', self.press)
        self.canvas.connect('button-release-event', self.release)
        self.canvas.connect('motion-notify-event', self.motion)
        self.scroll.add_with_viewport(self.canvas)
        self.scroll.connect('size-allocate', lambda *_: self.resize_canvas())
        self.status = Gtk.Label(label='Abra uma imagem para começar · Ctrl+O')
        self.status.set_margin_top(10)
        self.status.set_margin_bottom(10)
        layout.pack_end(self.status, False, False, 0)
        self.show_all()

    @staticmethod
    def button(box, label, callback, start=False, tooltip=None):
        button = Gtk.Button(label=label)
        button.connect('clicked', callback)
        if tooltip:
            button.set_tooltip_text(tooltip)
        if isinstance(box, Gtk.HeaderBar):
            (box.pack_start if start else box.pack_end)(button)
        else:
            box.pack_start(button, False, False, 0)
        return button

    def message(self, text):
        self.status.set_text(text)

    def error(self, text):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.CLOSE, text=text)
        dialog.run()
        dialog.destroy()

    def on_close(self, *_):
        self.get_application().close_window()
        return True

    def load(self, file):
        path = file.get_path()
        if not path:
            self.error('Abra uma imagem local. Arquivos remotos precisam ser baixados primeiro.')
            return False
        try:
            document = Document.load(path)
        except (GLib.Error, OSError, ValueError) as exc:
            self.error(f'Não foi possível abrir esta imagem.\n{exc}')
            return False
        self.document, self.path = document, Path(path)
        self.pending = None
        self.zoom = None
        self.tool_buttons['arrow'].set_active(True)
        self.set_title(self.path.name + ' — Ksnip Viewer')
        self.resize_canvas()
        self.update_status()
        self.canvas.grab_focus()
        return True

    def open_dialog(self, *_):
        dialog = Gtk.FileChooserDialog(title='Abrir imagem', transient_for=self,
                                       action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('Cancelar', Gtk.ResponseType.CANCEL, 'Abrir', Gtk.ResponseType.OK)
        images = Gtk.FileFilter()
        images.set_name('Imagens')
        images.add_pixbuf_formats()
        dialog.add_filter(images)
        response = dialog.run()
        file = dialog.get_file()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and file:
            self.load(file)

    def select_tool(self, button, tool):
        if button.get_active():
            self.tool = tool
            self.pending = None
            if hasattr(self, 'canvas'):
                self.canvas.queue_draw()
                self.canvas.grab_focus()
                self.update_status()

    def update_status(self):
        if self.document:
            _, _, width, height = self.document.bounds
            label = next(t[2] for t in TOOLS if t[0] == self.tool)
            self.message(f'{self.path.name}   ·   {width} × {height}   ·   {label}   ·   '
                         'Ctrl+C copiar   ·   Ctrl+S salvar   ·   Espaço fechar')

    def set_zoom(self, zoom):
        self.zoom = zoom
        self.resize_canvas()

    def resize_canvas(self):
        if self.document and self.zoom:
            _, _, w, h = self.document.bounds
            self.canvas.set_size_request(int(w*self.zoom)+48, int(h*self.zoom)+48)
        else:
            self.canvas.set_size_request(1, 1)
        self.canvas.queue_draw()

    def draw(self, widget, cr):
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        cr.set_source_rgb(.075, .085, .105)
        cr.paint()
        if not self.document:
            cr.set_source_rgb(.65, .69, .75)
            cr.select_font_face('Sans')
            cr.set_font_size(22)
            cr.move_to(60, 90)
            cr.show_text('Uma imagem. Algumas marcas. Pronto para enviar.')
            return False
        x, y, iw, ih = self.document.bounds
        scale = self.zoom or max(.01, min((w-48)/iw, (h-48)/ih, 1))
        ox, oy = (w-iw*scale)/2, (h-ih*scale)/2
        self.transform = (scale, ox-x*scale, oy-y*scale)
        cr.save()
        cr.translate(self.transform[1], self.transform[2])
        cr.scale(scale, scale)
        cr.rectangle(x, y, iw, ih)
        cr.clip()
        cr.set_source_rgb(.23, .24, .27)
        cr.paint()
        self.document.paint(cr)
        if self.pending:
            if self.pending.tool == 'crop':
                a, b = self.pending.points[0], self.pending.points[-1]
                cr.set_source_rgba(1, 1, 1, .9)
                cr.set_line_width(1.5/scale)
                cr.set_dash([6/scale, 4/scale])
                cr.rectangle(min(a[0], b[0]), min(a[1], b[1]), abs(a[0]-b[0]), abs(a[1]-b[1]))
                cr.stroke()
            else:
                draw_mark(cr, self.pending)
        cr.restore()
        return False

    def point(self, event):
        scale, ox, oy = self.transform
        return ((event.x-ox)/scale, (event.y-oy)/scale)

    def press(self, _, event):
        if not self.document or event.button != 1 or self.tool == 'preview':
            return False
        self.canvas.grab_focus()
        point = self.point(event)
        x, y, w, h = self.document.bounds
        if not (x <= point[0] <= x+w and y <= point[1] <= y+h):
            return False
        color = tuple(getattr(self.color, c) for c in ('red', 'green', 'blue', 'alpha'))
        if self.tool == 'number':
            self.document.add_number(point, color, self.width.get_value())
            self.canvas.queue_draw()
            self.update_status()
            return True
        self.pending = Mark(self.tool, [point, point], color, self.width.get_value())
        if self.tool == 'text':
            dialog = Gtk.Dialog(title='Adicionar texto', transient_for=self, modal=True)
            dialog.add_buttons('Cancelar', Gtk.ResponseType.CANCEL, 'Adicionar', Gtk.ResponseType.OK)
            entry = Gtk.Entry(margin=16)
            entry.set_placeholder_text('Escreva sua indicação…')
            entry.set_activates_default(True)
            dialog.set_default_response(Gtk.ResponseType.OK)
            dialog.get_content_area().add(entry)
            dialog.show_all()
            if dialog.run() == Gtk.ResponseType.OK and entry.get_text().strip():
                self.pending.text = entry.get_text().strip()
                self.document.add(self.pending)
            dialog.destroy()
            self.pending = None
            self.canvas.queue_draw()
        return True

    def motion(self, _, event):
        if self.pending:
            point = self.point(event)
            if self.pending.tool == 'pen':
                self.pending.points.append(point)
            else:
                self.pending.points[-1] = point
            self.canvas.queue_draw()

    def release(self, _, event):
        if self.pending and event.button == 1:
            self.motion(None, event)
            mark, self.pending = self.pending, None
            if mark.tool == 'crop':
                self.document.set_crop(mark.points[0], mark.points[-1])
                self.resize_canvas()
            else:
                a, b = mark.points[0], mark.points[-1]
                if mark.tool == 'pen' or abs(a[0]-b[0])+abs(a[1]-b[1]) > 2:
                    self.document.add(mark)
            self.update_status()
            self.canvas.queue_draw()

    def history(self, redo=False):
        if self.document:
            self.pending = None
            self.document.history(redo)
            self.resize_canvas()
            self.update_status()

    def save(self, *_):
        if not self.document:
            return False
        dialog = Gtk.FileChooserDialog(title='Salvar imagem marcada', transient_for=self,
                                       action=Gtk.FileChooserAction.SAVE)
        dialog.add_buttons('Cancelar', Gtk.ResponseType.CANCEL, 'Salvar PNG', Gtk.ResponseType.OK)
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_folder(str(self.path.parent))
        dialog.set_current_name(self.path.stem + '-marcada.png')
        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()
        if response != Gtk.ResponseType.OK or not filename:
            return False
        if not filename.lower().endswith('.png'):
            filename += '.png'
            if Path(filename).exists():
                confirm = Gtk.MessageDialog(transient_for=self, modal=True,
                    message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.YES_NO,
                    text=f'Substituir o arquivo existente?\n{filename}')
                replace = confirm.run() == Gtk.ResponseType.YES
                confirm.destroy()
                if not replace:
                    return False
        # Never overwrite the source, even if chosen explicitly in the save dialog.
        if Path(filename).resolve() == self.path.resolve():
            self.error('Escolha outro nome para preservar a imagem original.')
            return False
        try:
            self.document.save(filename)
        except Exception as exc:
            self.error(f'Não foi possível salvar.\n{exc}')
            return False
        self.document.saved_revision = self.document.revision
        self.message(f'Salvo em {filename}')
        return True

    def quick_save(self):
        if not self.document:
            return False
        try:
            self.document.overwrite(self.path)
        except Exception as exc:
            self.error(f'Não foi possível salvar.\n{exc}')
            return False
        self.document.saved_revision = self.document.revision
        self.message(f'Salvo em {self.path}')
        return True

    def copy(self, *_):
        if self.document:
            surface = self.document.render()
            pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, surface.get_width(), surface.get_height())
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_image(pixbuf)
            clipboard.store()
            self.message('Imagem copiada. Cole na conversa com Ctrl+V.')

    def key(self, _, event):
        # Keep normal text and numeric editing shortcuts in GTK input controls.
        if isinstance(self.get_focus(), (Gtk.Entry, Gtk.SpinButton)):
            return False
        name = Gdk.keyval_name(event.keyval).lower()
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        if ctrl:
            if name == 'z': self.history(shift)
            elif name == 'y': self.history(True)
            elif name == 'c': self.copy()
            elif name == 's': self.quick_save()
            elif name == 'o': self.open_dialog()
            elif name in ('plus', 'equal', 'minus'):
                scale = self.zoom or self.transform[0]
                self.set_zoom(max(.05, min(8, scale*(.8 if name == 'minus' else 1.25))))
            else: return False
        elif name == 'escape' and self.pending:
            self.pending = None
            self.canvas.queue_draw()
        elif name in ('escape', 'space'):
            self.on_close()
        else:
            for tool, _, _, shortcut in TOOLS:
                if name == shortcut:
                    self.tool_buttons[tool].set_active(True)
                    return True
            return False
        return True


class Application(Gtk.Application):
    def __init__(self, service=False):
        super().__init__(application_id='io.github.ksnipviewer.Preview', flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.window = None
        self.service = service
        self.parent_handle = ''
        self.preview_connection = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme', True)
        if self.service:
            from .preview import PreviewService
            self.preview_service = PreviewService(self)
            self.hold()

    def ensure_window(self):
        if self.window is None:
            self.window = Window(self)
            self.emit_properties()
        return self.window

    def do_activate(self):
        if not self.service:
            self.ensure_window().present()

    def do_open(self, files, count, hint):
        window = self.ensure_window()
        if files:
            window.load(files[0])
        window.present()

    def close_window(self):
        if self.window:
            window, self.window = self.window, None
            window.destroy()
            self.emit_properties()

    def emit_properties(self):
        if hasattr(self, 'preview_service'):
            self.preview_service.changed()

    def show_file(self, uri, handle, toggle, token=''):
        file = Gio.File.new_for_uri(uri)
        if self.window and self.window.path and file.equal(Gio.File.new_for_path(str(self.window.path))):
            if toggle:
                self.window.on_close()
            else:
                self.window.present()
            return
        if token:
            os.environ['XDG_ACTIVATION_TOKEN'] = token
        self.parent_handle = handle
        self.ensure_window().load(file)
        self.window.present()
        self.emit_properties()


def main():
    service = '--preview-service' in sys.argv
    args = [arg for arg in sys.argv if arg != '--preview-service']
    raise SystemExit(Application(service).run(args))
