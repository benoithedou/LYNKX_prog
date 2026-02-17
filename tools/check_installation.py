#!/usr/bin/env python3
"""
Installation checker for LYNKX Production Test Tool.

Verifies that all dependencies are installed and modules can be imported.
"""
import sys
import importlib

def check_python_version():
    """Check Python version."""
    version = sys.version_info
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("  ⚠️  Warning: Python 3.8+ recommended")
        return False
    return True

def check_dependency(name, import_name=None):
    """Check if a dependency is installed."""
    if import_name is None:
        import_name = name

    try:
        module = importlib.import_module(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✓ {name} ({version})")
        return True
    except ImportError:
        print(f"✗ {name} - NOT INSTALLED")
        return False

def check_modules():
    """Check if all internal modules can be imported."""
    modules = [
        'core.serial_manager',
        'core.lynkx_protocol',
        'device.config',
        'device.bootloader',
        'firmware.encryption',
        'services.state_manager',
        'services.test_workflow',
        'ui.main_window',
        'ui.terminal_widget',
        'utils.crc',
        'utils.constants',
    ]

    print("\nChecking internal modules:")
    all_ok = True
    for module in modules:
        try:
            importlib.import_module(module)
            print(f"  ✓ {module}")
        except Exception as e:
            print(f"  ✗ {module} - {e}")
            all_ok = False

    return all_ok

def main():
    """Run all checks."""
    print("LYNKX Production Test Tool - Installation Check\n")
    print("=" * 50)

    # Check Python version
    print("\nPython Version:")
    py_ok = check_python_version()

    # Check dependencies
    print("\nRequired Dependencies:")
    deps_ok = True
    deps_ok &= check_dependency('pyserial', 'serial')
    deps_ok &= check_dependency('tkinter')
    deps_ok &= check_dependency('pycryptodomex', 'Cryptodome')

    print("\nOptional Dependencies (for future features):")
    check_dependency('opencv-python', 'cv2')
    check_dependency('pyzbar')
    check_dependency('sounddevice')
    check_dependency('fpdf2', 'fpdf')
    check_dependency('numpy')
    check_dependency('requests')

    # Check internal modules
    modules_ok = check_modules()

    # Summary
    print("\n" + "=" * 50)
    if py_ok and deps_ok and modules_ok:
        print("✅ Installation OK! Ready to run.")
        print("\nRun the application with:")
        print("  python3 main.py")
        return 0
    else:
        print("❌ Installation incomplete.")
        if not deps_ok:
            print("\nInstall missing dependencies:")
            print("  pip install -r ../requirements.txt")
        return 1

if __name__ == "__main__":
    sys.exit(main())
