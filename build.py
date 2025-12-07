#!/usr/bin/env python3
"""
Build script for Network Monitor executable.
Uses the project's virtual environment for building.
"""

import os
import sys
import shutil
import subprocess

APP_NAME = "NetworkMonitor"
MAIN_SCRIPT = "network_monitor.py"
VENV_PYTHON = ".venv\\Scripts\\python.exe" if sys.platform == "win32" else ".venv/bin/python"

def clean_build():
    """Remove build artifacts"""
    for item in ['build', 'dist', '__pycache__', f'{APP_NAME}.spec', 'NetworkMonitor.spec']:
        if os.path.exists(item):
            print(f"Removing {item}")
            if os.path.isdir(item):
                shutil.rmtree(item)
            else:
                os.remove(item)
    print("✓ Clean complete")

def build_executable():
    """Build the executable"""
    # Check for venv
    if not os.path.exists(VENV_PYTHON):
        print("⚠️ Virtual environment not found. Creating one...")
        subprocess.run([sys.executable, '-m', 'venv', '.venv'], check=True)
        pip = ".venv\\Scripts\\pip.exe" if sys.platform == "win32" else ".venv/bin/pip"
        subprocess.run([pip, 'install', 'flask', 'pyinstaller'], check=True)
    
    cmd = [
        VENV_PYTHON, '-m', 'PyInstaller',
        '--onefile',
        '--console',
        '--clean',
        '-y',
        '--name', APP_NAME,
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'numpy',
        '--exclude-module', 'PIL',
        '--exclude-module', 'pillow',
        '--exclude-module', 'tkinter',
        '--exclude-module', 'pygame',
        '--exclude-module', 'PyQt5',
        '--exclude-module', 'PyQt6',
        '--exclude-module', 'scipy',
        '--exclude-module', 'pandas',
        MAIN_SCRIPT
    ]
    
    print(f"Building {APP_NAME}...")
    print("-" * 60)
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        exe_ext = '.exe' if sys.platform == 'win32' else ''
        output_path = f'dist/{APP_NAME}{exe_ext}'
        
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print("-" * 60)
            print(f"✓ Build successful!")
            print(f"  Output: {output_path}")
            print(f"  Size: {size_mb:.1f} MB")
            print(f"\nRun: .\\dist\\{APP_NAME}{exe_ext}")
            print(f"(Web dashboard opens automatically)")
            return True
    
    print("✗ Build failed!")
    return False

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true')
    args = parser.parse_args()
    
    if args.clean:
        clean_build()
    else:
        build_executable()
