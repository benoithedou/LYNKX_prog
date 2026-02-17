"""Test tab UI component."""
import threading
import os
import glob
from tkinter import Frame, Button, Label, StringVar, Checkbutton, IntVar, LabelFrame
from tkinter import filedialog, messagebox
from typing import Dict

from ui.terminal_widget import TerminalWidget
from services.state_manager import AppState
from services.test_workflow import TestWorkflow, TestWorkflowError
from core.serial_manager import SerialManager
from core.lynkx_protocol import LYNKXProtocol
from utils.constants import TEST_NAMES


class TestTab:
    """
    Test tab for device configuration and testing.

    Handles firmware selection, device configuration, and test execution.
    """

    def __init__(
        self,
        parent,
        state: AppState,
        serial_manager: SerialManager,
        protocol: LYNKXProtocol
    ):
        """
        Initialize test tab.

        Args:
            parent: Parent widget
            state: Application state
            serial_manager: Serial manager instance
            protocol: Protocol handler instance
        """
        self.frame = Frame(parent, bg="white", bd=2, relief='groove')
        self.state = state
        self.serial_manager = serial_manager
        self.protocol = protocol

        self._create_ui()
        self._load_default_firmware()

        # Subscribe to hardware version changes
        self.state.subscribe('hardware_version', self._on_hw_version_changed)

    def _on_hw_version_changed(self, data: dict) -> None:
        """Handle hardware version change."""
        self._load_default_firmware()

    def _create_ui(self) -> None:
        """Create tab UI."""
        # Firmware selection
        self.test_fw_var = StringVar()
        self.prod_fw_var = StringVar()

        Button(
            self.frame,
            text="Test Firmware",
            command=self._select_test_firmware,
            bg="white",
            fg="black"
        ).grid(row=0, column=0, pady=10, padx=5)

        Label(
            self.frame,
            textvariable=self.test_fw_var,
            bg="white",
            fg="black"
        ).grid(row=0, column=1, sticky="w")

        Button(
            self.frame,
            text="Prod Firmware",
            command=self._select_prod_firmware,
            bg="white",
            fg="black"
        ).grid(row=1, column=0, pady=10, padx=5)

        Label(
            self.frame,
            textvariable=self.prod_fw_var,
            bg="white",
            fg="black"
        ).grid(row=1, column=1, sticky="w")

        # Test checkboxes
        self.test_vars: Dict[str, IntVar] = {}
        for i, test_name in enumerate(TEST_NAMES):
            row = 2 + i // 3
            col = i % 3

            var = IntVar()
            self.test_vars[test_name] = var

            cb = Checkbutton(
                self.frame,
                text=test_name,
                variable=var,
                bg="white",
                fg="black",
                selectcolor="white"
            )
            cb.grid(row=row, column=col, padx=5, pady=2, sticky="w")

        # Action buttons
        Button(
            self.frame,
            text="Configure",
            command=self._run_configuration,
            bg="lightgreen",
            fg="black",
            font=('Helvetica', 12, 'bold')
        ).grid(row=10, column=0, pady=10, padx=5)

        Button(
            self.frame,
            text="Restart Test",
            command=self._restart_test,
            bg="white",
            fg="black"
        ).grid(row=10, column=1, pady=10, padx=5)

        Button(
            self.frame,
            text="New Device",
            command=self._reset,
            bg="white",
            fg="black"
        ).grid(row=10, column=2, pady=10, padx=5)

        # Terminal
        terminal_frame = LabelFrame(
            self.frame,
            text="Terminal",
            bg="white",
            fg="black"
        )
        terminal_frame.grid(row=11, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)

        self.terminal = TerminalWidget(terminal_frame, enable_log=False)

        # Configure grid weights
        self.frame.rowconfigure(11, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=1)

    def _load_default_firmware(self) -> None:
        """Load most recent firmware files based on hardware version."""
        hw_version = self.state.hardware_version

        if hw_version == "1.04":
            # HW 1.04 firmwares
            test_contains = 'LYNKX_test_firmware_HARD_14_Debug'
            prod_contains = 'LYNKXF_01.04'
        else:
            # HW 1.02 firmwares
            test_contains = 'LYNKX_test_firmware_HARD_12_Debug'
            prod_contains = 'LYNKXF_01.02'

        # Find most recent test firmware
        test_fw = self._find_recent_firmware('*.bin', contains=test_contains)
        if test_fw:
            self.state.test_firmware_path = test_fw
            self.test_fw_var.set(self._get_display_path(test_fw))

        # Find most recent production firmware
        prod_fw = self._find_recent_firmware('*.blf', contains=prod_contains)
        if prod_fw:
            self.state.production_firmware_path = prod_fw
            self.prod_fw_var.set(self._get_display_path(prod_fw))

    def _find_recent_firmware(self, pattern: str, contains: str = None) -> str:
        """
        Find most recent firmware file.

        Args:
            pattern: Glob pattern (e.g., '*.bin')
            contains: String that filename must contain

        Returns:
            Path to most recent file or empty string
        """
        # Get parent directory (one level up from tools)
        tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parent_dir = os.path.dirname(tools_dir)
        firmware_dir = os.path.join(parent_dir, 'firmwares')

        if not os.path.exists(firmware_dir):
            return ""

        files = glob.glob(os.path.join(firmware_dir, pattern))

        if contains:
            files = [f for f in files if contains in os.path.basename(f)]

        if not files:
            return ""

        # Return most recent
        files.sort(key=lambda x: os.path.getmtime(x))
        return files[-1]

    def _get_display_path(self, path: str) -> str:
        """Get display path showing parent_dir/filename."""
        parent_dir = os.path.basename(os.path.dirname(path))
        file_name = os.path.basename(path)
        return f"{parent_dir}/{file_name}"

    def _select_test_firmware(self) -> None:
        """Open file dialog for test firmware selection."""
        path = filedialog.askopenfilename(
            title="Select Test Firmware",
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")]
        )
        if path:
            self.state.test_firmware_path = path
            self.test_fw_var.set(self._get_display_path(path))

    def _select_prod_firmware(self) -> None:
        """Open file dialog for production firmware selection."""
        path = filedialog.askopenfilename(
            title="Select Production Firmware",
            filetypes=[("BLF files", "*.blf"), ("All files", "*.*")]
        )
        if path:
            self.state.production_firmware_path = path
            self.prod_fw_var.set(self._get_display_path(path))

    def _run_configuration(self) -> None:
        """Run full device configuration in background thread."""
        # Validate firmware selection
        if not self.state.test_firmware_path:
            messagebox.showerror("Error", "Please select test firmware")
            return

        if not self.state.production_firmware_path:
            messagebox.showerror("Error", "Please select production firmware")
            return

        # Run in background
        thread = threading.Thread(target=self._configuration_thread, daemon=True)
        thread.start()

    def _configuration_thread(self) -> None:
        """Configuration worker thread."""
        self.terminal.clear()

        def log(msg: str):
            self.terminal.add_line(msg)

        try:
            workflow = TestWorkflow(
                self.serial_manager,
                self.state,
                progress_callback=log
            )

            success = workflow.run_full_configuration(
                self.state.test_firmware_path,
                self.state.production_firmware_path
            )

            if success:
                log("✅ Configuration successful!")
            else:
                log("❌ Configuration failed")

        except TestWorkflowError as e:
            log(f"❌ Configuration error: {str(e)}")
            messagebox.showerror("Configuration Error", str(e))

        except Exception as e:
            log(f"❌ Unexpected error: {str(e)}")
            messagebox.showerror("Error", f"Unexpected error: {str(e)}")

    def _restart_test(self) -> None:
        """Restart test without reconfiguring device."""
        # Clear test checkboxes
        for var in self.test_vars.values():
            var.set(0)

        self.terminal.clear()
        self.terminal.add_line("Test restarted. Waiting for device output...")

    def _reset(self) -> None:
        """Reset for new device."""
        # Clear all state
        for var in self.test_vars.values():
            var.set(0)

        self.state.device_id_qr = ""
        self.state.device_id_bar = ""

        self.terminal.clear()
        self.terminal.add_line("Ready for new device")
