"""Terminal tab UI component."""
import threading
import os
from tkinter import (
    Frame, Button, Label, Entry, LabelFrame, StringVar,
    Checkbutton, BooleanVar, IntVar, Listbox, Scrollbar,
    X, BOTH, LEFT, RIGHT, Y, END, VERTICAL
)
from tkinter import filedialog, messagebox

from ui.terminal_widget import TerminalWidget
from services.state_manager import AppState
from core.serial_manager import SerialManager
from core.lynkx_protocol import LYNKXProtocol
from utils.constants import FM_READ_CHUNK_MAX


class TerminalTab:
    """
    Terminal tab for direct serial communication.

    Provides manual command entry, battery reading, file manager,
    logger control, and terminal logging.
    """

    def __init__(
        self,
        parent,
        state: AppState,
        serial_manager: SerialManager,
        protocol: LYNKXProtocol
    ):
        """
        Initialize terminal tab.

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

        self._reader_thread = None
        self._stop_reader = False

        # File manager state
        self.fm_entries = []
        self.fm_selected_id = None

        self._create_ui()

        # Subscribe to serial state changes
        self.state.subscribe('serial_connected', self._on_serial_state_changed)

    def _create_ui(self) -> None:
        """Create tab UI."""
        # ========== CONTROLS FRAME ==========
        controls_frame = Frame(self.frame, bg="white")
        controls_frame.pack(fill=X, padx=5, pady=5)

        # UART command entry
        Label(
            controls_frame,
            text="Commande UART :",
            font=('Helvetica', 10),
            bg="white",
            fg="black"
        ).grid(row=0, column=0, sticky="e", padx=5, pady=2)

        self.uart_entry = Entry(controls_frame, width=50, bg="white", fg="black")
        self.uart_entry.grid(row=0, column=1, columnspan=3, padx=5, pady=2, sticky="ew")
        self.uart_entry.bind('<Return>', lambda e: self._send_command())
        self.uart_entry.bind('<KP_Enter>', lambda e: self._send_command())

        Button(
            controls_frame,
            text="Envoyer",
            command=self._send_command,
            bg="white",
            fg="black"
        ).grid(row=0, column=4, padx=5, pady=2)

        # Battery reading
        Button(
            controls_frame,
            text="Lire Batterie",
            command=self._read_battery,
            bg="white",
            fg="black"
        ).grid(row=1, column=0, padx=5, pady=2)

        self.battery_var = StringVar(value="Batterie: ???")
        Label(
            controls_frame,
            textvariable=self.battery_var,
            font=('Helvetica', 10),
            bg="white",
            fg="black"
        ).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # Terminal logging controls
        log_frame = Frame(controls_frame, bg="white")
        log_frame.grid(row=1, column=2, columnspan=3, sticky="w", padx=5, pady=2)

        self.log_enabled_var = BooleanVar(value=False)
        self.log_path_var = StringVar(value="log.txt")

        Checkbutton(
            log_frame,
            text="Log terminal",
            variable=self.log_enabled_var,
            command=self._toggle_logging,
            bg="white",
            fg="black"
        ).pack(side="left", padx=5)

        Entry(
            log_frame,
            width=40,
            textvariable=self.log_path_var,
            bg="white",
            fg="black"
        ).pack(side="left", padx=5)

        Button(
            log_frame,
            text="Parcourir",
            command=self._select_log_file,
            bg="white",
            fg="black"
        ).pack(side="left", padx=5)

        # ========== FILE MANAGER ==========
        fm_frame = LabelFrame(self.frame, text="File Manager", bg="white", fg="black")
        fm_frame.pack(fill=X, padx=5, pady=5)
        fm_frame.columnconfigure(1, weight=1)
        fm_frame.columnconfigure(2, weight=1)
        fm_frame.columnconfigure(3, weight=1)

        # File list container
        fm_list_container = Frame(fm_frame, bg="white")
        fm_list_container.grid(row=0, column=0, rowspan=4, padx=5, pady=5, sticky="nsew")

        # File count label
        self.fm_count_var = StringVar(value="0 / 0")
        Label(
            fm_list_container,
            textvariable=self.fm_count_var,
            bg="white",
            fg="black"
        ).pack(anchor="w")

        # File listbox with scrollbar
        fm_list_inner = Frame(fm_list_container, bg="white")
        fm_list_inner.pack(fill=BOTH, expand=True)

        self.fm_listbox = Listbox(fm_list_inner, height=8, width=40)
        self.fm_listbox.pack(side=LEFT, fill=BOTH, expand=True)

        fm_scrollbar = Scrollbar(fm_list_inner, orient=VERTICAL, command=self.fm_listbox.yview)
        fm_scrollbar.pack(side=RIGHT, fill=Y)
        self.fm_listbox.configure(yscrollcommand=fm_scrollbar.set)
        self.fm_listbox.bind("<<ListboxSelect>>", self._fm_on_select)

        # File info label
        self.fm_info_var = StringVar(value="Aucun fichier selectionne")
        Label(
            fm_frame,
            textvariable=self.fm_info_var,
            bg="white",
            fg="black",
            anchor="w",
            justify="left"
        ).grid(row=0, column=1, columnspan=3, sticky="w", padx=5, pady=2)

        # Row 1: Lister, Infos, Supprimer
        Button(
            fm_frame,
            text="Lister",
            command=self._fm_refresh_list,
            bg="white",
            fg="black"
        ).grid(row=1, column=1, padx=5, pady=2, sticky="w")

        Button(
            fm_frame,
            text="Infos",
            command=self._fm_show_info,
            bg="white",
            fg="black"
        ).grid(row=1, column=2, padx=5, pady=2, sticky="w")

        Button(
            fm_frame,
            text="Supprimer",
            command=self._fm_delete_selected,
            bg="white",
            fg="black"
        ).grid(row=1, column=3, padx=5, pady=2, sticky="w")

        # Row 2: Telecharger, Tout effacer, Chunk size
        Button(
            fm_frame,
            text="Telecharger",
            command=self._fm_download_selected,
            bg="white",
            fg="black"
        ).grid(row=2, column=1, padx=5, pady=2, sticky="w")

        Button(
            fm_frame,
            text="Tout effacer",
            command=self._fm_erase_all,
            bg="white",
            fg="black"
        ).grid(row=2, column=2, padx=5, pady=2, sticky="w")

        # Chunk size
        chunk_frame = Frame(fm_frame, bg="white")
        chunk_frame.grid(row=2, column=3, padx=5, pady=2, sticky="w")
        Label(chunk_frame, text="Chunk:", bg="white", fg="black").pack(side=LEFT)
        self.fm_chunk_size_var = StringVar(value=str(FM_READ_CHUNK_MAX))
        Entry(chunk_frame, width=6, textvariable=self.fm_chunk_size_var, bg="white", fg="black").pack(side=LEFT)

        # Busy indicator
        self.fm_busy_var = StringVar(value="?")
        self.fm_busy_label = Label(
            fm_frame,
            textvariable=self.fm_busy_var,
            bg="gray",
            fg="white",
            width=15,
            anchor="center",
            font=("Arial", 9, "bold")
        )
        self.fm_busy_label.grid(row=1, column=4, padx=5, pady=2, sticky="ew")

        Button(
            fm_frame,
            text="Check Busy",
            command=self._fm_check_busy,
            bg="white",
            fg="black"
        ).grid(row=2, column=4, padx=5, pady=2, sticky="ew")

        # Debug Info button
        Button(
            fm_frame,
            text="Debug Info",
            command=self._fm_show_debug_info,
            bg="lightblue",
            fg="black",
            font=("Arial", 9, "bold")
        ).grid(row=0, column=4, padx=5, pady=2, sticky="ew")

        # Status and progress
        self.fm_status_var = StringVar(value="Pret")
        Label(
            fm_frame,
            textvariable=self.fm_status_var,
            bg="white",
            fg="black",
            anchor="w"
        ).grid(row=3, column=1, columnspan=2, sticky="w", padx=5, pady=2)

        self.fm_progress_var = StringVar(value="")
        Label(
            fm_frame,
            textvariable=self.fm_progress_var,
            bg="white",
            fg="black",
            anchor="w"
        ).grid(row=3, column=3, sticky="w", padx=5, pady=2)

        # ========== LOGGER CONTROL ==========
        logger_frame = LabelFrame(self.frame, text="Logger Control", bg="white", fg="black")
        logger_frame.pack(fill=X, padx=5, pady=5)

        Button(
            logger_frame,
            text="▶️ Start Logger",
            command=self._logger_start,
            bg="lightgreen",
            fg="black",
            font=("Arial", 10, "bold"),
            width=15
        ).pack(side=LEFT, padx=5, pady=5)

        Button(
            logger_frame,
            text="⏸️ Stop Logger",
            command=self._logger_stop,
            bg="orange",
            fg="black",
            font=("Arial", 10, "bold"),
            width=15
        ).pack(side=LEFT, padx=5, pady=5)

        Button(
            logger_frame,
            text="📊 Logger Status",
            command=self._logger_status,
            bg="lightblue",
            fg="black",
            font=("Arial", 10, "bold"),
            width=15
        ).pack(side=LEFT, padx=5, pady=5)

        # ========== TERMINAL CONTROLS ==========
        terminal_controls = Frame(self.frame, bg="white")
        terminal_controls.pack(fill=X, padx=5, pady=2)

        # Serial control buttons
        Button(
            terminal_controls,
            text="Open serial",
            command=self._open_serial,
            bg="white",
            fg="black"
        ).pack(side=LEFT, padx=2)

        Button(
            terminal_controls,
            text="Close serial",
            command=self._close_serial,
            bg="white",
            fg="black"
        ).pack(side=LEFT, padx=2)

        Button(
            terminal_controls,
            text="Clear Terminal",
            command=self._clear_terminal,
            bg="white",
            fg="black"
        ).pack(side=LEFT, padx=2)

        # Separator
        Frame(terminal_controls, width=20, bg="white").pack(side=LEFT)

        # Search functionality
        Label(
            terminal_controls,
            text="Recherche:",
            bg="white",
            fg="black"
        ).pack(side=LEFT, padx=2)

        self.search_var = StringVar()
        self.search_entry = Entry(
            terminal_controls,
            textvariable=self.search_var,
            width=20,
            bg="white",
            fg="black"
        )
        self.search_entry.pack(side=LEFT, padx=2)
        self.search_entry.bind('<Return>', lambda e: self._search_next())
        self.search_entry.bind('<KP_Enter>', lambda e: self._search_next())
        self.search_entry.bind('<KeyRelease>', lambda e: self._search_terminal())

        Button(
            terminal_controls,
            text="Suivant",
            command=self._search_next,
            bg="white",
            fg="black"
        ).pack(side=LEFT, padx=2)

        Button(
            terminal_controls,
            text="Precedent",
            command=self._search_prev,
            bg="white",
            fg="black"
        ).pack(side=LEFT, padx=2)

        self.search_result_var = StringVar(value="")
        Label(
            terminal_controls,
            textvariable=self.search_result_var,
            bg="white",
            fg="gray"
        ).pack(side=LEFT, padx=5)

        # ========== TERMINAL ==========
        self.terminal = TerminalWidget(self.frame, enable_log=True)

        # Search state
        self._search_matches = []
        self._search_index = -1

    # ==================== SERIAL STATE HANDLING ====================

    def _on_serial_state_changed(self, data: dict) -> None:
        """Handle serial connection state change from any source."""
        connected = data.get('connected', False)
        port = data.get('port', '')

        if connected:
            # Serial opened (possibly from another tab like Update)
            # Start reader loop if not already running
            if self._reader_thread is None or not self._reader_thread.is_alive():
                self._stop_reader = False
                self._reader_thread = threading.Thread(
                    target=self._reader_loop,
                    daemon=True
                )
                self._reader_thread.start()
                self.terminal.add_line(f"✓ Lecture série activée ({port})")
        else:
            # Serial closed
            self._stop_reader = True
            # Close log file if enabled
            if self.log_enabled_var.get():
                self.terminal.close_log_file()
                self.log_enabled_var.set(False)
                self.terminal.add_line("✓ Log fermé")

    # ==================== UART COMMANDS ====================

    def _send_command(self) -> None:
        """Send UART command."""
        command = self.uart_entry.get().strip()
        if not command:
            return

        if not self.serial_manager.is_open:
            messagebox.showerror("Erreur", "Port série non ouvert")
            return

        thread = threading.Thread(
            target=self._send_command_thread,
            args=(command,),
            daemon=True
        )
        thread.start()

    def _send_command_thread(self, command: str) -> None:
        """Send command in background thread."""
        try:
            self.terminal.add_line(f"> {command}")

            if command.startswith('@'):
                hex_data = command[1:].replace(' ', '')
                payload = bytes.fromhex(hex_data)
                success, response = self.protocol.send_packet(payload)

                if success:
                    if response:
                        self.terminal.add_line(f"← {response.hex()}")
                    else:
                        self.terminal.add_line("← (pas de réponse)")
                else:
                    self.terminal.add_line("✗ Commande échouée")
            else:
                self.serial_manager.write(command.encode() + b'\n')
                self.terminal.add_line("✓ Envoyé")

        except ValueError as e:
            self.terminal.add_line(f"✗ Hex invalide: {e}")
        except Exception as e:
            self.terminal.add_line(f"✗ Erreur: {e}")

    # ==================== SERIAL CONTROL ====================

    def _open_serial(self) -> None:
        """Open serial port and start reading."""
        if self.serial_manager.is_open:
            # Port already open - just make sure reader is running
            if self._reader_thread is None or not self._reader_thread.is_alive():
                self._stop_reader = False
                self._reader_thread = threading.Thread(
                    target=self._reader_loop,
                    daemon=True
                )
                self._reader_thread.start()
                self.terminal.add_line("✓ Lecture série activée")
            else:
                self.terminal.add_line("Port série déjà ouvert")
            return

        port = self.state.serial_port
        if not port or port == "Aucun port":
            messagebox.showerror("Erreur", "Aucun port sélectionné")
            return

        try:
            self.serial_manager.open(port)
            # This will trigger _on_serial_state_changed which starts the reader
            self.state.set_serial_connected(True, port)
            self.terminal.add_line(f"✓ Connexion série sur {port} établie")

        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le port: {e}")
            self.terminal.add_line(f"✗ Erreur ouverture: {e}")

    def _close_serial(self) -> None:
        """Close serial port."""
        if not self.serial_manager.is_open:
            self.terminal.add_line("Port série non ouvert")
            return

        # Stop reader first (non-blocking)
        self._stop_reader = True

        # Close port (this will cause reader to exit)
        try:
            self.serial_manager.close()
        except Exception:
            pass  # Port may already be closed

        # Update state
        self.state.set_serial_connected(False)
        self.terminal.add_line("✓ Port série fermé")

    def _reader_loop(self) -> None:
        """Read serial data continuously."""
        import time
        while not self._stop_reader and self.serial_manager.is_open:
            try:
                # Wait while in exclusive mode (firmware update, etc.)
                if self.serial_manager.exclusive_mode:
                    time.sleep(0.5)
                    continue

                # Wait while command is in progress
                if self.serial_manager.command_in_progress:
                    time.sleep(0.05)
                    continue

                # Read available data with short timeout
                data = self.serial_manager.read(1)
                if data:
                    # Read remaining available bytes
                    buffer = data
                    while True:
                        byte = self.serial_manager.read(1)
                        if not byte:
                            break
                        buffer += byte
                        if byte == b'\n':
                            break

                    # Decode and display
                    try:
                        text = buffer.decode('utf-8', errors='ignore').strip()
                        if text:
                            self.terminal.add_line(text)
                    except Exception:
                        self.terminal.add_line(f"<{buffer.hex()}>")

            except Exception as e:
                if not self._stop_reader:
                    self.terminal.add_line(f"Erreur lecture: {e}")
                break

    def _clear_terminal(self) -> None:
        """Clear terminal output."""
        self.terminal.clear()
        self._search_matches = []
        self._search_index = -1
        self.search_result_var.set("")

    def _search_terminal(self) -> None:
        """Search for text in terminal and highlight matches."""
        search_text = self.search_var.get().strip()
        if not search_text:
            self._search_matches = []
            self._search_index = -1
            self.search_result_var.set("")
            self.terminal.text.tag_remove("search", "1.0", END)
            return

        # Clear previous highlights
        self.terminal.text.tag_remove("search", "1.0", END)
        self.terminal.text.tag_remove("current_match", "1.0", END)

        # Configure search tags
        self.terminal.text.tag_configure("search", background="yellow")
        self.terminal.text.tag_configure("current_match", background="orange")

        # Find all matches
        self._search_matches = []
        start_pos = "1.0"
        while True:
            pos = self.terminal.text.search(
                search_text,
                start_pos,
                stopindex=END,
                nocase=True
            )
            if not pos:
                break
            end_pos = f"{pos}+{len(search_text)}c"
            self._search_matches.append((pos, end_pos))
            self.terminal.text.tag_add("search", pos, end_pos)
            start_pos = end_pos

        if self._search_matches:
            self._search_index = 0
            self._highlight_current_match()
            self.search_result_var.set(f"1/{len(self._search_matches)}")
        else:
            self._search_index = -1
            self.search_result_var.set("Aucun resultat")

    def _highlight_current_match(self) -> None:
        """Highlight the current search match."""
        if not self._search_matches or self._search_index < 0:
            return

        # Clear current match highlight
        self.terminal.text.tag_remove("current_match", "1.0", END)

        # Highlight current match
        pos, end_pos = self._search_matches[self._search_index]
        self.terminal.text.tag_add("current_match", pos, end_pos)

        # Scroll to make match visible
        self.terminal.text.see(pos)

    def _search_next(self) -> None:
        """Go to next search match."""
        search_text = self.search_var.get().strip()
        if not search_text:
            return

        # If search text changed, re-search
        if not self._search_matches or self._search_index < 0:
            self._search_terminal()
            return

        if self._search_matches:
            self._search_index = (self._search_index + 1) % len(self._search_matches)
            self._highlight_current_match()
            self.search_result_var.set(f"{self._search_index + 1}/{len(self._search_matches)}")

    def _search_prev(self) -> None:
        """Go to previous search match."""
        search_text = self.search_var.get().strip()
        if not search_text:
            return

        # If search text changed, re-search
        if not self._search_matches or self._search_index < 0:
            self._search_terminal()
            return

        if self._search_matches:
            self._search_index = (self._search_index - 1) % len(self._search_matches)
            self._highlight_current_match()
            self.search_result_var.set(f"{self._search_index + 1}/{len(self._search_matches)}")

    def _read_battery(self) -> None:
        """Read battery level."""
        if not self.serial_manager.is_open:
            messagebox.showerror("Erreur", "Port série non ouvert")
            return

        thread = threading.Thread(target=self._read_battery_thread, daemon=True)
        thread.start()

    def _read_battery_thread(self) -> None:
        """Read battery in background thread."""
        try:
            level = self.protocol.read_battery_level()

            if level is not None:
                self.battery_var.set(f"Batterie: {level}%")
                self.terminal.add_line(f"Niveau batterie: {level}%")
                self.state.set_battery_level(level)
            else:
                self.battery_var.set("Batterie: Erreur")
                self.terminal.add_line("Échec lecture batterie")

        except Exception as e:
            self.terminal.add_line(f"Erreur batterie: {e}")

    # ==================== TERMINAL LOGGING ====================

    def _toggle_logging(self) -> None:
        """Toggle terminal logging."""
        enabled = self.log_enabled_var.get()

        if enabled:
            # Resolve path (convert relative to absolute)
            path = self._resolve_log_path()

            # Open log file (set_log_file handles file opening)
            self.terminal.set_log_file(path, enabled=True)

            # Check if file was opened successfully
            if not self.terminal.log_file_enabled:
                self.log_enabled_var.set(False)
                messagebox.showerror("Log terminal", f"Impossible d'ouvrir le fichier:\n{path}")
                return

            self.terminal.add_line(f"✓ Log activé: {path}")
        else:
            # Close and flush log file
            self.terminal.close_log_file()
            self.terminal.add_line("✓ Log désactivé")

    def _resolve_log_path(self) -> str:
        """Resolve log path (convert relative to absolute)."""
        path = self.log_path_var.get().strip()
        if not path:
            path = "log.txt"
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        return path

    def _select_log_file(self) -> None:
        """Select log file."""
        path = filedialog.asksaveasfilename(
            title="Choisir un fichier de log",
            defaultextension=".txt",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")]
        )
        if path:
            self.log_path_var.set(path)
            # Re-toggle logging if already enabled to use new path
            if self.log_enabled_var.get():
                self._toggle_logging()

    # ==================== FILE MANAGER ====================

    def _fm_on_select(self, event) -> None:
        """Handle file selection in listbox."""
        selection = self.fm_listbox.curselection()
        if selection and self.fm_entries:
            idx = selection[0]
            if idx < len(self.fm_entries):
                entry = self.fm_entries[idx]
                self.fm_selected_id = entry.get('id')
                self.fm_info_var.set(f"ID: {entry.get('id')} - {entry.get('name', 'N/A')}")

    def _fm_refresh_list(self) -> None:
        """Refresh file list from device."""
        if not self.serial_manager.is_open:
            messagebox.showerror("Erreur", "Port série non ouvert")
            return

        self.fm_status_var.set("Chargement...")
        thread = threading.Thread(target=self._fm_refresh_list_thread, daemon=True)
        thread.start()

    def _fm_refresh_list_thread(self) -> None:
        """Refresh file list in background."""
        try:
            count = self.protocol.get_log_count()
            if count is None:
                self.fm_status_var.set("Erreur lecture")
                return

            self.fm_count_var.set(f"0 / {count}")
            self.fm_listbox.delete(0, END)
            self.fm_entries = []

            # TODO: Implement full file list retrieval
            self.fm_status_var.set(f"Pret - {count} fichiers")

        except Exception as e:
            self.fm_status_var.set(f"Erreur: {e}")

    def _fm_show_info(self) -> None:
        """Show info for selected file."""
        if self.fm_selected_id is None:
            messagebox.showinfo("Info", "Aucun fichier sélectionné")
            return
        # TODO: Implement file info display
        self.terminal.add_line(f"Info fichier ID: {self.fm_selected_id}")

    def _fm_delete_selected(self) -> None:
        """Delete selected file."""
        if self.fm_selected_id is None:
            messagebox.showinfo("Info", "Aucun fichier sélectionné")
            return
        # TODO: Implement file deletion
        self.terminal.add_line(f"Suppression fichier ID: {self.fm_selected_id}")

    def _fm_download_selected(self) -> None:
        """Download selected file."""
        if self.fm_selected_id is None:
            messagebox.showinfo("Info", "Aucun fichier sélectionné")
            return
        # TODO: Implement file download
        self.terminal.add_line(f"Téléchargement fichier ID: {self.fm_selected_id}")

    def _fm_erase_all(self) -> None:
        """Erase all files."""
        if not messagebox.askyesno("Confirmation", "Effacer tous les fichiers ?"):
            return
        # TODO: Implement erase all
        self.terminal.add_line("Effacement de tous les fichiers...")

    def _fm_check_busy(self) -> None:
        """Check if device is busy."""
        if not self.serial_manager.is_open:
            self.fm_busy_var.set("?")
            return
        # TODO: Implement busy check
        self.fm_busy_var.set("Ready")
        self.fm_busy_label.configure(bg="green")

    def _fm_show_debug_info(self) -> None:
        """Show debug info."""
        # TODO: Implement debug info
        self.terminal.add_line("Debug info demandé...")

    # ==================== LOGGER CONTROL ====================

    def _logger_start(self) -> None:
        """Start data logger."""
        if not self.serial_manager.is_open:
            messagebox.showerror("Erreur", "Port série non ouvert")
            return

        thread = threading.Thread(target=self._logger_start_thread, daemon=True)
        thread.start()

    def _logger_start_thread(self) -> None:
        """Start logger in background."""
        try:
            success = self.protocol.start_logger(log_type=0)
            if success:
                self.terminal.add_line("✓ Logger démarré")
            else:
                self.terminal.add_line("✗ Échec démarrage logger")
        except Exception as e:
            self.terminal.add_line(f"Erreur logger: {e}")

    def _logger_stop(self) -> None:
        """Stop data logger."""
        if not self.serial_manager.is_open:
            messagebox.showerror("Erreur", "Port série non ouvert")
            return

        thread = threading.Thread(target=self._logger_stop_thread, daemon=True)
        thread.start()

    def _logger_stop_thread(self) -> None:
        """Stop logger in background."""
        try:
            success = self.protocol.stop_logger()
            if success:
                self.terminal.add_line("✓ Logger arrêté")
            else:
                self.terminal.add_line("✗ Échec arrêt logger")
        except Exception as e:
            self.terminal.add_line(f"Erreur logger: {e}")

    def _logger_status(self) -> None:
        """Get logger status."""
        if not self.serial_manager.is_open:
            messagebox.showerror("Erreur", "Port série non ouvert")
            return

        thread = threading.Thread(target=self._logger_status_thread, daemon=True)
        thread.start()

    def _logger_status_thread(self) -> None:
        """Get logger status in background."""
        try:
            status = self.protocol.get_logger_status()
            if status:
                running = "En cours" if status.get('running') else "Arrêté"
                self.terminal.add_line(f"Logger: {running}")
            else:
                self.terminal.add_line("✗ Échec lecture status logger")
        except Exception as e:
            self.terminal.add_line(f"Erreur logger: {e}")
