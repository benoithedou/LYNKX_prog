"""Terminal widget for displaying output."""
import os
from datetime import datetime
from tkinter import Text, Scrollbar, Frame, END, VERTICAL, BOTH, LEFT, RIGHT, Y, DISABLED, NORMAL
from typing import Optional


class TerminalWidget:
    """
    Terminal-like output widget using Text.

    Provides scrollable text output with optional file logging.
    """

    def __init__(self, parent, enable_log: bool = True):
        """
        Initialize terminal widget.

        Args:
            parent: Parent tkinter widget
            enable_log: Whether this terminal supports file logging
        """
        self.parent = parent
        self.enable_log = enable_log
        self.auto_scroll = True
        self.log_file_path: Optional[str] = None
        self.log_file_enabled = False
        self._log_file_handle = None  # Keep file handle open for performance

        # Create frame for terminal
        self.frame = Frame(parent, bg="black")
        self.frame.pack(fill=BOTH, expand=True)

        # Create Text widget with scrollbar (better line spacing control)
        self.text = Text(
            self.frame,
            bg="black",
            fg="lightgreen",
            font=('Courier', 14),
            wrap='word',
            spacing1=2,  # Space above each line
            spacing3=2,  # Space below each line
            insertbackground="lightgreen",
            selectbackground="darkgreen",
            selectforeground="white",
            state=DISABLED  # Read-only by default
        )
        self.text.pack(side=LEFT, fill=BOTH, expand=True)

        self.scrollbar = Scrollbar(self.frame, orient=VERTICAL, command=self.text.yview)
        self.scrollbar.pack(side=RIGHT, fill=Y)

        self.text.config(yscrollcommand=self._on_scroll)

        # Bind user interaction to disable auto-scroll
        self.text.bind('<Button-1>', self._on_user_select)
        self.scrollbar.bind('<Button-1>', self._on_user_select)
        # Bind mouse wheel for scroll detection
        self.text.bind('<MouseWheel>', self._on_mouse_wheel)
        self.text.bind('<Button-4>', self._on_mouse_wheel)  # Linux scroll up
        self.text.bind('<Button-5>', self._on_mouse_wheel)  # Linux scroll down

    def _on_scroll(self, first, last):
        """Handle scroll events and update scrollbar."""
        # Update scrollbar position
        self.scrollbar.set(first, last)

        # Re-enable auto-scroll if scrolled to bottom
        if float(last) >= 0.99:
            self.auto_scroll = True

    def _on_user_select(self, event):
        """Handle user click (disable auto-scroll)."""
        self.auto_scroll = False

    def _on_mouse_wheel(self, event):
        """Handle mouse wheel scroll."""
        # Disable auto-scroll when user scrolls manually
        self.auto_scroll = False
        # Check position after a short delay to allow scroll to complete
        self.parent.after(50, self._check_scroll_position)

    def _check_scroll_position(self):
        """Check if scrolled to bottom and re-enable auto-scroll."""
        first, last = self.text.yview()
        if last >= 0.99:
            self.auto_scroll = True

    # Source emoji mapping
    SOURCE_EMOJI = {
        'app':  '\U0001F4BB',  # 💻 application logic
        'uart': '\U0001F4E1',  # 📡 serial data from device
        'dbg':  '\U0001F50D',  # 🔍 protocol debug (TX/RX)
        'err':  '\U0000274C',  # ❌ error
    }

    def add_line(self, line: str, pos=END, prefix: str = "", source: str = "app") -> None:
        """
        Add line to terminal.

        Args:
            line: Line to add
            pos: Position to insert (default: END)
            prefix: Optional prefix for line
            source: Origin tag for emoji: 'app', 'uart', 'dbg', 'err'
        """
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        emoji = self.SOURCE_EMOJI.get(source, self.SOURCE_EMOJI['app'])
        full_line = f"{emoji} [{ts}] {prefix}{line}"

        # Enable editing temporarily
        self.text.config(state=NORMAL)

        # Add to text widget
        if pos == END:
            self.text.insert(END, full_line + "\n")
        else:
            self.text.insert("1.0", full_line + "\n")

        # Disable editing
        self.text.config(state=DISABLED)

        # Auto-scroll if enabled
        if self.auto_scroll and pos == END:
            self.text.see(END)

        # Log to file if enabled
        if self.enable_log and self.log_file_enabled and self.log_file_path:
            self._write_log(full_line)

    def _write_log(self, line: str) -> None:
        """Write line to log file."""
        if self._log_file_handle:
            try:
                self._log_file_handle.write(line + '\n')
                self._log_file_handle.flush()  # Flush immediately to ensure data is written
            except Exception as e:
                print(f"Error writing to log file: {e}")

    def clear(self) -> None:
        """Clear terminal."""
        self.text.config(state=NORMAL)
        self.text.delete("1.0", END)
        self.text.config(state=DISABLED)

    def set_log_file(self, path: Optional[str], enabled: bool = True) -> None:
        """
        Set log file path and enable/disable logging.

        Args:
            path: Path to log file (None to disable)
            enabled: Whether logging is enabled
        """
        # Close existing file if open
        self.close_log_file()

        self.log_file_path = path
        self.log_file_enabled = enabled and path is not None

        # Open log file if enabled
        if self.log_file_enabled and self.log_file_path:
            try:
                self._log_file_handle = open(self.log_file_path, 'w', encoding='utf-8')
                self._log_file_handle.write("=== Terminal Log Started ===\n")
                self._log_file_handle.flush()
            except Exception as e:
                print(f"Error creating log file: {e}")
                self.log_file_enabled = False
                self._log_file_handle = None

    def close_log_file(self) -> None:
        """Flush and close the log file."""
        if self._log_file_handle:
            try:
                self._log_file_handle.flush()
                self._log_file_handle.close()
            except Exception as e:
                print(f"Error closing log file: {e}")
            finally:
                self._log_file_handle = None
                self.log_file_enabled = False

    def get_all_lines(self) -> list:
        """Get all lines from terminal."""
        content = self.text.get("1.0", END)
        return content.strip().split('\n') if content.strip() else []

    def enable_auto_scroll(self, enabled: bool = True) -> None:
        """Enable or disable auto-scroll."""
        self.auto_scroll = enabled
