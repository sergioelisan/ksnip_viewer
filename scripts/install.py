#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Install per-user launchers; replacing Space preview is explicitly opt-in."""
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = '# Managed by ksnip-viewer'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--space-preview', action='store_true', help='Usar este app para Espaço no Nautilus')
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))
    desktop = data/'applications/ksnip-viewer.desktop'
    service = data/'dbus-1/services/org.gnome.NautilusPreviewer.service'
    backup = service.with_suffix('.service.ksnip-viewer-backup')
    if args.uninstall:
        for target in (desktop, service):
            if target.exists() and MARKER in target.read_text():
                target.unlink()
        if backup.exists() and not service.exists():
            backup.rename(service)
        print('Integração removida. Encerre a sessão para reativar o serviço de preview anterior.')
        return
    # Desktop Exec uses double-quoted arguments rather than shell quoting.
    def quote(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
    command = f'/usr/bin/python3 {quote(ROOT/"ksnip-viewer")}'
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text(f'''{MARKER}
[Desktop Entry]
Type=Application
Name=Ksnip Viewer
Comment=Visualize e marque screenshots rapidamente
Exec={command} %f
Icon=insert-image
Terminal=false
Categories=Graphics;Viewer;
MimeType=image/png;image/jpeg;image/webp;image/bmp;image/tiff;
''')
    if args.space_preview:
        service.parent.mkdir(parents=True, exist_ok=True)
        if service.exists() and MARKER not in service.read_text():
            if backup.exists():
                raise SystemExit(f'Backup já existe: {backup}. Resolva antes de instalar.')
            service.rename(backup)
        service.write_text(f'''{MARKER}
[D-BUS Service]
Name=org.gnome.NautilusPreviewer
Exec={command} --preview-service
''')
    print('Instalado. O projeto deve permanecer em: ' + str(ROOT))
    if args.space_preview:
        print('Encerre e entre na sessão para ativar o novo preview no Espaço.')


if __name__ == '__main__':
    main()
