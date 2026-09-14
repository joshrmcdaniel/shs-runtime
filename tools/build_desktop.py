"""Build an asset-free native desktop app on the current operating system.

Run after `uv sync --locked --extra build`. LICENSE is the only explicit data file:
user APKs, episodes, screenshots, saves and native decompilations have no
path into the executable's resource collection.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'dist' / 'desktop'
    work = root / 'build' / 'desktop'
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='shs-build-') as temporary:
        stage = Path(temporary)
        entry = stage / 'shs_launcher.py'
        entry.write_text('from shs_runtime.application import main\n\nif __name__ == "__main__":\n    main()\n', encoding='utf-8')
        # pygame's hook supplies its bundled fallback font and SDL libraries.
        # Only authored runtime modules are reachable through this entry point.
        args = [sys.executable, '-m', 'PyInstaller', '--windowed', '--onedir', '--noconfirm',
                '--name', 'SHS Runtime', '--distpath', str(output), '--workpath', str(work),
                '--specpath', str(stage), '--paths', str(root / 'src'), '--noupx',
                '--add-data', str(root / 'LICENSE') + ':.',
                '--exclude-module', 'tkinter']
        if sys.platform == 'darwin':
            args += ['--osx-bundle-identifier', 'org.shsruntime.player']
        env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(work / 'pyinstaller-cache'))
        subprocess.run([*args, str(entry)], cwd=stage, env=env, check=True)
    print(f'Built desktop app in {output}')


if __name__ == '__main__':
    main()
