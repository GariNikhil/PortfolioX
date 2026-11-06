# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for PortfolioX.

Build from the repository root:

    .\\.venv\\Scripts\\python.exe -m PyInstaller --noconfirm --clean portfoliox.spec

Output: ``dist\\PortfolioX\\PortfolioX.exe`` (folder build; copy the whole
``PortfolioX`` folder, not just the .exe).

Only ``assets`` is bundled. ``data``, ``backups``, ``exports`` and
``referance`` are deliberately left out: they hold the live portfolio
database, generated reports, and personal broker statements and books.
Bundling them would publish that material inside the build. A frozen run
creates those folders next to the executable instead (see ``paths.py``),
so the same ``data`` folder keeps working when the build is moved.

``tools/fetch_stock_metadata.py`` uses yfinance, which pulls in pandas and
numpy (hundreds of MB). The GUI never imports it, so it is excluded to keep
the build small; add ``yfinance`` to ``hiddenimports`` below and drop the
excludes if that command must ship with the app.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# CustomTkinter loads its theme JSON files at runtime, which static import
# analysis cannot see. The contrib hook usually covers this; collecting the
# data explicitly keeps the build working if the hook is unavailable.
datas = [("assets", "assets")] + collect_data_files("customtkinter")

# Keyring imports its backend for the current OS by name, so none of them
# are found by walking imports.
hiddenimports = collect_submodules("keyring.backends") + [
    "customtkinter",
    "sqlite3",
    "openpyxl",
    "xlrd",
    "pypdf",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "pypdfium2",
        "yfinance",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PortfolioX",
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PortfolioX",
)
