# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['start.py'],
    pathex=[],
    binaries=[],
    datas=[('README.md', '.')],
    hiddenimports=['ttkbootstrap.toast', 'ttkbootstrap.tooltip', 'meowauto.ui.appearance', 'meowauto.ui.logview', 'meowauto.ui.playlist', 'meowauto.ui.yuanshen', 'meowauto.widgets.table', 'meowauto.utils.countdown', 'pretty_midi'],
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
    name='MeowField_AutoPiano',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MeowField_AutoPiano',
)
