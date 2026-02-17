"""Main application window."""
import serial.tools.list_ports
import cv2
from pyzbar.pyzbar import decode
from tkinter import Tk, Frame, Label, Entry, Button, StringVar, OptionMenu, X, BOTH
from tkinter import ttk, messagebox
from typing import List

from ui.test_tab import TestTab
from ui.update_tab import UpdateTab
from ui.terminal_tab import TerminalTab
from services.state_manager import AppState
from core.serial_manager import SerialManager
from core.lynkx_protocol import LYNKXProtocol
from utils.constants import HW_VERSION_1_04, HW_VERSION_1_02


class MainWindow:
    """
    Main application window.

    Manages the overall GUI and coordinates between tabs.
    """

    def __init__(self):
        """Initialize main window."""
        # Create application state
        self.state = AppState()

        # Create serial manager and protocol
        self.serial_manager = SerialManager()
        self.protocol = LYNKXProtocol(self.serial_manager)

        # Create main window
        self.window = Tk()
        self.window.title("LYNKX Production Test Tool - Refactored")
        self.window.configure(bg="white")
        self.window.geometry("900x850")

        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background="white", borderwidth=2, relief='ridge')
        style.configure(
            "TNotebook.Tab",
            background="white",
            foreground="black",
            font=('Helvetica', 11),
            padding=[10, 5]
        )
        style.map("TNotebook.Tab", background=[("selected", "lightgray")])

        # Create UI
        self._create_header()
        self._create_tabs()

        # Subscribe to state changes
        self.state.subscribe('serial_connected', self._on_serial_state_changed)

        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_header(self) -> None:
        """Create header section with common controls."""
        header_frame = Frame(self.window, bg="white")
        header_frame.pack(fill=X, padx=10, pady=10)

        # Operator name
        Label(
            header_frame,
            text="Operator:",
            font=('Helvetica', 12),
            bg="white",
            fg="black"
        ).grid(row=0, column=0, sticky="e", padx=5, pady=5)

        self.operator_var = StringVar(value=self.state.operator_name)
        self.operator_var.trace_add('write', self._on_operator_changed)

        Entry(
            header_frame,
            width=30,
            textvariable=self.operator_var,
            bg="white",
            fg="black"
        ).grid(row=0, column=1, padx=5)

        # Device ID QR Code
        Label(
            header_frame,
            text="Device ID (QR Code):",
            font=('Helvetica', 12),
            bg="white",
            fg="black"
        ).grid(row=1, column=0, sticky="e", padx=5, pady=5)

        self.qr_var = StringVar(value=self.state.device_id_qr)
        self.qr_var.trace_add('write', self._on_device_ids_changed)

        Entry(
            header_frame,
            width=30,
            textvariable=self.qr_var,
            bg="white",
            fg="black"
        ).grid(row=1, column=1, padx=5)

        Button(
            header_frame,
            text="📷 Scanner",
            command=lambda: self._scan_qr_code(self.qr_var),
            bg="white",
            fg="black"
        ).grid(row=1, column=2, padx=5)

        # Device ID Bar Code
        Label(
            header_frame,
            text="Device ID (Bar Code):",
            font=('Helvetica', 12),
            bg="white",
            fg="black"
        ).grid(row=2, column=0, sticky="e", padx=5, pady=5)

        self.bar_var = StringVar(value=self.state.device_id_bar)
        self.bar_var.trace_add('write', self._on_device_ids_changed)

        Entry(
            header_frame,
            width=30,
            textvariable=self.bar_var,
            bg="white",
            fg="black"
        ).grid(row=2, column=1, padx=5)

        # Hardware version
        Label(
            header_frame,
            text="HW Version:",
            font=('Helvetica', 12),
            bg="white",
            fg="black"
        ).grid(row=2, column=2, sticky="e", padx=5, pady=5)

        self.hw_var = StringVar(value=self.state.hardware_version)
        self.hw_var.trace_add('write', self._on_hw_version_changed)

        hw_menu = OptionMenu(
            header_frame,
            self.hw_var,
            HW_VERSION_1_02,
            HW_VERSION_1_04
        )
        hw_menu.configure(bg="white", fg="black")
        hw_menu.grid(row=2, column=3, padx=5)

        # COM Port
        Label(
            header_frame,
            text="COM Port:",
            font=('Helvetica', 12),
            bg="white",
            fg="black"
        ).grid(row=3, column=0, sticky="e", padx=5, pady=5)

        self.port_var = StringVar()
        self.port_menu = OptionMenu(header_frame, self.port_var, "")
        self.port_menu.configure(bg="white", fg="black")
        self.port_menu.grid(row=3, column=1, sticky="w", padx=5)

        Button(
            header_frame,
            text="↻",
            command=self._refresh_ports,
            bg="white",
            fg="black"
        ).grid(row=3, column=2, sticky="w", padx=5)

        self._refresh_ports()

    def _create_tabs(self) -> None:
        """Create tab notebook."""
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self.test_tab = TestTab(
            notebook,
            self.state,
            self.serial_manager,
            self.protocol
        )
        notebook.add(self.test_tab.frame, text="Test")

        self.update_tab = UpdateTab(
            notebook,
            self.state,
            self.serial_manager,
            self.protocol
        )
        notebook.add(self.update_tab.frame, text="Update")

        self.terminal_tab = TerminalTab(
            notebook,
            self.state,
            self.serial_manager,
            self.protocol
        )
        notebook.add(self.terminal_tab.frame, text="Terminal")

    def _refresh_ports(self) -> None:
        """Refresh COM port list."""
        ports = [port.device for port in serial.tools.list_ports.comports()]

        if not ports:
            ports = ["Aucun port"]

        # Update menu
        menu = self.port_menu["menu"]
        menu.delete(0, "end")

        for port in ports:
            menu.add_command(
                label=port,
                command=lambda p=port: self._on_port_selected(p)
            )

        # Select usbserial port by default if available
        selected_port = ports[0]
        for port in ports:
            if "usbserial" in port.lower() or "usb" in port.lower():
                selected_port = port
                break

        self.port_var.set(selected_port)
        self.state.serial_port = selected_port

    def _on_port_selected(self, port: str) -> None:
        """Handle port selection."""
        self.port_var.set(port)
        self.state.serial_port = port

    def _on_operator_changed(self, *args) -> None:
        """Handle operator name change."""
        self.state.operator_name = self.operator_var.get()

    def _on_device_ids_changed(self, *args) -> None:
        """Handle device ID change."""
        self.state.set_device_ids(
            self.qr_var.get(),
            self.bar_var.get()
        )

    def _on_hw_version_changed(self, *args) -> None:
        """Handle hardware version change."""
        self.state.set_hardware_version(self.hw_var.get())

    def _on_serial_state_changed(self, data: dict) -> None:
        """Handle serial state change."""
        # Update UI based on connection state
        pass

    def _scan_qr_code(self, target_var: StringVar) -> None:
        """
        Scan QR code using camera.

        Args:
            target_var: StringVar to set with scanned data
        """
        cap = cv2.VideoCapture(0)
        window_name = "Scan QR Code (appuie sur 'q' pour quitter)"

        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 640, 480)

        # Center the window
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - 640) // 2
        y = (screen_height - 480) // 2
        cv2.moveWindow(window_name, x, y)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            for barcode in decode(frame):
                qr_data = barcode.data.decode('utf-8')
                cap.release()
                cv2.destroyAllWindows()
                target_var.set(qr_data)

                # Bring window to front
                self.window.lift()
                self.window.attributes('-topmost', True)
                self.window.after_idle(self.window.attributes, '-topmost', False)
                return

            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        # Bring window to front even if no QR scanned
        self.window.lift()
        self.window.attributes('-topmost', True)
        self.window.after_idle(self.window.attributes, '-topmost', False)

    def _on_closing(self) -> None:
        """Handle window close."""
        # Close serial connection
        if self.serial_manager.is_open:
            try:
                self.serial_manager.close()
            except Exception:
                pass

        self.window.destroy()

    def run(self) -> None:
        """Run application."""
        self.window.mainloop()
