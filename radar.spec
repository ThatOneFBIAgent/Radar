# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\radar\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('themes', 'themes'),
        ('config.toml', '.'),
        ('assets', 'assets'),
        ('src/radar/data/cities_data.json.gz', 'radar/data'),
        ('src/radar/data/world_polygons.json', 'radar/data'),
        ('sound', 'sound'),
    ],
    hiddenimports=['dearpygui', 'miniaudio', 'cffi'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy', 'PIL', 'lxml', 'scipy', 'matplotlib', 'pandas', 
        'tkinter', 'PyQt5', 'IPython', 'notebook', 'jedi'
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='radar',
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
    icon=['assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='radar',
)
