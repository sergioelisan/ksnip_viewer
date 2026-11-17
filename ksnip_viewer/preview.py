# SPDX-License-Identifier: GPL-2.0-only
"""Nautilus/Sushi D-Bus contract (legacy and GNOME 50)."""
import subprocess

from gi.repository import Gio, GLib

BUS = 'org.gnome.NautilusPreviewer'
PATH = '/org/gnome/NautilusPreviewer'


def interface_xml():
    # Use the locally installed Sushi schema to track the extra activation-token
    # argument and SelectionEvent type across GNOME versions.
    try:
        result = subprocess.run([
            'gresource', 'extract',
            '/usr/share/sushi/org.gnome.NautilusPreviewer.data.gresource',
            '/org/gnome/NautilusPreviewer/org.gnome.NautilusPreviewer2.xml',
        ], capture_output=True, text=True, check=True)
        return result.stdout
    except (OSError, subprocess.CalledProcessError):
        return '''<node><interface name="org.gnome.NautilusPreviewer2">
        <method name="ShowFile"><arg type="s" direction="in"/><arg type="s" direction="in"/>
        <arg type="b" direction="in"/><arg type="s" direction="in"/></method>
        <method name="Close"/><property name="Visible" type="b" access="read"/>
        <property name="ParentHandle" type="s" access="read"/></interface></node>'''


class PreviewService:
    def __init__(self, app):
        self.app = app
        self.connection = app.get_dbus_connection()
        self.interfaces = []
        legacy = '''<node><interface name="org.gnome.NautilusPreviewer">
        <method name="ShowFile"><arg type="s" direction="in"/><arg type="i" direction="in"/>
        <arg type="b" direction="in"/></method><method name="Close"/></interface></node>'''
        for xml in (legacy, interface_xml()):
            info = Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0]
            self.connection.register_object(PATH, info, self.call, self.get_property, None)
            self.interfaces.append(info.name)
        self.owner = Gio.bus_own_name_on_connection(self.connection, BUS, Gio.BusNameOwnerFlags.NONE,
                                                   None, self.name_lost)

    def name_lost(self, *_):
        print('O serviço de preview já está em uso. Feche o Sushi antes de iniciar este serviço.')
        self.app.quit()

    def get_property(self, connection, sender, path, interface, prop):
        if prop == 'Visible':
            return GLib.Variant('b', self.app.window is not None)
        if prop == 'ParentHandle':
            return GLib.Variant('s', self.app.parent_handle)
        return None

    def call(self, connection, sender, path, interface, method, parameters, invocation):
        args = parameters.unpack()
        # Reply before displaying a modal error/unsaved-changes dialog.
        invocation.return_value(GLib.Variant('()', ()))
        if method == 'Close':
            if self.app.window:
                GLib.idle_add(self.close)
        elif method == 'ShowFile':
            uri, handle, toggle, *extra = args
            if interface == 'org.gnome.NautilusPreviewer':
                handle = f'x11:{handle}'
            GLib.idle_add(self.show, uri, handle, toggle, extra[0] if extra else '')

    def close(self):
        if self.app.window:
            self.app.window.on_close()
        return GLib.SOURCE_REMOVE

    def show(self, uri, handle, toggle, token):
        self.app.show_file(uri, handle, toggle, token)
        return GLib.SOURCE_REMOVE

    def changed(self):
        self.connection.emit_signal(None, PATH, 'org.freedesktop.DBus.Properties', 'PropertiesChanged',
            GLib.Variant('(sa{sv}as)', ('org.gnome.NautilusPreviewer2', {
                'Visible': GLib.Variant('b', self.app.window is not None),
                'ParentHandle': GLib.Variant('s', self.app.parent_handle),
            }, [])))
