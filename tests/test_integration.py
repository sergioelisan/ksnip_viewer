# SPDX-License-Identifier: GPL-2.0-only
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from gi.repository import Gio

from ksnip_viewer.preview import interface_xml


class IntegrationTests(unittest.TestCase):
    def test_app_import_in_fresh_process(self):
        # Other tests import document first, which pins Gdk 3 and can hide an
        # import-order failure in the actual desktop/D-Bus entry point.
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run([sys.executable, '-c',
            'import warnings, gi; warnings.simplefilter("error", gi.PyGIWarning); '
            'from ksnip_viewer.app import Application; '
            'from gi.repository import Gdk, Gtk; '
            'assert Gdk._version == "3.0"; assert Gtk._version == "3.0"'],
            cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_sushi_contract(self):
        interface = Gio.DBusNodeInfo.new_for_xml(interface_xml()).interfaces[0]
        self.assertEqual(interface.name, 'org.gnome.NautilusPreviewer2')
        method = next(m for m in interface.methods if m.name == 'ShowFile')
        self.assertIn(''.join(arg.signature for arg in method.in_args), ('ssb', 'ssbs'))

    def test_install_and_restore_custom_service(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, XDG_DATA_HOME=temp)
            service = Path(temp)/'dbus-1/services/org.gnome.NautilusPreviewer.service'
            service.parent.mkdir(parents=True)
            original = '[D-BUS Service]\nName=org.gnome.NautilusPreviewer\nExec=/custom/preview\n'
            service.write_text(original)
            install = [sys.executable, str(root/'scripts/install.py')]
            for _ in range(2):
                subprocess.run(install+['--space-preview'], env=env, check=True, capture_output=True)
            self.assertIn('--preview-service', service.read_text())
            desktop = Path(temp)/'applications/ksnip-viewer.desktop'
            self.assertIn(' %f', desktop.read_text())
            subprocess.run(install+['--uninstall'], env=env, check=True, capture_output=True)
            self.assertEqual(service.read_text(), original)
            self.assertFalse(desktop.exists())


if __name__ == '__main__':
    unittest.main()
