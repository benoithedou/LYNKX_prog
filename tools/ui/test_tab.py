"""Test tab UI component."""
import threading
import os
import glob
from tkinter import (
    Frame, Button, Label, StringVar, Checkbutton, IntVar,
    LabelFrame, DISABLED, NORMAL
)
from tkinter import filedialog, messagebox
from typing import Dict

from ui.terminal_widget import TerminalWidget
from services.state_manager import AppState
from services.test_workflow import TestWorkflow, TestWorkflowError
from services.test_runner import TestRunner
from services.report_generator import ReportGenerator
from core.serial_manager import SerialManager
from core.lynkx_protocol import LYNKXProtocol
from utils.constants import TEST_NAMES


class TestTab:
    """
    Test tab for device configuration and production testing.

    Handles firmware selection, device configuration, and the full
    production test sequence (LED, audio, RF, pressure, etc.).
    """

    def __init__(
        self,
        parent,
        state: AppState,
        serial_manager: SerialManager,
        protocol: LYNKXProtocol
    ):
        self.frame = Frame(parent, bg="white", bd=2, relief='groove')
        self.state = state
        self.serial_manager = serial_manager
        self.protocol = protocol
        self._test_runner: TestRunner = None

        self._create_ui()
        self._load_default_firmware()

        # Subscribe to hardware version changes
        self.state.subscribe('hardware_version', self._on_hw_version_changed)

    def _on_hw_version_changed(self, data: dict) -> None:
        """Handle hardware version change."""
        self._load_default_firmware()

    def _create_ui(self) -> None:
        """Create tab UI."""
        # --- Row 0-1: Firmware selection ---
        self.test_fw_var = StringVar()
        self.prod_fw_var = StringVar()

        Button(
            self.frame, text="Test Firmware",
            command=self._select_test_firmware,
            bg="white", fg="black"
        ).grid(row=0, column=0, pady=10, padx=5)

        Label(
            self.frame, textvariable=self.test_fw_var,
            bg="white", fg="black"
        ).grid(row=0, column=1, columnspan=2, sticky="w")

        Button(
            self.frame, text="Prod Firmware",
            command=self._select_prod_firmware,
            bg="white", fg="black"
        ).grid(row=1, column=0, pady=10, padx=5)

        Label(
            self.frame, textvariable=self.prod_fw_var,
            bg="white", fg="black"
        ).grid(row=1, column=1, columnspan=2, sticky="w")

        # --- Row 2-6: Test checkboxes (3 columns, all disabled initially) ---
        self.test_vars: Dict[str, IntVar] = {}
        self.test_checkboxes: Dict[str, Checkbutton] = {}

        for i, test_name in enumerate(TEST_NAMES):
            row = 2 + i // 3
            col = i % 3

            var = IntVar()
            self.test_vars[test_name] = var

            cb = Checkbutton(
                self.frame, text=test_name, variable=var,
                bg="white", fg="black", selectcolor="white",
                activeforeground="black", state=DISABLED
            )
            cb.grid(row=row, column=col, padx=5, pady=2, sticky="w")
            self.test_checkboxes[test_name] = cb

        # --- Row 8: Measurement labels ---
        self.ble_label_var = StringVar(value="BLE: Freq = ??? Hz / Power = ??? dBm")
        self.lora_label_var = StringVar(value="LoRa: Freq = ??? Hz / Power = ??? dBm")
        self.pressure_label_var = StringVar(value="Pressure = ??? mbar")

        Label(
            self.frame, textvariable=self.ble_label_var,
            bg="white", fg="black", font=('Helvetica', 9)
        ).grid(row=8, column=0, columnspan=2, padx=5, pady=1, sticky="w")

        self.ble_label_widget = Label(
            self.frame, text="", bg="white", fg="black"
        )

        Label(
            self.frame, textvariable=self.lora_label_var,
            bg="white", fg="black", font=('Helvetica', 9)
        ).grid(row=8, column=2, padx=5, pady=1, sticky="w")

        Label(
            self.frame, textvariable=self.pressure_label_var,
            bg="white", fg="black", font=('Helvetica', 9)
        ).grid(row=9, column=0, columnspan=2, padx=5, pady=1, sticky="w")

        # --- Row 10: Action buttons ---
        Button(
            self.frame, text="Configure",
            command=self._run_configuration,
            bg="lightgreen", fg="black",
            font=('Helvetica', 12, 'bold')
        ).grid(row=10, column=0, pady=10, padx=5)

        Button(
            self.frame, text="Restart Test",
            command=self._restart_test,
            bg="white", fg="black"
        ).grid(row=10, column=1, pady=10, padx=5)

        Button(
            self.frame, text="New Device",
            command=self._reset,
            bg="white", fg="black"
        ).grid(row=10, column=2, pady=10, padx=5)

        # --- Row 11: Terminal ---
        terminal_frame = LabelFrame(
            self.frame, text="Terminal",
            bg="white", fg="black"
        )
        terminal_frame.grid(row=11, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)

        self.terminal = TerminalWidget(terminal_frame, enable_log=False)

        # Configure grid weights
        self.frame.rowconfigure(11, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=1)

    # ------------------------------------------------------------------
    # Firmware selection
    # ------------------------------------------------------------------

    def _load_default_firmware(self) -> None:
        """Load most recent firmware files based on hardware version."""
        hw_version = self.state.hardware_version

        if hw_version == "1.04":
            test_contains = 'LYNKX_test_firmware_HARD_14_Debug'
            prod_contains = 'LYNKXF_01.04'
        else:
            test_contains = 'LYNKX_test_firmware_HARD_12_Debug'
            prod_contains = 'LYNKXF_01.02'

        test_fw = self._find_recent_firmware('*.bin', contains=test_contains)
        if test_fw:
            self.state.test_firmware_path = test_fw
            self.test_fw_var.set(self._get_display_path(test_fw))

        prod_fw = self._find_recent_firmware('*.blf', contains=prod_contains)
        if prod_fw:
            self.state.production_firmware_path = prod_fw
            self.prod_fw_var.set(self._get_display_path(prod_fw))

    def _find_recent_firmware(self, pattern: str, contains: str = None) -> str:
        """Find most recent firmware file."""
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

    # ------------------------------------------------------------------
    # Configuration + Test launch
    # ------------------------------------------------------------------

    def _run_configuration(self) -> None:
        """Run full device configuration then start test loop."""
        if not self.state.test_firmware_path:
            messagebox.showerror("Error", "Please select test firmware")
            return
        if not self.state.production_firmware_path:
            messagebox.showerror("Error", "Please select production firmware")
            return

        # Stop any existing test runner
        if self._test_runner and self._test_runner.running:
            self._test_runner.stop()

        thread = threading.Thread(target=self._configuration_thread, daemon=True)
        thread.start()

    def _configuration_thread(self) -> None:
        """Configuration worker thread: program device then start test loop."""
        self.terminal.clear()
        self._reset_checkboxes()

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
                log("")
                log("--- Starting production tests ---")
                # Start the test runner loop
                self._start_test_runner()
            else:
                log("❌ Configuration failed")

        except TestWorkflowError as e:
            msg = str(e)
            log(f"❌ Configuration error: {msg}")
            self.frame.after(0, lambda m=msg: messagebox.showerror("Configuration Error", m))

        except Exception as e:
            msg = str(e)
            log(f"❌ Unexpected error: {msg}")
            self.frame.after(0, lambda m=msg: messagebox.showerror("Error", f"Unexpected error: {m}"))

    def _start_test_runner(self) -> None:
        """Create and start the test runner."""
        self._test_runner = TestRunner(
            serial_manager=self.serial_manager,
            state=self.state,
            log_callback=self._on_test_log,
            enable_checkbox_callback=self._on_enable_checkbox,
            check_test_callback=self._on_check_test,
            rf_result_callback=self._on_rf_result,
            pressure_result_callback=self._on_pressure_result,
            tests_complete_callback=self._on_tests_complete,
        )
        self._test_runner.start()

    # ------------------------------------------------------------------
    # Test runner callbacks (called from worker thread -> use frame.after)
    # ------------------------------------------------------------------

    def _on_test_log(self, msg: str) -> None:
        """Log message from test runner."""
        self.terminal.add_line(msg)

    def _on_enable_checkbox(self, test_name: str) -> None:
        """Enable a checkbox for user click (LED tests)."""
        def _enable():
            cb = self.test_checkboxes.get(test_name)
            if cb:
                cb.config(state=NORMAL)
                cb.bind('<Button-1>', self._on_led_checkbox_click)
        self.frame.after(0, _enable)

    def _on_check_test(self, test_name: str, passed: bool) -> None:
        """Mark a test checkbox as checked."""
        def _check():
            var = self.test_vars.get(test_name)
            if var:
                var.set(1 if passed else 0)
            cb = self.test_checkboxes.get(test_name)
            if cb:
                cb.config(state=DISABLED)
        self.frame.after(0, _check)

    def _on_rf_result(self, tech: str, freq: float, power: float) -> None:
        """Update RF measurement labels."""
        def _update():
            label = f"{tech}: Freq = {freq} Hz / Power = {power} dBm"
            if tech == "BLE":
                self.ble_label_var.set(label)
            elif tech in ("LORA", "LoRa"):
                self.lora_label_var.set(label)
        self.frame.after(0, _update)

    def _on_pressure_result(self, value: float, ok: bool) -> None:
        """Update pressure label."""
        def _update():
            self.pressure_label_var.set(f"Pressure = {value:.0f} mbar")
        self.frame.after(0, _update)

    def _on_tests_complete(self) -> None:
        """Handle end of all production tests - generate PDF report."""
        def _complete():
            try:
                # Get device ID from barcode
                device_id = self.state.device_id_bar or self.state.device_id_qr
                if '=' in device_id:
                    device_id = device_id.split('=')[1]

                # Generate PDF report
                report = ReportGenerator(self.state)
                filepath = report.generate(
                    device_id=device_id,
                    test_results=self.state.test_results,
                    operator_name=self.state.operator_name
                )

                self.terminal.add_line(f"📄 Report saved: {filepath}")
                messagebox.showinfo("Saving", f"File saved as {os.path.basename(filepath)}")

            except Exception as e:
                self.terminal.add_line(f"❌ Report error: {e}")
                messagebox.showerror("Report Error", str(e))

        self.frame.after(0, _complete)

    # ------------------------------------------------------------------
    # LED checkbox click handler
    # ------------------------------------------------------------------

    def _on_led_checkbox_click(self, event) -> None:
        """Handle user clicking a LED test checkbox."""
        if self._test_runner:
            # Unbind click from current checkbox
            widget = event.widget
            widget.unbind('<Button-1>')
            # Delegate to test runner (sends 'T' to device, advances)
            self._test_runner.on_led_click()
        # Return "break" to prevent tkinter default toggle
        # (which would un-check the box we just checked)
        return "break"

    # ------------------------------------------------------------------
    # Restart / Reset
    # ------------------------------------------------------------------

    def _restart_test(self) -> None:
        """Restart test without reconfiguring device."""
        # Stop current test runner
        if self._test_runner and self._test_runner.running:
            self._test_runner.stop()

        self._reset_checkboxes()
        self._reset_labels()
        self.terminal.clear()

        # Open serial port if not already open
        if not self.serial_manager.is_open:
            port = self.state.serial_port
            if not port:
                messagebox.showerror("Error", "No serial port selected")
                return
            try:
                self.serial_manager.open(port)
                self.state.set_serial_connected(True, port)
                self.terminal.add_line(f"Serial port {port} opened")
            except Exception as e:
                messagebox.showerror("Error", f"Cannot open serial port: {e}")
                return

        # Send reset commands to device
        try:
            self.serial_manager.write(b'S')
            import time
            time.sleep(1)
            self.serial_manager.write(b'R')
        except Exception:
            pass

        self.terminal.add_line("Test restarted. Waiting for device output...")

        # Start new test runner
        self._start_test_runner()

    def _reset(self) -> None:
        """Reset for new device."""
        # Stop current test runner
        if self._test_runner and self._test_runner.running:
            self._test_runner.stop()

        self._reset_checkboxes()
        self._reset_labels()
        self.state.device_id_qr = ""
        self.state.device_id_bar = ""
        self.state.test_results.clear()

        self.terminal.clear()
        self.terminal.add_line("Ready for new device")

    def _reset_checkboxes(self) -> None:
        """Reset all test checkboxes to unchecked and disabled."""
        for name in TEST_NAMES:
            self.test_vars[name].set(0)
            self.test_checkboxes[name].config(state=DISABLED)
            self.test_checkboxes[name].unbind('<Button-1>')

    def _reset_labels(self) -> None:
        """Reset measurement labels."""
        self.ble_label_var.set("BLE: Freq = ??? Hz / Power = ??? dBm")
        self.lora_label_var.set("LoRa: Freq = ??? Hz / Power = ??? dBm")
        self.pressure_label_var.set("Pressure = ??? mbar")
