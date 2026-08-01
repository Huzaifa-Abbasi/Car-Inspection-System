"""
Build Automation Script for AutoScan Pro.

Installs PyInstaller if missing, generates the PyInstaller spec file,
and compiles the project into a directory bundle.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    print("[AutoScan Pro] Starting build process...")
    
    # 1. Install PyInstaller if not present
    try:
        import PyInstaller
        print("[AutoScan Pro] PyInstaller is already installed.")
    except ImportError:
        print("[AutoScan Pro] PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        import PyInstaller
        print("[AutoScan Pro] PyInstaller installed successfully.")
        
    # 2. Setup build paths
    project_root = Path(__file__).resolve().parent
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"
    spec_file = project_root / "AutoScanPro.spec"
    
    # Clean previous builds
    if dist_dir.exists():
        print(f"[AutoScan Pro] Cleaning old dist directory at {dist_dir} ...")
        shutil.rmtree(dist_dir, ignore_errors=True)
    if build_dir.exists():
        print(f"[AutoScan Pro] Cleaning old build directory at {build_dir} ...")
        shutil.rmtree(build_dir, ignore_errors=True)
        
    # 3. Create spec file
    spec_content = """# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None
datas = []
binaries = []
hiddenimports = []

# Collect dependencies
packages_to_collect = ['ultralytics', 'pywebview', 'weasyprint', 'cairocffi', 'cffi', 'uvicorn', 'fastapi', 'passlib', 'jose', 'xhtml2pdf']
for pkg in packages_to_collect:
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
        datas.extend(pkg_datas)
        binaries.extend(pkg_binaries)
        hiddenimports.extend(pkg_hiddenimports)
    except Exception as e:
        print(f"Warning collecting {pkg}: {e}")

# Include application assets and models
datas.extend([
    ('frontend', 'frontend'),
    ('backend/templates', 'backend/templates'),
    ('best.pt', '.'),
    ('yolov8n.pt', '.'),
])

# Additional hidden imports
hiddenimports.extend([
    'sqlite3',
    'aiosqlite',
    'sqlalchemy.sql.default_comparator',
    'passlib.handlers.bcrypt',
    'python-jose',
    'jose',
    'cv2',
    'numpy',
    'email_validator',
    'cairocffi',
    'cffi',
    'xhtml2pdf',
    'xhtml2pdf.pisa',
    'html5lib',
    'reportlab.graphics.barcode.common',
    'reportlab.graphics.barcode.code39',
    'reportlab.graphics.barcode.code93',
    'reportlab.graphics.barcode.code128',
    'reportlab.graphics.barcode.usps',
    'reportlab.graphics.barcode.usps4s',
])

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoScanPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to True so user can see errors/logs on terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutoScanPro',
)
"""

    print(f"[AutoScan Pro] Writing spec file to {spec_file} ...")
    spec_file.write_text(spec_content, encoding="utf-8")
    
    # 4. Run PyInstaller
    print("[AutoScan Pro] Compiling executable. This may take a few minutes...")
    import PyInstaller.__main__
    
    PyInstaller.__main__.run([
        str(spec_file),
        "--clean",
        "-y",
    ])
    
    print("[AutoScan Pro] Executable build complete!")
    print(f"[AutoScan Pro] Output directory: {dist_dir / 'AutoScanPro'}")
    print(f"[AutoScan Pro] Executable: {dist_dir / 'AutoScanPro' / 'AutoScanPro.exe'}")

if __name__ == "__main__":
    main()
