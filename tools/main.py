"""
LYNKX Production Test Tool - Main Entry Point

This is the refactored version with clean architecture.
"""
import sys
import os
import traceback

# Add the tools directory to Python path to enable relative imports
tools_dir = os.path.dirname(os.path.abspath(__file__))
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)

from ui.main_window import MainWindow


def main():
    """Application entry point."""
    try:
        app = MainWindow()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        input("Press Enter to exit...")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
