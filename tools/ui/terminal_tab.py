"""Terminal tab UI component."""
import struct
import threading
import os
import time
from datetime import datetime
from tkinter import (
    Frame, Button, Label, Entry, LabelFrame, StringVar,
    Checkbutton, BooleanVar, IntVar, Listbox, Scrollbar, OptionMenu,
    X, BOTH, LEFT, RIGHT, Y, END, VERTICAL
)
from tkinter import filedialog, messagebox

from ui.terminal_widget import TerminalWidget
from services.state_manager import AppState
from core.serial_manager import SerialManager
from core.lynkx_protocol import LYNKXProtocol
from utils.constants import (
    FM_READ_CHUNK_MAX, FM_LIST_PAGE_MAX,
    LOG_TYPE_RANDO, LOG_TYPE_PARA, LOG_TYPE_DEBUG,
    LOG_TYPE_NAMES, LOG_STATE_NAMES, LOGGER_ERROR_LABELS,
    LOG_DATA_BASE, LOG_DIR_BASE, LOG_DIR_END,
    SERIAL_TIMEOUT,
)


def _format_unix(ts):
    """Format a unix timestamp for display. Returns '---' if 0."""
    if not ts:
        return "---"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError):
        return f"({ts})"


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
        self.frame = Frame(parent, bg="white", bd=2, relief='groove')
        self.state = state
        self.serial_manager = serial_manager
        self.protocol = protocol

        self._reader_thread = None
        self._stop_reader = False

        # File manager state
        self.fm_entries = []
        self.fm_selected_id = None

        # Enable protocol debug: messages go to terminal
        self.protocol.debug = True
        self.protocol.debug_callback = lambda msg: self.terminal.add_line(msg, source="dbg") if hasattr(self, 'terminal') else None

        self._create_ui()

        # Now that terminal exists, re-assign debug callback
        self.protocol.debug_callback = lambda msg: self.terminal.add_line(msg, source="dbg")

        # Subscribe to serial state changes
        self.state.subscribe('serial_connected', self._on_serial_state_changed)

    def _create_ui(self) -> None:
        """Create tab UI."""
        # ========== CONTROLS FRAME ==========
        controls_frame = Frame(self.frame, bg="white")
        controls_frame.pack(fill=X, padx=5, pady=5)

        # UART command entry
        Label(
            controls_frame, text="Commande UART :",
            font=('Helvetica', 10), bg="white", fg="black"
        ).grid(row=0, column=0, sticky="e", padx=5, pady=2)

        self.uart_entry = Entry(controls_frame, width=50, bg="white", fg="black")
        self.uart_entry.grid(row=0, column=1, columnspan=3, padx=5, pady=2, sticky="ew")
        self.uart_entry.bind('<Return>', lambda e: self._send_command())
        self.uart_entry.bind('<KP_Enter>', lambda e: self._send_command())

        Button(
            controls_frame, text="Envoyer", command=self._send_command,
            bg="white", fg="black"
        ).grid(row=0, column=4, padx=5, pady=2)

        # Battery reading
        Button(
            controls_frame, text="Lire Batterie", command=self._read_battery,
            bg="white", fg="black"
        ).grid(row=1, column=0, padx=5, pady=2)

        self.battery_var = StringVar(value="Batterie: ???")
        Label(
            controls_frame, textvariable=self.battery_var,
            font=('Helvetica', 10), bg="white", fg="black"
        ).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # Terminal logging controls
        log_frame = Frame(controls_frame, bg="white")
        log_frame.grid(row=1, column=2, columnspan=3, sticky="w", padx=5, pady=2)

        self.log_enabled_var = BooleanVar(value=False)
        self.log_path_var = StringVar(value="log.txt")

        Checkbutton(
            log_frame, text="Log terminal", variable=self.log_enabled_var,
            command=self._toggle_logging, bg="white", fg="black"
        ).pack(side="left", padx=5)

        Entry(
            log_frame, width=40, textvariable=self.log_path_var,
            bg="white", fg="black"
        ).pack(side="left", padx=5)

        Button(
            log_frame, text="Parcourir", command=self._select_log_file,
            bg="white", fg="black"
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

        self.fm_count_var = StringVar(value="0 / 0")
        Label(fm_list_container, textvariable=self.fm_count_var, bg="white", fg="black").pack(anchor="w")

        fm_list_inner = Frame(fm_list_container, bg="white")
        fm_list_inner.pack(fill=BOTH, expand=True)

        self.fm_listbox = Listbox(fm_list_inner, height=8, width=50, font=("Courier", 9))
        self.fm_listbox.pack(side=LEFT, fill=BOTH, expand=True)

        fm_scrollbar = Scrollbar(fm_list_inner, orient=VERTICAL, command=self.fm_listbox.yview)
        fm_scrollbar.pack(side=RIGHT, fill=Y)
        self.fm_listbox.configure(yscrollcommand=fm_scrollbar.set)
        self.fm_listbox.bind("<<ListboxSelect>>", self._fm_on_select)

        # File info label
        self.fm_info_var = StringVar(value="Aucun fichier selectionne")
        Label(
            fm_frame, textvariable=self.fm_info_var, bg="white", fg="black",
            anchor="w", justify="left"
        ).grid(row=0, column=1, columnspan=3, sticky="w", padx=5, pady=2)

        # Row 1: Lister, Infos, Supprimer
        Button(fm_frame, text="Lister", command=self._fm_refresh_list, bg="white", fg="black").grid(
            row=1, column=1, padx=5, pady=2, sticky="w")
        Button(fm_frame, text="Infos", command=self._fm_show_info, bg="white", fg="black").grid(
            row=1, column=2, padx=5, pady=2, sticky="w")
        Button(fm_frame, text="Supprimer", command=self._fm_delete_selected, bg="white", fg="black").grid(
            row=1, column=3, padx=5, pady=2, sticky="w")

        # Row 2: Telecharger, Tout effacer, Chunk size
        Button(fm_frame, text="Telecharger", command=self._fm_download_selected, bg="white", fg="black").grid(
            row=2, column=1, padx=5, pady=2, sticky="w")
        Button(fm_frame, text="Tout effacer", command=self._fm_erase_all, bg="white", fg="black").grid(
            row=2, column=2, padx=5, pady=2, sticky="w")

        # Row 2 col 3: Decoder button
        Button(fm_frame, text="Decoder .bin", command=self._fm_decode_file, bg="lightyellow", fg="black").grid(
            row=2, column=3, padx=5, pady=2, sticky="w")

        # Chunk size
        chunk_frame = Frame(fm_frame, bg="white")
        chunk_frame.grid(row=3, column=3, padx=5, pady=2, sticky="w")
        Label(chunk_frame, text="Chunk:", bg="white", fg="black").pack(side=LEFT)
        self.fm_chunk_size_var = StringVar(value=str(FM_READ_CHUNK_MAX))
        Entry(chunk_frame, width=6, textvariable=self.fm_chunk_size_var, bg="white", fg="black").pack(side=LEFT)

        # Busy indicator
        self.fm_busy_var = StringVar(value="?")
        self.fm_busy_label = Label(
            fm_frame, textvariable=self.fm_busy_var, bg="gray", fg="white",
            width=15, anchor="center", font=("Arial", 9, "bold")
        )
        self.fm_busy_label.grid(row=1, column=4, padx=5, pady=2, sticky="ew")

        Button(fm_frame, text="Check Busy", command=self._fm_check_busy, bg="white", fg="black").grid(
            row=2, column=4, padx=5, pady=2, sticky="ew")

        # Debug Info button
        Button(
            fm_frame, text="Debug Info", command=self._fm_show_debug_info,
            bg="lightblue", fg="black", font=("Arial", 9, "bold")
        ).grid(row=0, column=4, padx=5, pady=2, sticky="ew")

        # Status and progress
        self.fm_status_var = StringVar(value="Pret")
        Label(fm_frame, textvariable=self.fm_status_var, bg="white", fg="black", anchor="w").grid(
            row=3, column=1, columnspan=2, sticky="w", padx=5, pady=2)

        self.fm_progress_var = StringVar(value="")
        Label(fm_frame, textvariable=self.fm_progress_var, bg="white", fg="black", anchor="w").grid(
            row=3, column=3, sticky="w", padx=5, pady=2)

        # ========== LOGGER CONTROL ==========
        logger_frame = LabelFrame(self.frame, text="Logger Control", bg="white", fg="black")
        logger_frame.pack(fill=X, padx=5, pady=5)

        # Log type selector
        Label(logger_frame, text="Type:", bg="white", fg="black",
              font=("Arial", 10)).pack(side=LEFT, padx=(5, 2), pady=5)

        self.logger_type_var = StringVar(value="DEBUG")
        type_menu = OptionMenu(logger_frame, self.logger_type_var, "RANDO", "PARA", "DEBUG")
        type_menu.config(bg="white", fg="black", font=("Arial", 10), width=8)
        type_menu.pack(side=LEFT, padx=2, pady=5)

        Button(
            logger_frame, text="Start Logger", command=self._logger_start,
            bg="lightgreen", fg="black", font=("Arial", 10, "bold"), width=15
        ).pack(side=LEFT, padx=5, pady=5)

        Button(
            logger_frame, text="Stop Logger", command=self._logger_stop,
            bg="orange", fg="black", font=("Arial", 10, "bold"), width=15
        ).pack(side=LEFT, padx=5, pady=5)

        Button(
            logger_frame, text="Logger Status", command=self._logger_status,
            bg="lightblue", fg="black", font=("Arial", 10, "bold"), width=15
        ).pack(side=LEFT, padx=5, pady=5)

        self.logger_status_var = StringVar(value="")
        Label(logger_frame, textvariable=self.logger_status_var, bg="white", fg="black",
              font=("Arial", 10)).pack(side=LEFT, padx=10, pady=5)

        # ========== TERMINAL CONTROLS ==========
        terminal_controls = Frame(self.frame, bg="white")
        terminal_controls.pack(fill=X, padx=5, pady=2)

        Button(terminal_controls, text="Open serial", command=self._open_serial,
               bg="white", fg="black").pack(side=LEFT, padx=2)
        Button(terminal_controls, text="Close serial", command=self._close_serial,
               bg="white", fg="black").pack(side=LEFT, padx=2)
        Button(terminal_controls, text="Clear Terminal", command=self._clear_terminal,
               bg="white", fg="black").pack(side=LEFT, padx=2)

        Frame(terminal_controls, width=20, bg="white").pack(side=LEFT)

        Label(terminal_controls, text="Recherche:", bg="white", fg="black").pack(side=LEFT, padx=2)

        self.search_var = StringVar()
        self.search_entry = Entry(terminal_controls, textvariable=self.search_var, width=20,
                                  bg="white", fg="black")
        self.search_entry.pack(side=LEFT, padx=2)
        self.search_entry.bind('<Return>', lambda e: self._search_next())
        self.search_entry.bind('<KP_Enter>', lambda e: self._search_next())
        self.search_entry.bind('<KeyRelease>', lambda e: self._search_terminal())

        Button(terminal_controls, text="Suivant", command=self._search_next,
               bg="white", fg="black").pack(side=LEFT, padx=2)
        Button(terminal_controls, text="Precedent", command=self._search_prev,
               bg="white", fg="black").pack(side=LEFT, padx=2)

        self.search_result_var = StringVar(value="")
        Label(terminal_controls, textvariable=self.search_result_var, bg="white", fg="gray").pack(side=LEFT, padx=5)

        # ========== TERMINAL ==========
        self.terminal = TerminalWidget(self.frame, enable_log=True)

        # Search state
        self._search_matches = []
        self._search_index = -1

    # ==================== HELPERS ====================

    def _check_serial(self) -> bool:
        """Check if serial is open, show error if not."""
        if not self.serial_manager.is_open:
            messagebox.showerror("Erreur", "Port serie non ouvert")
            return False
        return True

    def _run_in_thread(self, target, *args):
        """Run a function in a daemon thread."""
        threading.Thread(target=target, args=args, daemon=True).start()

    def _get_chunk_size(self) -> int:
        """Get chunk size from UI, validated."""
        try:
            cs = int(self.fm_chunk_size_var.get())
        except ValueError:
            cs = FM_READ_CHUNK_MAX
        return max(1, min(cs, 130))

    def _get_selected_log_type(self) -> int:
        """Get log type from dropdown."""
        name = self.logger_type_var.get()
        return {"RANDO": LOG_TYPE_RANDO, "PARA": LOG_TYPE_PARA, "DEBUG": LOG_TYPE_DEBUG}.get(name, LOG_TYPE_DEBUG)

    # ==================== SERIAL STATE HANDLING ====================

    def _on_serial_state_changed(self, data: dict) -> None:
        """Handle serial connection state change from any source."""
        connected = data.get('connected', False)
        port = data.get('port', '')

        if connected:
            if self._reader_thread is None or not self._reader_thread.is_alive():
                self._stop_reader = False
                self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
                self._reader_thread.start()
                self.terminal.add_line(f"Lecture serie activee ({port})")
        else:
            self._stop_reader = True
            if self.log_enabled_var.get():
                self.terminal.close_log_file()
                self.log_enabled_var.set(False)
                self.terminal.add_line("Log ferme")

    # ==================== UART COMMANDS ====================

    def _send_command(self) -> None:
        """Send UART command."""
        command = self.uart_entry.get().strip()
        if not command:
            return
        if not self._check_serial():
            return
        self._run_in_thread(self._send_command_thread, command)

    def _send_command_thread(self, command: str) -> None:
        """Send command in background thread."""
        try:
            self.terminal.add_line(f"> {command}")
            if command.startswith('@'):
                hex_data = command[1:].replace(' ', '')
                payload = bytes.fromhex(hex_data)
                success, response = self.protocol.send_packet(payload)
                if success and response:
                    self.terminal.add_line(f"  {response.hex()}")
                elif success:
                    self.terminal.add_line("  (pas de reponse)")
                else:
                    self.terminal.add_line("  Commande echouee", source="err")
            else:
                self.serial_manager.write(command.encode() + b'\n')
                self.terminal.add_line("  Envoye")
        except ValueError as e:
            self.terminal.add_line(f"  Hex invalide: {e}")
        except Exception as e:
            self.terminal.add_line(f"  Erreur: {e}")

    # ==================== SERIAL CONTROL ====================

    def _open_serial(self) -> None:
        """Open serial port and start reading."""
        if self.serial_manager.is_open:
            if self._reader_thread is None or not self._reader_thread.is_alive():
                self._stop_reader = False
                self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
                self._reader_thread.start()
                self.terminal.add_line("Lecture serie activee")
            else:
                self.terminal.add_line("Port serie deja ouvert")
            return

        port = self.state.serial_port
        if not port or port == "Aucun port":
            messagebox.showerror("Erreur", "Aucun port selectionne")
            return

        try:
            self.serial_manager.open(port)
            self.state.set_serial_connected(True, port)
            self.terminal.add_line(f"Connexion serie sur {port} etablie")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le port: {e}")
            self.terminal.add_line(f"Erreur ouverture: {e}", source="err")

    def _close_serial(self) -> None:
        """Close serial port."""
        if not self.serial_manager.is_open:
            self.terminal.add_line("Port serie non ouvert")
            return
        self._stop_reader = True
        try:
            self.serial_manager.close()
        except Exception:
            pass
        self.state.set_serial_connected(False)
        self.terminal.add_line("Port serie ferme")

    def _reader_loop(self) -> None:
        """Read serial data continuously."""
        while not self._stop_reader and self.serial_manager.is_open:
            try:
                if self.serial_manager.exclusive_mode:
                    time.sleep(0.5)
                    continue
                if self.serial_manager.command_in_progress:
                    time.sleep(0.05)
                    continue

                data = self.serial_manager.read(1)
                if data:
                    buffer = data
                    while True:
                        byte = self.serial_manager.read(1)
                        if not byte:
                            break
                        buffer += byte
                        if byte == b'\n':
                            break
                    try:
                        text = buffer.decode('utf-8', errors='ignore').strip()
                        if text:
                            self.terminal.add_line(text, source="uart")
                    except Exception:
                        self.terminal.add_line(f"<{buffer.hex()}>", source="uart")
            except Exception as e:
                if not self._stop_reader:
                    self.terminal.add_line(f"Erreur lecture: {e}", source="err")
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

        self.terminal.text.tag_remove("search", "1.0", END)
        self.terminal.text.tag_remove("current_match", "1.0", END)
        self.terminal.text.tag_configure("search", background="yellow")
        self.terminal.text.tag_configure("current_match", background="orange")

        self._search_matches = []
        start_pos = "1.0"
        while True:
            pos = self.terminal.text.search(search_text, start_pos, stopindex=END, nocase=True)
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
        self.terminal.text.tag_remove("current_match", "1.0", END)
        pos, end_pos = self._search_matches[self._search_index]
        self.terminal.text.tag_add("current_match", pos, end_pos)
        self.terminal.text.see(pos)

    def _search_next(self) -> None:
        """Go to next search match."""
        if not self.search_var.get().strip():
            return
        if not self._search_matches or self._search_index < 0:
            self._search_terminal()
            return
        if self._search_matches:
            self._search_index = (self._search_index + 1) % len(self._search_matches)
            self._highlight_current_match()
            self.search_result_var.set(f"{self._search_index + 1}/{len(self._search_matches)}")

    def _search_prev(self) -> None:
        """Go to previous search match."""
        if not self.search_var.get().strip():
            return
        if not self._search_matches or self._search_index < 0:
            self._search_terminal()
            return
        if self._search_matches:
            self._search_index = (self._search_index - 1) % len(self._search_matches)
            self._highlight_current_match()
            self.search_result_var.set(f"{self._search_index + 1}/{len(self._search_matches)}")

    def _read_battery(self) -> None:
        """Read battery level."""
        if not self._check_serial():
            return
        self._run_in_thread(self._read_battery_thread)

    def _read_battery_thread(self) -> None:
        """Read battery in background thread."""
        try:
            level, err = self.protocol.read_battery_level()
            if level is not None:
                self.battery_var.set(f"Batterie: {level}%")
                self.terminal.add_line(f"Niveau batterie: {level}%")
                self.state.set_battery_level(level)
            else:
                self.battery_var.set("Batterie: Erreur")
                self.terminal.add_line(f"Echec lecture batterie: {err}", source="err")
        except Exception as e:
            self.terminal.add_line(f"Erreur batterie: {e}", source="err")

    # ==================== TERMINAL LOGGING ====================

    def _toggle_logging(self) -> None:
        """Toggle terminal logging."""
        enabled = self.log_enabled_var.get()
        if enabled:
            path = self._resolve_log_path()
            self.terminal.set_log_file(path, enabled=True)
            if not self.terminal.log_file_enabled:
                self.log_enabled_var.set(False)
                messagebox.showerror("Log terminal", f"Impossible d'ouvrir le fichier:\n{path}")
                return
            self.terminal.add_line(f"Log active: {path}")
        else:
            self.terminal.close_log_file()
            self.terminal.add_line("Log desactive")

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
            if self.log_enabled_var.get():
                self._toggle_logging()

    # ==================== FILE MANAGER ====================

    def _fm_format_entry(self, entry: dict) -> str:
        """Format a log entry for display in the listbox."""
        log_id = entry.get('log_id', 0)
        log_type = LOG_TYPE_NAMES.get(entry.get('log_type', -1), "?")
        state = LOG_STATE_NAMES.get(entry.get('state', -1), "?")
        size = entry.get('size_bytes', 0)
        start = entry.get('start_unix', 0)
        end = entry.get('end_unix', 0)

        if size >= 1024:
            size_str = f"{size / 1024:.1f}KB"
        else:
            size_str = f"{size}B"

        start_str = _format_unix(start)
        end_str = _format_unix(end)

        return f"#{log_id:<3} {log_type:<5} {state:<7} {size_str:>8}  {start_str} -> {end_str}"

    def _fm_on_select(self, event) -> None:
        """Handle file selection in listbox."""
        selection = self.fm_listbox.curselection()
        if not selection or not self.fm_entries:
            return
        idx = selection[0]
        if idx >= len(self.fm_entries):
            return
        entry = self.fm_entries[idx]
        self.fm_selected_id = entry.get('log_id')

        # Display detailed info
        log_type = LOG_TYPE_NAMES.get(entry.get('log_type', -1), "?")
        state = LOG_STATE_NAMES.get(entry.get('state', -1), "?")
        size = entry.get('size_bytes', 0)
        start = _format_unix(entry.get('start_unix', 0))
        end = _format_unix(entry.get('end_unix', 0))
        self.fm_info_var.set(
            f"Log #{self.fm_selected_id} | {log_type} | {state} | {size} octets | {start} -> {end}"
        )

    def _fm_refresh_list(self) -> None:
        """Refresh file list from device."""
        if not self._check_serial():
            return
        self.fm_status_var.set("Chargement...")
        self._run_in_thread(self._fm_refresh_list_thread)

    def _fm_refresh_list_thread(self) -> None:
        """Refresh file list in background."""
        try:
            # Check busy
            info, busy_err = self.protocol.fm_is_busy()
            if busy_err:
                self.terminal.add_line(f"fm_is_busy: {busy_err}")
            if info is not None:
                busy = info['busy']
                self.frame.after(0, lambda: (
                    self.fm_busy_var.set("OCCUPE" if busy else "LIBRE"),
                    self.fm_busy_label.configure(bg="red" if busy else "green")
                ))

            count, count_err = self.protocol.fm_get_log_count()
            if count is None:
                self.fm_status_var.set(f"Erreur log_count: {count_err}")
                return

            entries = []
            if count > 0:
                start = 0
                while start < count:
                    page_size = min(FM_LIST_PAGE_MAX, count - start)
                    page, page_err = self.protocol.fm_get_list_page(start, page_size)
                    if page is None:
                        self.fm_status_var.set(f"Erreur list_page: {page_err}")
                        return
                    entries.extend(page)
                    start += len(page)
                    if not page:
                        break

            self.fm_entries = entries
            self.fm_count_var.set(f"{len(entries)} / {count}")

            def update_lb():
                self.fm_listbox.delete(0, END)
                for e in entries:
                    self.fm_listbox.insert(END, self._fm_format_entry(e))
            self.frame.after(0, update_lb)

            self.fm_status_var.set(f"Liste mise a jour ({len(entries)} logs)")

        except Exception as e:
            self.fm_status_var.set(f"Erreur: {e}")

    def _fm_show_info(self) -> None:
        """Show info for selected file."""
        if self.fm_selected_id is None:
            messagebox.showinfo("Info", "Aucun fichier selectionne")
            return
        if not self._check_serial():
            return
        self._run_in_thread(self._fm_show_info_thread)

    def _fm_show_info_thread(self) -> None:
        """Show file info in background."""
        try:
            self.fm_status_var.set("Lecture infos...")
            entry, err = self.protocol.fm_get_log_info(self.fm_selected_id)
            if entry is None:
                self.fm_status_var.set(f"Erreur info: {err}")
                return

            log_type = LOG_TYPE_NAMES.get(entry.get('log_type', -1), "?")
            state = LOG_STATE_NAMES.get(entry.get('state', -1), "?")
            size = entry.get('size_bytes', 0)
            start = _format_unix(entry.get('start_unix', 0))
            end = _format_unix(entry.get('end_unix', 0))

            msg = (
                f"Log #{self.fm_selected_id}\n\n"
                f"Type: {log_type}\n"
                f"Etat: {state}\n"
                f"Taille: {size} octets ({size / 1024:.1f} KB)\n"
                f"Debut: {start}\n"
                f"Fin: {end}\n"
            )
            self.fm_status_var.set("Infos lues")
            self.frame.after(0, lambda: messagebox.showinfo("Log Info", msg))

        except Exception as e:
            self.fm_status_var.set(f"Erreur: {e}")

    def _fm_delete_selected(self) -> None:
        """Delete selected file."""
        if self.fm_selected_id is None:
            messagebox.showinfo("Info", "Aucun fichier selectionne")
            return
        if not messagebox.askyesno("Supprimer", f"Supprimer le log #{self.fm_selected_id} ?"):
            return
        if not self._check_serial():
            return
        self._run_in_thread(self._fm_delete_thread)

    def _fm_delete_thread(self) -> None:
        """Delete file in background."""
        try:
            self.fm_status_var.set("Verification...")
            info, busy_err = self.protocol.fm_is_busy()
            if busy_err:
                self.terminal.add_line(f"fm_is_busy: {busy_err}")
            if info and info['busy']:
                self.fm_status_var.set("Systeme occupe")
                self.frame.after(0, lambda: messagebox.showwarning(
                    "Occupe", "Arretez le logger avant de supprimer."))
                return

            self.fm_status_var.set("Suppression...")
            ok, del_err = self.protocol.fm_delete_log(self.fm_selected_id)
            if ok:
                self.fm_status_var.set(f"Log #{self.fm_selected_id} supprime")
                self.terminal.add_line(f"Log #{self.fm_selected_id} supprime")
                self._fm_refresh_list_thread()
            else:
                self.fm_status_var.set(f"Echec suppression: {del_err}")
                self.terminal.add_line(f"Echec suppression: {del_err}", source="err")
        except Exception as e:
            self.fm_status_var.set(f"Erreur: {e}")

    def _fm_download_selected(self) -> None:
        """Download selected file."""
        if self.fm_selected_id is None:
            messagebox.showinfo("Info", "Aucun fichier selectionne")
            return
        if not self._check_serial():
            return

        save_path = filedialog.asksaveasfilename(
            title="Enregistrer le log",
            defaultextension=".bin",
            initialfile=f"log_{self.fm_selected_id}.bin",
            filetypes=[("Binary", "*.bin"), ("All files", "*.*")]
        )
        if not save_path:
            return

        self._run_in_thread(self._fm_download_thread, save_path)

    def _fm_download_thread(self, save_path: str) -> None:
        """Download file in background."""
        prev_debug = self.protocol.debug
        try:
            self.fm_status_var.set("Telechargement...")
            entry = next((e for e in self.fm_entries if e.get('log_id') == self.fm_selected_id), None)
            if not entry:
                entry, info_err = self.protocol.fm_get_log_info(self.fm_selected_id)
                if not entry:
                    self.fm_status_var.set(f"Erreur info: {info_err}")
                    return

            total_size = entry.get('size_bytes', 0)
            chunk_size = self._get_chunk_size()
            self.terminal.add_line(f"Telechargement log #{self.fm_selected_id} ({total_size} B, chunk={chunk_size})")

            # Disable debug + enter exclusive mode to block reader thread
            self.protocol.debug = False
            self.serial_manager.enter_exclusive_mode()
            # Reduce serial timeout for fast back-to-back reads
            self.serial_manager.set_timeout(0.05)
            last_pct = -1
            offset = 0
            with open(save_path, "wb") as f:
                while True:
                    data, out_read, chunk_err = self.protocol.fm_read_log_chunk(
                        self.fm_selected_id, offset, chunk_size
                    )
                    if data is None:
                        self.fm_status_var.set(f"Erreur chunk: {chunk_err}")
                        self.terminal.add_line(f"Erreur a offset={offset}: {chunk_err}", source="err")
                        return
                    if len(data) == 0:
                        break
                    f.write(data)
                    offset += len(data)

                    if total_size:
                        pct = min(100, offset * 100 // total_size)
                        # Only update UI every 5% to reduce tkinter overhead
                        if pct >= last_pct + 5 or offset >= total_size:
                            self.fm_progress_var.set(f"{offset}/{total_size} ({pct}%)")
                            last_pct = pct
                        if offset >= total_size:
                            break
                    else:
                        self.fm_progress_var.set(f"{offset} octets")

            self.fm_status_var.set(f"Telechargement termine: {offset} octets")
            self.fm_progress_var.set("")
            self.terminal.add_line(f"Sauvegarde: {save_path} ({offset} octets)")

        except Exception as e:
            self.fm_status_var.set(f"Erreur: {e}")
            self.terminal.add_line(f"Erreur telechargement: {e}", source="err")
        finally:
            self.serial_manager.set_timeout(SERIAL_TIMEOUT)
            self.serial_manager.exit_exclusive_mode()
            self.protocol.debug = prev_debug

    def _fm_erase_all(self) -> None:
        """Erase all files using step-by-step method."""
        if not messagebox.askyesno(
            "Effacer tout",
            "ATTENTION\n\nEffacer TOUS les logs de maniere DEFINITIVE ?\n\nCette operation est IRREVERSIBLE !"
        ):
            return
        if not self._check_serial():
            return
        self._run_in_thread(self._fm_erase_all_thread)

    def _fm_erase_all_thread(self) -> None:
        """Erase all logs using step-by-step (non-blocking) method."""
        try:
            # Check busy
            self.fm_status_var.set("Verification...")
            info, busy_err = self.protocol.fm_is_busy()
            if busy_err:
                self.terminal.add_line(f"fm_is_busy: {busy_err}")
            if info and info['busy']:
                self.fm_status_var.set("Systeme occupe")
                self.frame.after(0, lambda: messagebox.showwarning(
                    "Occupe", "Arretez le logger avant d'effacer."))
                return

            # Launch async erase
            self.fm_status_var.set("Lancement effacement...")
            ok, launch_err = self.protocol.fm_erase_all_async()
            if not ok:
                self.fm_status_var.set(f"Echec lancement: {launch_err}")
                self.terminal.add_line(f"fm_erase_all_async: {launch_err}")
                return

            self.terminal.add_line("Effacement async lance, polling progression...")
            self.fm_status_var.set("Effacement en cours...")

            # Poll FM_IS_ERASING for progress
            max_poll_failures = 10
            consecutive_failures = 0

            while True:
                time.sleep(0.8)
                info, poll_err = self.protocol.fm_is_busy()

                if info is None:
                    consecutive_failures += 1
                    self.terminal.add_line(
                        f"  poll: erreur ({consecutive_failures}/{max_poll_failures}): {poll_err}")
                    if consecutive_failures >= max_poll_failures:
                        self.fm_status_var.set(f"Erreur poll apres {max_poll_failures} echecs")
                        self.terminal.add_line(f"Abandon polling apres {max_poll_failures} echecs consecutifs")
                        return
                    continue

                consecutive_failures = 0
                pct = info['erase_percent']
                busy = info['busy']
                self.fm_progress_var.set(f"Effacement: {pct}%")
                self.terminal.add_line(f"  erase: {pct}% (busy={busy})")

                if not busy:
                    break

            self.fm_status_var.set("Effacement termine")
            self.fm_progress_var.set("")
            self.terminal.add_line("Effacement complet termine")
            self._fm_refresh_list_thread()

        except Exception as e:
            self.fm_status_var.set(f"Erreur: {e}")
            self.terminal.add_line(f"Exception erase_all: {e}", source="err")

    def _fm_check_busy(self) -> None:
        """Check if device is busy."""
        if not self._check_serial():
            self.fm_busy_var.set("?")
            return
        self._run_in_thread(self._fm_check_busy_thread)

    def _fm_check_busy_thread(self) -> None:
        """Check busy in background."""
        try:
            info, err = self.protocol.fm_is_busy()
            if info is None:
                self.terminal.add_line(f"fm_is_busy: {err}")
                self.frame.after(0, lambda: (
                    self.fm_busy_var.set("Erreur"),
                    self.fm_busy_label.configure(bg="orange")
                ))
            elif info['busy']:
                pct = info['erase_percent']
                label = f"OCCUPE ({pct}%)" if pct > 0 else "OCCUPE"
                self.frame.after(0, lambda: (
                    self.fm_busy_var.set(label),
                    self.fm_busy_label.configure(bg="red")
                ))
            else:
                self.frame.after(0, lambda: (
                    self.fm_busy_var.set("LIBRE"),
                    self.fm_busy_label.configure(bg="green")
                ))
        except Exception as e:
            self.frame.after(0, lambda: self.fm_busy_var.set(f"Err: {e}"))

    def _fm_show_debug_info(self) -> None:
        """Show FileManager debug info."""
        if not self._check_serial():
            return
        self._run_in_thread(self._fm_show_debug_info_thread)

    def _fm_show_debug_info_thread(self) -> None:
        """Show debug info in background."""
        try:
            self.fm_status_var.set("Lecture debug info...")
            info, dbg_err = self.protocol.fm_get_debug_info()
            if info is None:
                self.fm_status_var.set(f"Erreur debug: {dbg_err}")
                self.terminal.add_line(f"fm_get_debug_info: {dbg_err}")
                return

            data_wr = info['s_data_wr_ptr']
            dir_wr = info['s_dir_wr_ptr']
            next_id = info['s_next_log_id']
            dir_seq = info['s_dir_seq']

            data_used = data_wr - LOG_DATA_BASE
            dir_used = dir_wr - LOG_DIR_BASE
            data_total = LOG_DIR_BASE - LOG_DATA_BASE

            is_virgin = (data_wr == LOG_DATA_BASE and dir_wr == LOG_DIR_BASE
                         and next_id == 1 and dir_seq == 0)

            msg = "FILE MANAGER DEBUG INFO\n\n"

            if is_virgin:
                msg += "Etat: Systeme vierge (apres ERASE_ALL)\n\n"
            else:
                msg += "Etat: Systeme actif\n\n"

            msg += f"Pointeurs memoire:\n"
            msg += f"  s_data_wr_ptr = 0x{data_wr:08X}\n"
            msg += f"  s_dir_wr_ptr  = 0x{dir_wr:08X}\n\n"

            msg += f"Compteurs:\n"
            msg += f"  s_next_log_id = {next_id}\n"
            msg += f"  s_dir_seq     = {dir_seq}\n\n"

            msg += f"Memoire:\n"
            msg += f"  DATA: {data_used / 1024:.1f} KB / {data_total / 1024:.1f} KB "
            if data_total > 0:
                msg += f"({data_used * 100 // data_total}%)\n"
            else:
                msg += "\n"
            msg += f"  DIR:  {dir_used / 1024:.1f} KB\n"

            self.fm_status_var.set("Debug info OK")
            self.frame.after(0, lambda: messagebox.showinfo("FileManager Debug", msg))

        except Exception as e:
            self.fm_status_var.set(f"Erreur: {e}")

    def _fm_decode_file(self) -> None:
        """Decode a previously downloaded .bin log file."""
        file_path = filedialog.askopenfilename(
            title="Ouvrir un fichier log .bin",
            filetypes=[("Binary", "*.bin"), ("All files", "*.*")]
        )
        if not file_path:
            return
        self._run_in_thread(self._fm_decode_file_thread, file_path)

    def _fm_decode_file_thread(self, file_path: str) -> None:
        """Decode log file in background."""
        try:
            with open(file_path, "rb") as f:
                data = f.read()

            if len(data) < 32:
                self.terminal.add_line(f"Fichier trop petit ({len(data)} octets)")
                return

            header, blocks = decode_log_file(data)
            if header is None:
                self.terminal.add_line("Fichier invalide (magic LYNKXLOG absent)")
                return

            report = format_decoded_log(header, blocks)

            # Show in terminal
            for line in report.split('\n'):
                self.terminal.add_line(line)

            # Propose saving as .txt
            save_path = file_path.rsplit('.', 1)[0] + "_decoded.txt"
            def ask_save():
                if messagebox.askyesno("Sauvegarder", f"Sauvegarder le decodage dans:\n{save_path} ?"):
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(report)
                    self.terminal.add_line(f"Decodage sauvegarde: {save_path}")
            self.frame.after(0, ask_save)

        except Exception as e:
            self.terminal.add_line(f"Erreur decodage: {e}", source="err")

    # ==================== LOGGER CONTROL ====================

    def _logger_start(self) -> None:
        """Start data logger."""
        if not self._check_serial():
            return
        self._run_in_thread(self._logger_start_thread)

    def _logger_start_thread(self) -> None:
        """Start logger in background."""
        try:
            log_type = self._get_selected_log_type()
            type_name = LOG_TYPE_NAMES.get(log_type, "?")
            self.terminal.add_line(f"Demarrage logger (type={type_name})...")

            ok, error_code, start_err = self.protocol.logger_start(log_type)
            if ok:
                self.terminal.add_line(f"Logger demarre (mode {type_name})")
                self.logger_status_var.set(f"RUNNING ({type_name})")
            else:
                err_msg = LOGGER_ERROR_LABELS.get(error_code, f"code {error_code}")
                self.terminal.add_line(f"Echec demarrage: {err_msg} | {start_err}", source="err")
                self.logger_status_var.set(f"Echec: {err_msg}")
        except Exception as e:
            self.terminal.add_line(f"Erreur logger: {e}", source="err")

    def _logger_stop(self) -> None:
        """Stop data logger."""
        if not self._check_serial():
            return
        self._run_in_thread(self._logger_stop_thread)

    def _logger_stop_thread(self) -> None:
        """Stop logger in background."""
        try:
            self.terminal.add_line("Arret logger...")
            ok, error_code, stop_err = self.protocol.logger_stop()
            if ok:
                self.terminal.add_line("Logger arrete")
                self.logger_status_var.set("STOPPED")
            else:
                err_msg = LOGGER_ERROR_LABELS.get(error_code, f"code {error_code}")
                self.terminal.add_line(f"Echec arret: {err_msg} | {stop_err}", source="err")
                self.logger_status_var.set(f"Echec: {err_msg}")
        except Exception as e:
            self.terminal.add_line(f"Erreur logger: {e}", source="err")

    def _logger_status(self) -> None:
        """Get logger status."""
        if not self._check_serial():
            return
        self._run_in_thread(self._logger_status_thread)

    def _logger_status_thread(self) -> None:
        """Get logger status in background."""
        try:
            status, status_err = self.protocol.logger_get_status()
            if status:
                running = status.get('running', False)
                last_error = status.get('last_error', 0)
                err_msg = LOGGER_ERROR_LABELS.get(last_error, f"code {last_error}")

                state_str = "RUNNING" if running else "STOPPED"
                self.terminal.add_line(f"Logger: {state_str} | Derniere erreur: {err_msg}")
                self.logger_status_var.set(state_str)
            else:
                self.terminal.add_line(f"Echec lecture status: {status_err}", source="err")
                self.logger_status_var.set("Erreur")
        except Exception as e:
            self.terminal.add_line(f"Erreur logger: {e}", source="err")


# ==================== LOG FILE DECODER ====================

def decode_log_file(data: bytes):
    """
    Decode a binary log file.

    Returns:
        Tuple of (header_dict, list_of_block_dicts) or (None, []) if invalid.
    """
    if len(data) < 32:
        return None, []

    # Parse header (32 bytes, little-endian fields)
    magic = data[0:8]
    if magic != b"LYNKXLOG":
        return None, []

    header = {
        'magic': magic.decode('ascii'),
        'version': data[8],
        'log_type': data[9],
        'start_unix': struct.unpack_from("<I", data, 10)[0],
        'header_len': struct.unpack_from("<H", data, 14)[0],
        'uuid': data[16:24].hex(':'),
        'rfu': data[24:32],
    }

    # Parse blocks
    blocks = []
    offset = header.get('header_len', 32)
    cumulative_ms = 0

    while offset < len(data):
        if offset + 5 > len(data):
            break  # Not enough for minimal block header

        blk_type = data[offset]
        payload_len = struct.unpack_from("<H", data, offset + 1)[0]
        dt_ms = struct.unpack_from("<H", data, offset + 3)[0]

        block_total = payload_len + 6  # type(1) + len(2) + dt(2) + payload + crc(1)
        if offset + block_total > len(data):
            break

        payload = data[offset + 5: offset + 5 + payload_len]
        crc_byte = data[offset + 5 + payload_len]

        cumulative_ms += dt_ms

        block = {
            'type': blk_type,
            'type_name': _BLK_NAMES.get(blk_type, f"0x{blk_type:02X}"),
            'dt_ms': dt_ms,
            'cumulative_ms': cumulative_ms,
            'payload_len': payload_len,
            'crc': crc_byte,
            'decoded': _decode_payload(blk_type, payload),
        }
        blocks.append(block)
        offset += block_total

    return header, blocks


_BLK_NAMES = {
    0x01: "TIME_SYNC", 0x02: "STATUS", 0x03: "EVENT",
    0x10: "GNSS_1HZ", 0x11: "BARO_1HZ", 0x12: "BARO_5HZ",
    0x20: "ACCEL_SUMMARY", 0x21: "ACCEL_RAW",
    0x30: "BLE_ANCHORS", 0x31: "BLE_PAYLOAD",
    0x40: "LORAWAN_FRAME", 0x41: "LORA_P2P_FRAME",
}

_EVENT_NAMES = {
    0x01: "SHORT_CLIC", 0x02: "LONG_CLIC", 0x03: "DOUBLE_CLIC",
    0x04: "TRIPLE_CLIC", 0x05: "SHORT_LONG_CLIC",
    0x06: "EMERGENCY", 0x07: "EMERGENCY_TEST", 0x08: "EMERGENCY_END",
    0x10: "SINGLE_TAP", 0x11: "DOUBLE_TAP",
    0x12: "IMPACT_DETECTED", 0x13: "FREEFALL_SUSPECTED",
    0x14: "SLEEP", 0x15: "WAKE_UP",
    0x20: "TAKEOFF_DETECTED", 0x21: "LANDING_DETECTED",
    0x30: "BLE_CONNECTED", 0x31: "BLE_DISCONNECTED",
    0x40: "GNSS_FIX_ACQUIRED", 0x41: "GNSS_FIX_LOST",
    0x50: "MONITOR_DISABLED", 0x51: "MONITOR_PRE_PAUSED",
    0x52: "MONITOR_PAUSED", 0x53: "MONITOR_ENABLED",
    0x54: "MONITOR_WARNING", 0x55: "MONITOR_INA_TRIGG",
    0x56: "MONITOR_TRIGGERED",
    0x60: "UNPLUGGED", 0x61: "CHARGING",
}

_MODE_NAMES = {
    0: "IDLE", 1: "RANDO", 2: "PARA", 3: "INDOOR", 4: "SOS",
}

_ACC_STATE_NAMES = {
    0: "STILL", 1: "WALK", 2: "AIRBORNE", 3: "IMPACT",
}

_RADIO_DIR = {0: "RX", 1: "TX"}
_BLE_DIR = {0: "RX", 1: "TX"}


def _decode_payload(blk_type: int, payload: bytes) -> dict:
    """Decode block payload based on type. All fields are little-endian."""
    try:
        if blk_type == 0x01 and len(payload) >= 4:  # TIME_SYNC
            unix_time = struct.unpack_from("<I", payload, 0)[0]
            return {'unix_time': unix_time, 'datetime': _format_unix(unix_time)}

        elif blk_type == 0x02 and len(payload) >= 7:  # STATUS
            batt_mv, temp_centi, mode = struct.unpack_from("<HhB", payload, 0)
            error_flags = struct.unpack_from("<H", payload, 5)[0]
            return {
                'batt_mv': batt_mv, 'temp_c': temp_centi / 100.0,
                'mode': _MODE_NAMES.get(mode, f"0x{mode:02X}"),
                'error_flags': f"0x{error_flags:04X}"
            }

        elif blk_type == 0x03 and len(payload) >= 5:  # EVENT
            event_id = payload[0]
            param = struct.unpack_from("<I", payload, 1)[0]
            return {
                'event': _EVENT_NAMES.get(event_id, f"0x{event_id:02X}"),
                'param': param
            }

        elif blk_type == 0x10 and len(payload) >= 16:  # GNSS_1HZ
            lat, lon, alt, speed, course, fix, sats = struct.unpack_from("<iihHHBB", payload, 0)
            return {
                'lat': lat / 1e7, 'lon': lon / 1e7,
                'alt_m': alt, 'speed_km_h': speed / 100.0 * 3.6,
                'course': course / 100.0, 'fix': f"0x{fix:02X}", 'sats': sats
            }

        elif blk_type == 0x11 and len(payload) >= 4:  # BARO_1HZ
            p15, temp_centi = struct.unpack_from("<Hh", payload, 0)
            return {'pressure_pa': p15 / 32768.0 * 101325, 'temp_c': temp_centi / 100.0}

        elif blk_type == 0x12 and len(payload) >= 6:  # BARO_5HZ
            p_ref = struct.unpack_from("<H", payload, 0)[0]
            dp = struct.unpack_from("<4b", payload, 2)
            return {'p_ref_p15': p_ref, 'dp_pa': list(dp)}

        elif blk_type == 0x20 and len(payload) >= 9:  # ACCEL_SUMMARY
            odr, rng, rms, mean, max_g, st = struct.unpack_from("<BBHHHB", payload, 0)
            return {
                'odr_hz': odr, 'range_g': rng,
                'rms_mg': rms, 'mean_mg': mean, 'max_mg': max_g,
                'state': _ACC_STATE_NAMES.get(st, f"0x{st:02X}")
            }

        elif blk_type == 0x21 and len(payload) >= 4:  # ACCEL_RAW
            odr, rng, n, fmt = struct.unpack_from("<BBBB", payload, 0)
            samples = []
            off = 4
            for _ in range(min(n, (len(payload) - 4) // 6)):
                x, y, z = struct.unpack_from("<hhh", payload, off)
                samples.append(f"({x},{y},{z})")
                off += 6
            return {
                'odr_hz': odr, 'range_g': rng, 'n': n, 'fmt': fmt,
                'samples_mg': " ".join(samples)
            }

        elif blk_type == 0x30 and len(payload) >= 3:  # BLE_ANCHORS
            scan_ms, n = struct.unpack_from("<HB", payload, 0)
            anchors = []
            off = 3
            for _ in range(min(n, (len(payload) - 3) // 8)):
                mac = payload[off:off+6].hex(':')
                rssi = struct.unpack_from("<b", payload, off+6)[0]
                adv_type = payload[off+7]
                anchors.append(f"{mac}({rssi}dBm)")
                off += 8
            return {'scan_ms': scan_ms, 'n': n, 'anchors': " ".join(anchors)}

        elif blk_type == 0x31 and len(payload) >= 4:  # BLE_PAYLOAD
            d, ch = payload[0], payload[1]
            nbytes = struct.unpack_from("<H", payload, 2)[0]
            data_hex = payload[4:4+nbytes].hex(' ') if nbytes > 0 else ""
            return {
                'dir': _BLE_DIR.get(d, f"0x{d:02X}"), 'channel': ch,
                'nbytes': nbytes, 'data': data_hex
            }

        elif blk_type == 0x40 and len(payload) >= 8:  # LORAWAN_FRAME
            d, port = payload[0], payload[1]
            fcnt = struct.unpack_from("<H", payload, 2)[0]
            rssi, snr = struct.unpack_from("<bb", payload, 4)
            nbytes = struct.unpack_from("<H", payload, 6)[0]
            frame_hex = payload[8:8+nbytes].hex(' ') if nbytes > 0 else ""
            return {
                'dir': _RADIO_DIR.get(d, f"0x{d:02X}"), 'port': port,
                'fcnt': fcnt, 'rssi': rssi, 'snr': snr,
                'nbytes': nbytes, 'frame': frame_hex
            }

        elif blk_type == 0x41 and len(payload) >= 11:  # LORA_P2P_FRAME
            d = payload[0]
            freq_khz = payload[1] | (payload[2] << 8) | (payload[3] << 16)
            sf, bw, cr = payload[4], payload[5], payload[6]
            txp, rssi, snr = struct.unpack_from("<bbb", payload, 7)
            nbytes = struct.unpack_from("<H", payload, 10)[0]
            frame_hex = payload[12:12+nbytes].hex(' ') if nbytes > 0 else ""
            bw_str = {0: "125k", 1: "250k", 2: "500k"}.get(bw, f"{bw}")
            return {
                'dir': _RADIO_DIR.get(d, f"0x{d:02X}"),
                'freq_MHz': freq_khz / 1000.0, 'SF': sf, 'BW': bw_str, 'CR': cr,
                'txp': txp, 'rssi': rssi, 'snr': snr,
                'nbytes': nbytes, 'payload': frame_hex
            }

        else:
            return {'raw': payload.hex()}

    except Exception:
        return {'raw': payload.hex()}


def _format_unix(ts):
    """Format unix timestamp."""
    if not ts:
        return "---"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError):
        return f"({ts})"


def format_decoded_log(header: dict, blocks: list) -> str:
    """Format decoded log as human-readable text report."""
    lines = []
    lines.append("=" * 60)
    lines.append("LYNKX LOG DECODED")
    lines.append("=" * 60)

    log_type_name = LOG_TYPE_NAMES.get(header.get('log_type', -1), '?')
    lines.append(f"Format version : {header.get('version', '?')}")
    lines.append(f"Type           : {log_type_name}")
    lines.append(f"Debut          : {_format_unix(header.get('start_unix', 0))}")
    lines.append(f"UUID           : {header.get('uuid', '?')}")
    lines.append(f"Blocs          : {len(blocks)}")
    lines.append("")

    # Summary by block type
    type_counts = {}
    for b in blocks:
        name = b['type_name']
        type_counts[name] = type_counts.get(name, 0) + 1

    lines.append("--- Statistiques ---")
    for name, count in sorted(type_counts.items()):
        lines.append(f"  {name:<20} : {count}")
    lines.append("")

    # Total duration
    if blocks:
        total_ms = blocks[-1]['cumulative_ms']
        total_s = total_ms / 1000
        mins = int(total_s // 60)
        secs = total_s % 60
        lines.append(f"Duree totale: {mins}m {secs:.1f}s ({total_ms} ms)")
        lines.append("")

    # Detail blocks
    lines.append("--- Blocs ---")
    for i, b in enumerate(blocks):
        t_s = b['cumulative_ms'] / 1000.0
        dt = b['dt_ms']
        name = b['type_name']
        dec = b['decoded']

        # Format decoded fields
        if 'raw' in dec:
            detail = f"[{dec['raw']}]"
        else:
            parts = []
            for k, v in dec.items():
                if isinstance(v, float):
                    parts.append(f"{k}={v:.4f}")
                else:
                    parts.append(f"{k}={v}")
            detail = ", ".join(parts)

        lines.append(f"  [{t_s:8.2f}s +{dt:5d}ms] {name:<18} {detail}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
