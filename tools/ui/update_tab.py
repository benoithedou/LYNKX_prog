"""Update tab UI component."""
import threading
import os
import glob
from tkinter import Frame, Button, Label, StringVar, LabelFrame, Checkbutton, BooleanVar
from tkinter import filedialog, messagebox

from ui.terminal_widget import TerminalWidget
from services.state_manager import AppState
from services.test_workflow import TestWorkflow, TestWorkflowError
from core.serial_manager import SerialManager
from core.lynkx_protocol import LYNKXProtocol
from firmware.encryption import FirmwareEncryption


class UpdateTab:
    """
    Update tab for firmware updates.

    Handles firmware selection, encryption, and device updates.
    """

    # Firmware source paths
    FIRMWARE_SOURCE_PATH_14 = '/Volumes/LYNKX_drive/rep/LYNKX_firmware/output/LYNKX_firmware_HARD_14_Debug.bin'
    FIRMWARE_SOURCE_PATH_12 = '/Volumes/LYNKX_drive/rep/LYNKX_firmware/output/LYNKX_firmware_HARD_12_Debug.bin'

    def __init__(
        self,
        parent,
        state: AppState,
        serial_manager: SerialManager,
        protocol: LYNKXProtocol
    ):
        """
        Initialize update tab.

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

        # Update thread management
        self._update_thread = None
        self._update_stop_flag = False

        self._create_ui()

        # Auto-select default firmwares
        self._auto_select_firmwares()

        # Subscribe to hardware version changes
        self.state.subscribe('hardware_version', self._on_hw_version_changed)

    def _create_ui(self) -> None:
        """Create tab UI."""
        # Firmware selection
        self.update_fw_var = StringVar()
        self.backup_fw_var = StringVar()

        Button(
            self.frame,
            text="Firmware file",
            command=self._select_update_firmware,
            bg="white",
            fg="black"
        ).grid(row=0, column=0, pady=10, padx=5)

        Label(
            self.frame,
            textvariable=self.update_fw_var,
            bg="white",
            fg="black"
        ).grid(row=0, column=1, sticky="w")

        # Backup firmware selection
        Button(
            self.frame,
            text="Backup file",
            command=self._select_backup_firmware,
            bg="white",
            fg="black"
        ).grid(row=1, column=0, pady=10, padx=5)

        self.backup_label = Label(
            self.frame,
            textvariable=self.backup_fw_var,
            bg="white",
            fg="black"
        )
        self.backup_label.grid(row=1, column=1, sticky="w")

        # Options frame (right column)
        options_frame = Frame(self.frame, bg="white")
        options_frame.grid(row=0, column=2, rowspan=2, padx=20, sticky="nw")

        # Write config checkbox (linked to backup - config is in external flash)
        # If backup is written, external flash is erased so config must be written too
        self.en_config_var = BooleanVar(value=True)
        self.config_checkbox = Checkbutton(
            options_frame,
            text="Write config",
            variable=self.en_config_var,
            bg="white",
            fg="black",
            state="disabled"  # Disabled initially since backup is enabled by default
        )
        self.config_checkbox.pack(anchor="w")

        # Write backup checkbox
        self.en_backup_var = BooleanVar(value=True)
        Checkbutton(
            options_frame,
            text="Write backup",
            variable=self.en_backup_var,
            bg="white",
            fg="black",
            command=self._on_backup_toggle
        ).pack(anchor="w")

        # Action buttons
        Button(
            self.frame,
            text="Update Firmware",
            command=self._run_update,
            bg="lightblue",
            fg="black",
            font=('Helvetica', 12, 'bold')
        ).grid(row=2, column=0, pady=10, padx=5)

        Button(
            self.frame,
            text="Encrypt Firmware",
            command=self._run_encryption,
            bg="lightyellow",
            fg="black",
            font=('Helvetica', 12, 'bold')
        ).grid(row=2, column=1, pady=10, padx=5)

        # Terminal
        terminal_frame = LabelFrame(
            self.frame,
            text="Terminal",
            bg="white",
            fg="black"
        )
        terminal_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        self.terminal = TerminalWidget(terminal_frame, enable_log=False)

        # Configure grid weights
        self.frame.rowconfigure(3, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)

    def _select_update_firmware(self) -> None:
        """Select firmware for update."""
        path = filedialog.askopenfilename(
            title="Select Update Firmware",
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")]
        )
        if path:
            self.state.update_firmware_path = path
            self.update_fw_var.set(self._get_display_path(path))

    def _select_backup_firmware(self) -> None:
        """Select backup firmware."""
        path = filedialog.askopenfilename(
            title="Select Backup Firmware",
            filetypes=[("BLF files", "*.blf"), ("All files", "*.*")]
        )
        if path:
            self.state.backup_firmware_path = path
            self.backup_fw_var.set(self._get_display_path(path))

    def _on_backup_toggle(self) -> None:
        """Handle backup checkbox toggle."""
        enabled = self.en_backup_var.get()
        # Visual feedback - gray out label when disabled
        if enabled:
            self.backup_label.configure(fg="black")
            # If backup is enabled, config must be enabled too (external flash will be erased)
            self.en_config_var.set(True)
            self.config_checkbox.configure(state="disabled")
        else:
            self.backup_label.configure(fg="gray")
            # Re-enable config checkbox when backup is disabled
            self.config_checkbox.configure(state="normal")

    def _run_update(self) -> None:
        """Run firmware update."""
        if not self.state.update_firmware_path:
            messagebox.showerror("Erreur", "Veuillez sélectionner un firmware")
            return

        # Only require backup firmware if checkbox is checked
        if self.en_backup_var.get() and not self.state.backup_firmware_path:
            messagebox.showerror("Erreur", "Veuillez sélectionner un firmware de backup")
            return

        # Stop previous update if running
        if self._update_thread and self._update_thread.is_alive():
            self._update_stop_flag = True
            self.terminal.add_line("⚠️ Interruption de la mise à jour précédente...")
            # Close serial to force thread to stop
            if self.serial_manager.is_open:
                self.serial_manager.close()
                self.state.set_serial_connected(False)
            # Wait for thread to finish (with timeout)
            self._update_thread.join(timeout=2.0)

        # Reset stop flag and start new update
        self._update_stop_flag = False
        self._update_thread = threading.Thread(target=self._update_worker, daemon=True)
        self._update_thread.start()

    def _update_worker(self) -> None:
        """Update worker thread."""
        self.terminal.clear()

        def log(msg: str):
            if not self._update_stop_flag:
                self.terminal.add_line(msg)

        try:
            # Check if stopped before starting
            if self._update_stop_flag:
                return

            workflow = TestWorkflow(
                self.serial_manager,
                self.state,
                progress_callback=log
            )

            # Pass backup path only if checkbox is checked
            backup_path = self.state.backup_firmware_path if self.en_backup_var.get() else None
            write_config = self.en_config_var.get()

            success = workflow.run_firmware_update(
                self.state.update_firmware_path,
                backup_path,
                write_config
            )

            # Check if stopped - don't show result messages
            if self._update_stop_flag:
                return

            if success:
                log("✅ Update successful!")
                self.frame.after(0, lambda: messagebox.showinfo("Success", "Firmware update complete!"))
            else:
                log("❌ Update failed")
                self.frame.after(0, lambda: messagebox.showerror("Error", "Firmware update failed"))

        except TestWorkflowError as e:
            if not self._update_stop_flag:
                log(f"❌ Update error: {str(e)}")
                self.frame.after(0, lambda err=str(e): messagebox.showerror("Update Error", err))

        except Exception as e:
            if not self._update_stop_flag:
                log(f"❌ Unexpected error: {str(e)}")
                self.frame.after(0, lambda err=str(e): messagebox.showerror("Error", f"Unexpected error: {err}"))

        finally:
            # Close serial port at end of update
            try:
                if self.serial_manager.is_open:
                    self.serial_manager.close()
                    self.state.set_serial_connected(False)
                    log("🔌 Port série fermé")
            except Exception:
                pass  # Port may already be closed

    def _run_encryption(self) -> None:
        """Run firmware encryption."""
        if not self.state.update_firmware_path:
            messagebox.showerror("Error", "Please select firmware to encrypt")
            return

        thread = threading.Thread(target=self._encryption_thread, daemon=True)
        thread.start()

    def _encryption_thread(self) -> None:
        """Encryption worker thread."""
        self.terminal.clear()

        def log(msg: str):
            self.terminal.add_line(msg)

        try:
            log("🔒 Encrypting firmware...")
            log(f"Input: {self.state.update_firmware_path}")

            # Get firmwares directory
            tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            parent_dir = os.path.dirname(tools_dir)
            output_dir = os.path.join(parent_dir, 'firmwares')

            success, output_path, message = FirmwareEncryption.encrypt_firmware(
                self.state.update_firmware_path,
                output_dir
            )

            if success:
                log("✅ Encryption successful!")
                log(message)
                # Refresh firmware selection to pick up newly encrypted file
                self.frame.after(0, self._auto_select_firmwares)
                self.frame.after(0, lambda msg=message: messagebox.showinfo("Success", msg))
            else:
                log(f"❌ Encryption failed: {message}")
                self.frame.after(0, lambda msg=message: messagebox.showerror("Error", msg))

        except Exception as e:
            log(f"❌ Encryption error: {str(e)}")
            self.frame.after(0, lambda err=str(e): messagebox.showerror("Error", f"Encryption failed: {err}"))

    def _on_hw_version_changed(self, data: dict) -> None:
        """Handle hardware version change."""
        self._auto_select_firmwares()

    def _auto_select_firmwares(self) -> None:
        """Auto-select default firmwares based on hardware version."""
        hw_version = self.state.hardware_version

        # Get firmwares directory
        tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parent_dir = os.path.dirname(tools_dir)
        firmwares_dir = os.path.join(parent_dir, 'firmwares')

        if hw_version == "1.04":
            # Backup firmware - most recent .blf containing LYNKXF_01.04
            backup_path = self._find_recent_file(firmwares_dir, '*.blf', 'LYNKXF_01.04')
            # Update firmware - from source path
            update_path = self.FIRMWARE_SOURCE_PATH_14
        else:
            # HW 1.02
            backup_path = self._find_recent_file(firmwares_dir, '*.blf', 'LYNKXF_01.02')
            update_path = self.FIRMWARE_SOURCE_PATH_12

        # Set backup firmware
        if backup_path and os.path.exists(backup_path):
            self.state.backup_firmware_path = backup_path
            self.backup_fw_var.set(self._get_display_path(backup_path))

        # Set update firmware
        if update_path and os.path.exists(update_path):
            self.state.update_firmware_path = update_path
            self.update_fw_var.set(self._get_display_path(update_path))

    def _find_recent_file(self, directory: str, pattern: str, contains: str = None) -> str:
        """
        Find most recent file matching pattern.

        Args:
            directory: Directory to search
            pattern: Glob pattern (e.g., '*.blf')
            contains: Optional string that filename must contain

        Returns:
            Path to most recent file or empty string
        """
        search_path = os.path.join(directory, pattern)
        files = glob.glob(search_path)

        if contains:
            files = [f for f in files if contains in os.path.basename(f)]

        if not files:
            return ""

        # Sort by modification time, return most recent
        files_sorted = sorted(files, key=lambda x: os.path.getmtime(x))
        return files_sorted[-1] if files_sorted else ""

    def _get_display_path(self, path: str) -> str:
        """Get display path showing parent_dir/filename."""
        parent_dir = os.path.basename(os.path.dirname(path))
        file_name = os.path.basename(path)
        return f"{parent_dir}/{file_name}"
