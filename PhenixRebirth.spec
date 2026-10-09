# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

_ffmpeg = collect_all('imageio_ffmpeg')      # the ffmpeg executable of the clips

a = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=_ffmpeg[1],
    datas=[('src', 'src'), ('assets', 'assets')] + _ffmpeg[0],
    hiddenimports=['game', 'settings', 'player', 'enemy', 'boss', 'explosion', 'starfield', 'sounds', 'i18n', 'highscores', 'videoclip'] + _ffmpeg[2],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PhenixRebirth',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PhenixRebirth',
)
