"""Update tab UI component."""
import threading
import os
import glob
from tkinter import Frame, Button, Label, StringVar, IntVar, LabelFrame, Checkbutton, BooleanVar, Spinbox
from tkinter import filedialog, messagebox
from tkinter import ttk

from ui.terminal_widget import TerminalWidget
from services.state_manager import AppState
from services.test_workflow import TestWorkflow, TestWorkflowError
from core.serial_manager import SerialManager
from core.lynkx_protocol import LYNKXProtocol
from firmware.encryption import FirmwareEncryption
from device.config import BeaconSettings, UserSettings
from device.bootloader import Bootloader
from utils.constants import BEACON_SETTINGS_ADDRESS, USER_SETTINGS_ADDRESS


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

        # Write settings checkbox (beacon + user settings after programming)
        self.en_write_settings_var = BooleanVar(value=True)
        Checkbutton(
            options_frame,
            text="Write settings",
            variable=self.en_write_settings_var,
            bg="white",
            fg="black"
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

        # --- Beacon Settings (production config) ---
        beacon_frame = LabelFrame(self.frame, text="Beacon Settings", bg="white", fg="black")
        beacon_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=2)

        self.beacon_ble_scanner_var = BooleanVar(value=False)
        self.beacon_gnss_var = BooleanVar(value=True)
        self.beacon_p2p_var = BooleanVar(value=True)
        self.beacon_lora_repeater_var = BooleanVar(value=False)
        self.beacon_notification_var = BooleanVar(value=True)
        self.beacon_auto_pwr_off_var = BooleanVar(value=False)
        self.beacon_auto_pwr_off_delay_var = IntVar(value=0)

        Checkbutton(beacon_frame, text="BLE Scanner", variable=self.beacon_ble_scanner_var,
                    bg="white", fg="black", selectcolor="white").grid(row=0, column=0, padx=5, sticky="w")
        Checkbutton(beacon_frame, text="GNSS", variable=self.beacon_gnss_var,
                    bg="white", fg="black", selectcolor="white").grid(row=0, column=1, padx=5, sticky="w")
        Checkbutton(beacon_frame, text="P2P", variable=self.beacon_p2p_var,
                    bg="white", fg="black", selectcolor="white").grid(row=0, column=2, padx=5, sticky="w")
        Checkbutton(beacon_frame, text="LoRa Repeater", variable=self.beacon_lora_repeater_var,
                    bg="white", fg="black", selectcolor="white").grid(row=0, column=3, padx=5, sticky="w")
        Checkbutton(beacon_frame, text="Notification", variable=self.beacon_notification_var,
                    bg="white", fg="black", selectcolor="white").grid(row=1, column=0, padx=5, sticky="w")
        Checkbutton(beacon_frame, text="Auto Power Off", variable=self.beacon_auto_pwr_off_var,
                    bg="white", fg="black", selectcolor="white").grid(row=1, column=1, padx=5, sticky="w")
        Label(beacon_frame, text="Delay (min):", bg="white", fg="black").grid(row=1, column=2, padx=2, sticky="e")
        Spinbox(beacon_frame, from_=0, to=65535, width=6, textvariable=self.beacon_auto_pwr_off_delay_var,
                bg="white", fg="black").grid(row=1, column=3, padx=5, sticky="w")

        # --- User Settings ---
        user_frame = LabelFrame(self.frame, text="User Settings", bg="white", fg="black")
        user_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=2)

        self.user_inactivity_var = StringVar(value="Off")
        self.user_power_profile_var = StringVar(value="Balanced")
        self.user_power_on_charging_var = BooleanVar(value=True)

        Label(user_frame, text="Inactivity:", bg="white", fg="black").grid(row=0, column=0, padx=2, sticky="e")
        ttk.Combobox(user_frame, textvariable=self.user_inactivity_var, width=8,
                     values=["Off", "30s", "60s", "120s", "180s", "300s"],
                     state="readonly").grid(row=0, column=1, padx=5, sticky="w")
        Label(user_frame, text="Power Profile:", bg="white", fg="black").grid(row=0, column=2, padx=2, sticky="e")
        ttk.Combobox(user_frame, textvariable=self.user_power_profile_var, width=10,
                     values=["Perf", "Balanced", "Eco", "Eco2"],
                     state="readonly").grid(row=0, column=3, padx=5, sticky="w")
        Checkbutton(user_frame, text="Power On Charging", variable=self.user_power_on_charging_var,
                    bg="white", fg="black", selectcolor="white").grid(row=0, column=4, padx=5, sticky="w")

        # --- Write Config standalone button ---
        Button(
            self.frame,
            text="Write Config",
            command=self._run_write_config,
            bg="lightyellow",
            fg="black"
        ).grid(row=5, column=0, pady=5, padx=5)

        # Terminal
        terminal_frame = LabelFrame(
            self.frame,
            text="Terminal",
            bg="white",
            fg="black"
        )
        terminal_frame.grid(row=6, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)

        self.terminal = TerminalWidget(terminal_frame, enable_log=False)

        # Configure grid weights
        self.frame.rowconfigure(6, weight=1)
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

    def _build_beacon_settings(self) -> BeaconSettings:
        """Build BeaconSettings from UI variables."""
        return BeaconSettings(
            ble_scanner=int(self.beacon_ble_scanner_var.get()),
            gnss_en=int(self.beacon_gnss_var.get()),
            p2p_en=int(self.beacon_p2p_var.get()),
            lora_repeater=int(self.beacon_lora_repeater_var.get()),
            notification_en=int(self.beacon_notification_var.get()),
            auto_power_off_en=int(self.beacon_auto_pwr_off_var.get()),
            auto_power_off_delay=self.beacon_auto_pwr_off_delay_var.get()
        )

    def _build_user_settings(self) -> UserSettings:
        """Build UserSettings from UI variables."""
        return UserSettings(
            inactivity_duration=UserSettings.INACTIVITY_MAP.get(self.user_inactivity_var.get(), 0),
            power_profile=UserSettings.PROFILE_MAP.get(self.user_power_profile_var.get(), 1),
            power_on_charging=int(self.user_power_on_charging_var.get())
        )

    def _run_write_config(self) -> None:
        """Run standalone config write."""
        thread = threading.Thread(target=self._write_config_worker, daemon=True)
        thread.start()

    def _write_config_worker(self) -> None:
        """Write config worker thread."""
        self.terminal.clear()

        def log(msg: str):
            self.terminal.add_line(msg)

        try:
            log("--- Write Config ---")

            # Open serial if needed
            if not self.serial_manager.is_open:
                port = self.state.serial_port
                if not port:
                    raise Exception("No serial port selected")
                log(f"🔌 Opening {port}...")
                self.serial_manager.open(port)
                self.state.set_serial_connected(True, port)

            # Wait for device
            log("⏳ Waiting for LYNKX+...")
            if not self.serial_manager.wait_for_device(timeout=10.0):
                raise Exception("Device not detected")
            log("✅ LYNKX+ connected")

            self.serial_manager.set_timeout(4.0)
            bootloader = Bootloader(self.serial_manager)

            # Write beacon settings
            beacon = self._build_beacon_settings()
            log(f"⚙️  Writing beacon settings @ 0x{BEACON_SETTINGS_ADDRESS:08X}...")
            bootloader.write_external_memory(beacon.to_bytes(), address=BEACON_SETTINGS_ADDRESS)
            log("✓ Beacon settings written")

            # Write user settings
            user = self._build_user_settings()
            log(f"⚙️  Writing user settings @ 0x{USER_SETTINGS_ADDRESS:08X}...")
            bootloader.write_external_memory(user.to_bytes(), address=USER_SETTINGS_ADDRESS)
            log("✓ User settings written")

            log("--- Config written ---")

        except Exception as e:
            log(f"❌ Error: {str(e)}")

        finally:
            try:
                if self.serial_manager.is_open:
                    self.serial_manager.close()
                    self.state.set_serial_connected(False)
                    log("🔌 Port closed")
            except Exception:
                pass

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

            # Build settings from UI if write settings is enabled
            beacon_settings = self._build_beacon_settings() if self.en_write_settings_var.get() else None
            user_settings = self._build_user_settings() if self.en_write_settings_var.get() else None

            success = workflow.run_firmware_update(
                self.state.update_firmware_path,
                backup_path,
                write_config,
                beacon_settings,
                user_settings
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
