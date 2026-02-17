# Interface unifiée de test de production LYNKX (compatible macOS)

# rm -rf venv
# /usr/local/bin/python3 -m venv venv
# source venv/bin/activate
# pip install -r requirements.txt
# python3 -m tkinter 
# mkdir -p ~/lib
# ln -s "$(brew --prefix zbar)/lib/libzbar.dylib" ~/lib/libzbar.dylib




from tkinter import *
from tkinter import filedialog, messagebox
from tkinter import ttk
import serial
import serial.tools.list_ports
from pyzbar.pyzbar import decode
import cv2
import threading
import time
import numpy as np
import struct
import math
import sounddevice as sd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import requests
import os
import sys
import argparse
import glob
from Cryptodome.Cipher import AES #python3 -m pip install pycryptodomex
from Cryptodome.Util.Padding import pad
import binascii


# -----------------------------
# Variables globales
# -----------------------------
cnt = 0
reset_flag = 0
lynkx_type = 0
ser = None
VID = 0x0483
PID = 0x5740
cmd_id_counter = 0
serial_lock = threading.Lock()
command_in_progress = False  # Flag pour désactiver terminal_log pendant l'envoi de commandes
terminal_log_lock = threading.Lock()

# LYNKX Commands
LYNKX_GET_BAT_LEVEL = 0x03
LYNKX_CMD_GET_FIRM_VER = 0x05
LYNKX_ERROR_OK = 0x00
LYNKX_ERROR_KO = 0x01
LYNKX_ERROR_BAD_PARAMETER = 0x02
LYNKX_ERROR_NOT_SUPPORTED = 0x03
LYNKX_ERROR_BAD_CRC8 = 0x04
LYNKX_ERROR_FIRM_BAD_CRC32 = 0x05
LYNKX_ERROR_FIRM_LOW_BAT = 0x06
LYNKX_ERROR_VERS = 0x07
LYNKX_ERROR_BOOT_BAD_CRC32 = 0x08
LYNKX_ERROR_BOOT_LOW_BAT = 0x09
LYNKX_ERROR_UNKNWON_PARAMETER = 0x0A

LYNKX_CMD_FM_IS_ERASING = 0x20
LYNKX_CMD_FM_GET_LOG_COUNT = 0x21
LYNKX_CMD_FM_GET_LIST_PAGE = 0x22
LYNKX_CMD_FM_GET_LOG_INFO = 0x23
LYNKX_CMD_FM_READ_LOG_CHUNK = 0x24
LYNKX_CMD_FM_DELETE_LOG = 0x25
LYNKX_CMD_FM_ERASE_ALL_BLOCKING = 0x26
LYNKX_CMD_FM_ERASE_ALL_STEP = 0x27
LYNKX_CMD_FM_GET_DEBUG_INFO = 0x28
LYNKX_CMD_LOGGER_GET_STATUS = 0x29
LYNKX_CMD_LOGGER_STOP = 0x2A
LYNKX_CMD_LOGGER_START = 0x2B
FM_LIST_PAGE_MAX = 16
FM_READ_CHUNK_MAX = 20
# Logger error codes
LOGGER_OK = 0
LOGGER_ERR_NOT_RUNNING = 1
LOGGER_ERR_ALREADY_RUNNING = 2
LOGGER_ERR_FM = 3
LOGGER_ERR_SERIALIZE = 4
LOGGER_ERR_QUEUE_EMPTY = 5
# Logger log types
LOG_TYPE_DEBUG = 0
FM_LOG_INFO_STRUCT = struct.Struct(">I B B B B I I I")
FM_LOG_INFO_FIELDS = ("log_id", "log_type", "state", "rfu", "pad", "start_unix", "end_unix", "size_bytes")
current_pressure = 0
sensor_pressure = 0
max_freq_lora = 0
max_power_lora = 0
max_freq_ble = 0
max_power_ble = 0
test_firmware_file = ""
firmware_file = ""
firmware_backup_file = ""
tab_ID_QR_Code = []
tab_ID_Bar_Code = []
START = 1
read_thread = None
fm_entries = []
fm_selected_id = None
terminal_log_enabled = False
terminal_log_file_path = ""
term_views = []
en_backup_var = None

MAC_ADDRESS = "8C:1F:64:EE"

global test_names, test_vars
test_names = ['LED_GREEN1', 'LED_GREEN2', 'LED_RED1', 'LED_RED2', 'LED_FLASH', 'SOUND', 'PRESSURE', 'ACCELEROMETER', 'BC_STATE', 'BLE', 'LORA', 'GNSS', 'FLASH', 'EMERGENCY_TAB']





# Vecteur d'initialisation (IV)
# iv = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F'
# iv =  bytes([0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00])
iv =  bytes([0xad,0x3f,0xc1,0x48,0x9a,0x75,0xe3,0x43,0x97,0x82,0xbd,0x12,0x0b,0x05,0xe3,0x78])

# Clé AES (256 bits)
# key = b'Sixteen byte key'
key = bytes([0x3d, 0x0b, 0x0a, 0x8a, 0x1b, 0x5d, 0x17, 0xe2, 0x41, 0x23, 0x8d, 0xa9, 0xbb, 0x6c, 0x37, 0x8d])

# Taille du bloc
block_size = 256

version_major = 0 
version_minor = 0 
hardware_version = 0

OK = 0
FAIL = 1



def reverse_bytes_in_dwords(input_list):
    assert len(input_list) % 4 == 0  # Ensure the input length is a multiple of 4

    output = [0] * len(input_list)

    for i in range(0, len(input_list), 4):
        # Reverse the bytes in each 32-bit word
        output[i] = input_list[i + 3]
        output[i + 1] = input_list[i + 2]
        output[i + 2] = input_list[i + 1]
        output[i + 3] = input_list[i]

    return output

def calculate_crc32(bytes):
    poly = 0x04C11DB7
    initial = 0xFFFFFFFF

    bytes = reverse_bytes_in_dwords(bytes)

    table = [0] * 256
    for i in range(256):
        c = i << 24
        for j in range(8):
            if (c & 0x80000000) != 0:
                c = (c << 1) ^ poly
            else:
                c <<= 1
        table[i] = c

    # MSB first

    crc = initial
    for byte in bytes:
        index = ((crc >> 24) ^ byte) & 0xFF
        crc = (crc << 8) ^ table[index]

    return crc & 0xffffffff

def read_bytes_from_file(file_path):
    with open(file_path, "rb") as file:
        return file.read()

def save_bytes_to_file(data, output_file):
    with open(output_file, 'wb') as file:
        file.write(data)

# Fonction de chiffrement AES CBC
def encrypt_file(input_file, temp_file):

    cipher = AES.new(key, AES.MODE_CBC, iv)

    with open(input_file, 'rb') as file_in:
        with open(temp_file, 'wb') as file_out:
            i=0;
            while True:
                # Lecture d'un bloc de données du fichier d'entrée
                data = file_in.read(block_size)

                if i == 1:
                    version_major = data[0x49]
                    version_minor = data[0x4a]
                    version = version_major + version_minor/100
                    hardware_version_min_major = data[0x4b]
                    hardware_version_min_minor = data[0x4c]
                    hardware_version_min = hardware_version_min_major + hardware_version_min_minor/100

                # Si la taille du bloc est inférieure à la taille du bloc, on a atteint la fin du fichier
                if len(data) == 0:
                    break
                elif len(data) < 256 :
                    # Padding should already be done
                    return FAIL

                # Chiffrement du bloc de données
                encrypted_data = cipher.encrypt(data)

 
                # Écriture du bloc chiffré dans le fichier de sortie
                file_out.write(encrypted_data)
                i += 1

    return version, hardware_version_min, OK

def encrypt_firmware(input_file):
    global version_major
    global version_minor 
    global hard_version


    printT("Input file: "+input_file)
    input_padded_file = 'LYNKX_firmware_padded.bin'

    #import firmware from binary file
    bytes = read_bytes_from_file(input_file)

    if (len(bytes)%256):
        #pad to modulo 256 to have same file length after AES encryption
        bytes = pad(bytes,len(bytes)+256-len(bytes)%256)

    # compute CRC32 of decrypted file (checked by bootloader at firmware update)
    crc32_clear = calculate_crc32(list(bytes))

    # CRC32 of encrypted file is not known yet so encrypt in temp file
    save_bytes_to_file(bytes, input_padded_file)
    temp_file = 'xxxx.bin'
    version, hardware_version_min, Status = encrypt_file(input_padded_file, temp_file)

    if (Status==0):
        # compute CRC32 of encrypted file
        bytes = read_bytes_from_file(temp_file)
        crc32_crypted = calculate_crc32(list(bytes))

        # rename output file 
        # add EPOCH timestamp to filename to uniquify
        timestamp = int(time.time())
        output_file = 'firmwares/LYNKXF_' +  str(f"{hardware_version_min:05.2f}") + '_' + str(timestamp) + '_' +  str(f"{version:05.2f}") + '_' + str(format(crc32_clear, 'x')).zfill(8) + '_' + str(format(crc32_crypted, 'x')).zfill(8) +'.blf'
        printT("Output file: "+output_file)
        os.rename(temp_file, output_file)
        os.remove(input_padded_file)

        printT("Encryption completed.")
        printT("Hardware_version_min : " + str(f"{hardware_version_min:05.2f}"))
        printT("Firmware version : " + str(f"{version:05.2f}"))

    else:
        printT("check padding of clear file")
    return

# -----------------------------
# Fonctions de sélection firmware
# -----------------------------
def button_test_firmware():
    global test_firmware_file
    test_firmware_file = filedialog.askopenfilename(filetypes=[("Binary Files", "*.bin"), ("All Files", "*")])
    if test_firmware_file:
        select_test_firmware_button.config(bg="light green")
    else:
        select_test_firmware_button.config(bg="white")

def button_firmware():
    global firmware_file
    firmware_file = filedialog.askopenfilename(filetypes=[("Binary Files", "*.blf"), ("All Files", "*")])
    if firmware_file:
        select_firmware_button.config(bg="light green")
        firm_var.set(get_filename_with_parent_dir(firmware_file))
    else:
        select_firmware_button.config(bg="white")

def button_firmware_backup():
    global firmware_backup_file
    firmware_backup_file = filedialog.askopenfilename(filetypes=[("Binary Files", "*.blf"), ("All Files", "*")])
    if firmware_backup_file:
        select_firmware_backup_button.config(bg="light green")
        firm_backup_var.set(get_filename_with_parent_dir(firmware_backup_file))
    else:
        select_firmware_backup_button.config(bg="white")

def button_firmware_update():
    global firmware_update_file
    firmware_update_file = filedialog.askopenfilename(filetypes=[("Binary Files", "*.bin"), ("All Files", "*")])
    if firmware_update_file:
        select_firmware_update_button.config(bg="light green")
        firm_update_var.set(get_filename_with_parent_dir(firmware_update_file))
    else:
        select_firmware_update_button.config(bg="white")
    

def scan_qr_code(target_var):
    global window
    cap = cv2.VideoCapture(0)
    window_name = "Scan QR Code (appuie sur 'q' pour quitter)"

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 640, 480)

    # Centrer la fenêtre
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
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

            # 👉 Revenir au premier plan
            window.lift()
            window.attributes('-topmost', True)
            window.after_idle(window.attributes, '-topmost', False)
            return

        cv2.imshow(window_name, frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    # 👉 Revenir au premier plan même si aucun QR n'est scanné
    window.lift()
    window.attributes('-topmost', True)
    window.after_idle(window.attributes, '-topmost', False)


def update_com_ports_list():
    global com_port, port_menu
    ports = [port.device for port in serial.tools.list_ports.comports()]
    if not ports:
        ports = ["Aucun port"]

    # 🔍 Sélectionner un port contenant "usbserial" si présent
    preferred_port = next((p for p in ports if "usbserial" in p.lower()), ports[0])
    com_port.set(preferred_port)

    menu = port_menu['menu']
    menu.delete(0, 'end')
    for port in ports:
        menu.add_command(label=port, command=lambda value=port: com_port.set(value))


# -----------------------------
# Placeholder reset/restart (à compléter avec logique métier)
# -----------------------------
def restart():
    global ser, reset_flag, read_thread
    printT("[↻] Reset test...")
    deselect_all()
    global current_pressure, lora_label_var, ble_label_var
    pressure_label_var.set("Pressure = ??? mbar")
    lora_label_var.set("Freq = ??? Hz / Power = ??? dBm")
    ble_label_var.set("Freq = ??? Hz / Power = ??? dBm")

    open_com()

    ser.write(b'S')
    time.sleep(1)
    ser.write(b'R')
    
    reset_flag=0
    #Vérifie si le thread est déjà actif
    if not read_thread or not read_thread.is_alive():
        read_thread = threading.Thread(target=test_application)
        read_thread.daemon = True
        read_thread.start()

def reset():
    printT("[⭮] Réinitialisation effectuée.")

    global entry_ID_QR_Code, Device_ID_QR_Code, Device_ID_Bar_Code, entry_ID_Bar_Code
    global entry_user
    global test_firmware_file, firmware_file
    global current_pressure
    global term
    global reset_flag
    global ser
    global lynkx_type, max_freq_lora, max_power_lora, max_power_ble
    global pressure_label_var, lora_label_var, ble_label_var
    global pressure_label_widget, lora_label_widget, ble_label_widget

    deselect_all()

    # Sécurité pour le port série
    if ser and hasattr(ser, "is_open") and ser.is_open:
        reset_flag = 1

    # Remise à zéro des affichages
    pressure_label_var.set("Pressure = 0 mbar")
    pressure_label_widget.config(fg="black")

    lora_label_var.set("Freq = 0 Hz / Power = 0 dBm")
    lora_label_widget.config(fg="black")

    ble_label_var.set("Freq = 0 Hz / Power = 0 dBm")
    ble_label_widget.config(fg="black")

    # Réinitialisation des IDs
    Device_ID_QR_Code.set("")
    qr_entry.delete(0, 'end')

    Device_ID_Bar_Code.set("")
    bar_entry.delete(0, 'end')

    # Réinitialisation variables internes
    current_pressure = 0
    lynkx_type = 0
    max_freq_lora = 0
    max_power_lora = 0
    max_freq_ble = 0
    max_power_ble = 0

    # Remet le focus sur le champ QR
    qr_entry.focus_set()

def click_checkbutton(event):
    global cnt

    ser.write(b'T')  # signal au STM32

    # Coche la case courante
    name = test_names[cnt]
    test_vars[cnt].set(1)
    test_checkboxes[name].config(state=DISABLED)
    test_checkboxes[name].unbind('<Button-1>')

    # Active la case suivante (si < 5 premiers tests)
    if cnt < 4:
        next_name = test_names[cnt + 1]
        test_checkboxes[next_name].config(state=NORMAL)
        test_checkboxes[next_name].bind('<Button-1>', click_checkbutton)
    else:
        record_audio()  # après le 5e clic

    cnt += 1

def checking_window():
    global COM_PORT, term, uart_entry, battery_label_var
    global com_port, port_menu, select_test_firmware_button, select_firmware_button, select_firmware_update_button, select_firmware_backup_button
    global ble_label_var, lora_label_var, pressure_label_var
    global ble_label_widget, lora_label_widget, pressure_label_widget, hardware_version
    global firm_test_var, firm_var, firm_update_var, firm_backup_var, en_backup_var
    global operator_name
    global Device_ID_Bar_Code, Device_ID_QR_Code, qr_entry, bar_entry
    global test_vars_dict, test_vars, test_checkboxes
    global fm_listbox, fm_status_var, fm_info_var, fm_count_var, fm_progress_var, fm_chunk_size_var, fm_busy_var, fm_busy_label
    global window

    window = Tk()
    window.title("Test and program tool for LYNKX devices")
    window.configure(bg="white")
    window.geometry("850x800")

    # --- Style ttk pour les onglets ---
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TNotebook", background="white", borderwidth=2, relief='ridge')
    style.configure("TNotebook.Tab", background="white", foreground="black", font=('Helvetica', 11), padding=[10, 5])
    style.map("TNotebook.Tab", background=[("selected", "lightgray")])

    # Variables
    ble_label_var = StringVar()
    lora_label_var = StringVar()
    pressure_label_var = StringVar()
    operator_name = StringVar()
    firm_var = StringVar()
    firm_update_var = StringVar()
    firm_backup_var = StringVar()
    firm_test_var = StringVar()
    en_backup_var = BooleanVar(value=True)

    # ---------- HEADER ----------
    header_frame = Frame(window, bg="white")
    header_frame.pack(fill=X, padx=10, pady=10)

    Label(header_frame, text="Nom de l'opérateur :", font=('Helvetica', 12),
          bg="white", fg="black").grid(row=0, column=0, sticky="e", padx=5, pady=5)
    operator_entry = Entry(header_frame, width=30, textvariable=operator_name,
                           bg="white", fg="black")
    operator_entry.grid(row=0, column=1, padx=5)
    operator_name.set("bh")

    Label(header_frame, text="ID Appareil (QR Code) :", font=('Helvetica', 12),
          bg="white", fg="black").grid(row=1, column=0, sticky="e", padx=5, pady=5)
    Device_ID_QR_Code = StringVar()
    Device_ID_QR_Code.set("")
    qr_entry = Entry(header_frame, width=30, textvariable=Device_ID_QR_Code,
                     bg="white", fg="black")
    qr_entry.grid(row=1, column=1, padx=5)
    Button(header_frame, text="📷 Scanner", command=lambda: scan_qr_code(Device_ID_QR_Code),
           bg="white", fg="black").grid(row=1, column=2, sticky="w")

    Label(header_frame, text="ID Appareil (Bar Code) :", font=('Helvetica', 12),
          bg="white", fg="black").grid(row=2, column=0, sticky="e", padx=5, pady=5)
    Device_ID_Bar_Code = StringVar()
    Device_ID_Bar_Code.set("")
    bar_entry = Entry(header_frame, width=30, textvariable=Device_ID_Bar_Code,
                      bg="white", fg="black")
    bar_entry.grid(row=2, column=1, padx=5)

    Label(header_frame, text="Version HW :", font=('Helvetica', 12),
          bg="white", fg="black").grid(row=2, column=2, sticky="e", padx=5, pady=5)
    hardware_version = StringVar()
    hardware_version.set("1.04")
    hw_menu = OptionMenu(header_frame, hardware_version, "1.02", "1.04",command=on_hw_change)
    hw_menu.configure(bg="white", fg="black")
    hw_menu.grid(row=2, column=3, padx=5)

    Label(header_frame, text="Port COM :", font=('Helvetica', 12),
          bg="white", fg="black").grid(row=3, column=0, sticky="e", padx=5, pady=5)
    com_port = StringVar()
    COM_PORT = com_port
    ports = [port.device for port in serial.tools.list_ports.comports()]
    if not ports:
        ports = ["Aucun port"]
    com_port.set(ports[0])
    port_menu = OptionMenu(header_frame, com_port, *ports)
    port_menu.configure(bg="white", fg="black")
    port_menu.grid(row=3, column=1, sticky="w", padx=5)
    Button(header_frame, text="↻", command=update_com_ports_list,
           bg="white", fg="black").grid(row=3, column=2, sticky="w", padx=5)
    update_com_ports_list()

    # ---------- Onglets (Notebook) ----------
    notebook = ttk.Notebook(window)
    notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

    # --- Onglet "Test" ---
    test_tab = Frame(notebook, bg="white", bd=2, relief='groove')
    notebook.add(test_tab, text="Test")

    select_test_firmware_button = Button(test_tab, text="Test Firmware",
                                         command=button_test_firmware,
                                         bg="white", fg="black")
    select_test_firmware_button.grid(row=0, column=0, pady=10, padx=5)
    firm_test_label_widget = Label(test_tab, textvariable=firm_test_var,
                                   bg="white", fg="black", anchor="w", justify=LEFT)
    firm_test_label_widget.grid(row=0, column=1, sticky="w")
    firm_test_var.set("")

    select_firmware_button = Button(test_tab, text="Prod Firmware",
                                    command=button_firmware,
                                    bg="white", fg="black")
    select_firmware_button.grid(row=1, column=0, padx=5, pady=5)
    firm_label_widget = Label(test_tab, textvariable=firm_var,
                              bg="white", fg="black", anchor="w", justify=LEFT)
    firm_label_widget.grid(row=1, column=1, sticky="w")
    firm_var.set("")

    # Supposons que test_names est défini ailleurs
    test_vars = [IntVar() for _ in test_names]
    test_checkboxes = {}
    for i, name in enumerate(test_names):
        row = 2 + i // 3
        col = i % 3
        cb = Checkbutton(test_tab, text=name, variable=test_vars[i],
                         bg="white", fg="black", selectcolor="white",
                         activeforeground="black")
        cb.grid(row=row, column=col, padx=5, pady=2, sticky="w")
        test_checkboxes[name] = cb
    test_vars_dict = {name: var for name, var in zip(test_names, test_vars)}

    ble_label_widget = Label(test_tab, textvariable=ble_label_var,
                             bg="white", fg="black")
    lora_label_widget = Label(test_tab, textvariable=lora_label_var,
                              bg="white", fg="black")
    pressure_label_widget = Label(test_tab, textvariable=pressure_label_var,
                                  bg="white", fg="black")
    ble_label_widget.grid(row=6, column=0, columnspan=2, pady=2)
    lora_label_widget.grid(row=7, column=0, columnspan=2, pady=2)
    pressure_label_widget.grid(row=8, column=0, columnspan=2, pady=2)

    Button(test_tab, text="Configurer",
           command=lambda: threading.Thread(
               target=run_full_configuration,
               args=(Device_ID_QR_Code, Device_ID_Bar_Code, operator_name, hardware_version)
           ).start(),
           bg="white", fg="black").grid(row=9, column=0, pady=10)
    Button(test_tab, text="Restart test",
           command=restart, bg="white", fg="black").grid(row=9, column=1, pady=10)
    Button(test_tab, text="New one",
           command=reset, bg="white", fg="black").grid(row=9, column=2, pady=10)
    test_tab.columnconfigure(0, weight=1)
    test_tab.columnconfigure(1, weight=1)
    test_tab.columnconfigure(2, weight=1)

    test_terminal_frame = LabelFrame(test_tab, text="Terminal", bg="white", fg="black")
    test_terminal_frame.grid(row=10, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
    test_tab.rowconfigure(10, weight=1)

    # --- Onglet "Update" ---
    update_tab = Frame(notebook, bg="white", bd=2, relief='groove')
    notebook.add(update_tab, text="Update")
    select_firmware_update_button = Button(update_tab, text="Firmware",
                                    command=button_firmware_update,
                                    bg="white", fg="black")
    select_firmware_update_button.grid(row=1, column=0, padx=5, pady=5)
    firm_update_label_widget = Label(update_tab, textvariable=firm_update_var,
                              bg="white", fg="black", anchor="w", justify=LEFT)
    firm_update_label_widget.grid(row=1, column=1, sticky="w")
    firm_update_var.set("")
    
    select_firmware_backup_button = Button(update_tab, text="Backup Firmware",
                                    command=button_firmware_backup,
                                    bg="white", fg="black")
    Checkbutton(update_tab, text="en_backup", variable=en_backup_var,
                bg="white", fg="black", selectcolor="white",
                activeforeground="black").grid(row=2, column=0, padx=5, pady=5, sticky="w")
    select_firmware_backup_button.grid(row=2, column=1, padx=5, pady=5, sticky="w")
    firm_update_label_widget = Label(update_tab, textvariable=firm_backup_var,
                              bg="white", fg="black", anchor="w", justify=LEFT)
    firm_update_label_widget.grid(row=2, column=2, sticky="w")
    firm_backup_var.set("")

    Button(update_tab, text="Update Firm",
        command=lambda: threading.Thread(
            target=update_beacon,
            args=(Device_ID_QR_Code, Device_ID_Bar_Code, hardware_version)
        ).start(),
        bg="white", fg="black").grid(row=4, column=0, pady=10)

    Button(update_tab, text="Encrypt Firm",
        command=lambda: threading.Thread(
            target=encrypt_firmware,
            args=(firmware_update_file,)
        ).start(),
        bg="white", fg="black").grid(row=4, column=3, pady=10)

    update_tab.columnconfigure(0, weight=1)
    update_tab.columnconfigure(1, weight=1)
    update_tab.columnconfigure(2, weight=1)
    update_tab.columnconfigure(3, weight=1)

    update_terminal_frame = LabelFrame(update_tab, text="Terminal", bg="white", fg="black")
    update_terminal_frame.grid(row=5, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
    update_tab.rowconfigure(5, weight=1)


    # --- Onglet "Terminal" ---
    terminal_tab = Frame(notebook, bg="white", bd=2, relief='groove')
    notebook.add(terminal_tab, text="Terminal")

    # Frame pour les contrôles (haut de l'onglet)
    controls_frame = Frame(terminal_tab, bg="white")
    controls_frame.pack(fill=X, padx=5, pady=5)

    # Champ de saisie UART
    Label(controls_frame, text="Commande UART :", font=('Helvetica', 10),
          bg="white", fg="black").grid(row=0, column=0, sticky="e", padx=5, pady=2)

    uart_entry = Entry(controls_frame, width=50, bg="white", fg="black")
    uart_entry.grid(row=0, column=1, padx=5, pady=2, sticky="w")
    uart_entry.bind('<Return>', send_uart_command)
    uart_entry.bind('<KP_Enter>', send_uart_command)  # Pour le pavé numérique

    Button(controls_frame, text="Envoyer", command=send_uart_command,
           bg="white", fg="black").grid(row=0, column=2, padx=5, pady=2)

    Button(controls_frame, text="Open serial",
        command=lambda: threading.Thread(
            target=terminal_logger,
            args=()
        ).start(),
        bg="white", fg="black").grid(row=1, column=0, padx=5, pady=2)

    Button(controls_frame, text="Close serial",
        command=close_com,
        bg="white", fg="black").grid(row=1, column=1, padx=5, pady=2)

    Button(controls_frame, text="Clear Terminal",
        command=lambda: threading.Thread(
            target=clear_all_terminals,
            args=()
        ).start(),
        bg="white", fg="black").grid(row=1, column=2, padx=5, pady=2)

    # Bouton et label pour la batterie
    Button(controls_frame, text="Lire Batterie",
        command=read_battery_level,
        bg="white", fg="black").grid(row=1, column=3, padx=5, pady=2)

    battery_label_var = StringVar()
    battery_label_var.set("Batterie: ???")
    Label(controls_frame, textvariable=battery_label_var, font=('Helvetica', 10),
          bg="white", fg="black").grid(row=1, column=4, sticky="w", padx=5, pady=2)

    # --- Log Terminal ---
    terminal_log_enabled_var = BooleanVar(value=False)
    terminal_log_path_var = StringVar(value="log.txt")

    def resolve_terminal_log_path():
        path = terminal_log_path_var.get().strip()
        if not path:
            path = "log.txt"
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        return path

    def toggle_terminal_log():
        global terminal_log_enabled, terminal_log_file_path
        if terminal_log_enabled_var.get():
            path = resolve_terminal_log_path()
            try:
                with open(path, "w", encoding="utf-8"):
                    pass
            except Exception as e:
                terminal_log_enabled_var.set(False)
                terminal_log_enabled = False
                terminal_log_file_path = ""
                messagebox.showerror("Log terminal", f"Impossible d'ouvrir le fichier:\n{path}\n\n{e}")
                return
            terminal_log_enabled = True
            terminal_log_file_path = path
        else:
            terminal_log_enabled = False

    def select_terminal_log_file():
        path = filedialog.asksaveasfilename(
            title="Choisir un fichier de log",
            initialdir=os.getcwd(),
            initialfile="log.txt",
            defaultextension=".txt",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")]
        )
        if not path:
            return
        terminal_log_path_var.set(path)
        if terminal_log_enabled_var.get():
            toggle_terminal_log()

    log_controls_frame = Frame(controls_frame, bg="white")
    log_controls_frame.grid(row=2, column=0, columnspan=5, sticky="w", padx=5, pady=2)

    Checkbutton(log_controls_frame, text="Log terminal", variable=terminal_log_enabled_var,
                command=toggle_terminal_log, bg="white", fg="black").pack(side=LEFT, padx=5)
    Entry(log_controls_frame, width=40, textvariable=terminal_log_path_var,
          bg="white", fg="black").pack(side=LEFT, padx=5)
    Button(log_controls_frame, text="Parcourir", command=select_terminal_log_file,
           bg="white", fg="black").pack(side=LEFT, padx=5)

    # --- File Manager ---
    fm_frame = LabelFrame(terminal_tab, text="File Manager", bg="white", fg="black")
    fm_frame.pack(fill=X, padx=5, pady=5)
    fm_frame.columnconfigure(1, weight=1)
    fm_frame.columnconfigure(2, weight=1)
    fm_frame.columnconfigure(3, weight=1)

    fm_list_container = Frame(fm_frame, bg="white")
    fm_list_container.grid(row=0, column=0, rowspan=4, padx=5, pady=5, sticky="nsew")

    fm_count_var = StringVar()
    fm_count_var.set("0 / 0")
    Label(fm_list_container, textvariable=fm_count_var, bg="white", fg="black").pack(anchor="w")

    fm_list_inner = Frame(fm_list_container, bg="white")
    fm_list_inner.pack(fill=BOTH, expand=True)
    fm_listbox = Listbox(fm_list_inner, height=8, width=40)
    fm_listbox.pack(side=LEFT, fill=BOTH, expand=True)
    fm_list_scroll = Scrollbar(fm_list_inner, orient=VERTICAL, command=fm_listbox.yview)
    fm_list_scroll.pack(side=RIGHT, fill=Y)
    fm_listbox.configure(yscrollcommand=fm_list_scroll.set)
    fm_listbox.bind("<<ListboxSelect>>", fm_on_select)

    fm_info_var = StringVar()
    fm_info_var.set("Aucun fichier selectionne")
    Label(fm_frame, textvariable=fm_info_var, bg="white", fg="black", anchor="w", justify=LEFT).grid(
        row=0, column=1, columnspan=3, sticky="w", padx=5, pady=2
    )

    Button(fm_frame, text="Lister", command=fm_refresh_list, bg="white", fg="black").grid(
        row=1, column=1, padx=5, pady=2, sticky="w"
    )
    Button(fm_frame, text="Infos", command=fm_show_info, bg="white", fg="black").grid(
        row=1, column=2, padx=5, pady=2, sticky="w"
    )
    Button(fm_frame, text="Supprimer", command=fm_delete_selected, bg="white", fg="black").grid(
        row=1, column=3, padx=5, pady=2, sticky="w"
    )

    Button(fm_frame, text="Telecharger", command=fm_download_selected, bg="white", fg="black").grid(
        row=2, column=1, padx=5, pady=2, sticky="w"
    )
    Button(fm_frame, text="Tout effacer", command=fm_erase_all, bg="white", fg="black").grid(
        row=2, column=2, padx=5, pady=2, sticky="w"
    )

    fm_chunk_size_var = StringVar()
    fm_chunk_size_var.set(str(FM_READ_CHUNK_MAX))
    fm_chunk_frame = Frame(fm_frame, bg="white")
    fm_chunk_frame.grid(row=2, column=3, padx=5, pady=2, sticky="w")
    Label(fm_chunk_frame, text="Chunk:", bg="white", fg="black").pack(side=LEFT)
    Entry(fm_chunk_frame, width=6, textvariable=fm_chunk_size_var, bg="white", fg="black").pack(side=LEFT)

    # Indicateur d'état busy
    fm_busy_var = StringVar()
    fm_busy_var.set("?")
    fm_busy_label = Label(fm_frame, textvariable=fm_busy_var, bg="gray", fg="white", width=15, anchor="center", font=("Arial", 9, "bold"))
    fm_busy_label.grid(row=1, column=4, padx=5, pady=2, sticky="ew")
    Button(fm_frame, text="Check Busy", command=fm_check_busy_status, bg="white", fg="black").grid(
        row=2, column=4, padx=5, pady=2, sticky="ew"
    )

    # Bouton Debug Info
    Button(fm_frame, text="🔍 Debug Info", command=fm_show_debug_info, bg="lightblue", fg="black", font=("Arial", 9, "bold")).grid(
        row=0, column=4, padx=5, pady=2, sticky="ew"
    )

    fm_status_var = StringVar()
    fm_status_var.set("Pret")
    Label(fm_frame, textvariable=fm_status_var, bg="white", fg="black", anchor="w").grid(
        row=3, column=1, columnspan=2, sticky="w", padx=5, pady=2
    )
    fm_progress_var = StringVar()
    fm_progress_var.set("")
    Label(fm_frame, textvariable=fm_progress_var, bg="white", fg="black", anchor="w").grid(
        row=3, column=3, sticky="w", padx=5, pady=2
    )

    # --- Logger Control ---
    logger_frame = LabelFrame(terminal_tab, text="Logger Control", bg="white", fg="black")
    logger_frame.pack(fill=X, padx=5, pady=5)

    Button(logger_frame, text="▶️ Start Logger", command=logger_do_start, bg="lightgreen", fg="black", font=("Arial", 10, "bold"), width=15).pack(side=LEFT, padx=5, pady=5)
    Button(logger_frame, text="⏸️ Stop Logger", command=logger_do_stop, bg="orange", fg="black", font=("Arial", 10, "bold"), width=15).pack(side=LEFT, padx=5, pady=5)
    Button(logger_frame, text="📊 Logger Status", command=logger_show_status, bg="lightblue", fg="black", font=("Arial", 10, "bold"), width=15).pack(side=LEFT, padx=5, pady=5)

    # Terminal prend le reste de l'espace
    term = TerminalApp(terminal_tab, enable_log=True)
    term_views.clear()
    term_views.append(term)
    term_views.append(TerminalApp(test_terminal_frame, enable_log=False))
    term_views.append(TerminalApp(update_terminal_frame, enable_log=False))

    # Appel initial
    select_firmwares_file()
    select_firmwares_update_file()
    window.mainloop()



class TerminalApp:
    def __init__(self, root, enable_log=True):
        self.root = root
        self.auto_scroll_enabled = True
        self.enable_log = enable_log

        self.terminal_frame = Frame(root, bg="black")
        self.terminal_frame.pack(fill=BOTH, padx=10, pady=(0, 10), expand=True)

        self.terminal_scrollbar = Scrollbar(self.terminal_frame)
        self.terminal_scrollbar.pack(side=RIGHT, fill=Y)

        self.terminal_listbox = Listbox(self.terminal_frame, bg="black", fg="white",
                                           font=("Menlo", 11),
                                           yscrollcommand=self.terminal_scrollbar.set)
        self.terminal_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        self.terminal_scrollbar.config(command=self.on_scroll)

        # Bind sélection -> stop autoscroll
        self.terminal_listbox.bind("<<ListboxSelect>>", self.on_user_select)

    def on_scroll(self, *args):
        self.terminal_listbox.yview(*args)

        # Vérifie si on est tout en bas
        first, last = self.terminal_listbox.yview()
        if last == 1.0:
            self.auto_scroll_enabled = True
            
    def clearT(self):
        self.terminal_listbox.delete(0, END)

    def on_user_select(self, event):
        # Arrête le scroll automatique si utilisateur sélectionne
        self.auto_scroll_enabled = False

    def add_terminal_line(self, line, pos, prefix=""):
        if prefix:
            formatted_line = f"{prefix} {line}"
        else:
            formatted_line = line

        if (pos==END):
            self.terminal_listbox.insert(END, formatted_line)
        else:
            self.terminal_listbox.delete(END)
            self.terminal_listbox.insert(END, formatted_line)
        if self.auto_scroll_enabled:
            self.terminal_listbox.see(END)  # 👈 Fait défiler jusqu'à la dernière ligne
        self.write_log_line(formatted_line)

    def write_log_line(self, line):
        if not self.enable_log:
            return
        if not terminal_log_enabled:
            return
        path = terminal_log_file_path
        if not path:
            return
        try:
            with terminal_log_lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:
            pass

def on_hw_change(selection):
    select_firmwares_file()
    select_firmwares_update_file()


def recent_file(file_pattern, contains=None):
    repertoire_courant = os.getcwd()
    chemin_recherche = os.path.join(repertoire_courant, "firmwares", file_pattern)
    fichiers = glob.glob(chemin_recherche)

    if contains:
        fichiers = [f for f in fichiers if contains in os.path.basename(f)]

    fichiers_tries = sorted(fichiers, key=lambda x: os.path.getmtime(x))
    
    if not fichiers_tries:
        return "???"

    return fichiers_tries[-1]

def get_filename_with_parent_dir(path):
    """
    Retourne 'dossier_parent/nom_fichier' à partir d'un chemin complet.
    """
    parent_dir = os.path.basename(os.path.dirname(path))
    file_name = os.path.basename(path)
    return f"{parent_dir}/{file_name}"

def select_firmwares_file():
    global hardware_version, firm_test_var, firm_var, firmware_file, test_firmware_file
    hard_version = hardware_version.get()
    if (hard_version=="1.04"):
        firmware_file = recent_file('*.blf', contains='LYNKXF_01.04')
        firm_var.set(get_filename_with_parent_dir(firmware_file))

        test_firmware_file = recent_file('*.bin', contains='LYNKX_test_firmware_HARD_14_Debug')
        firm_test_var.set(get_filename_with_parent_dir(test_firmware_file))
    else:
        firmware_file = recent_file('*.blf', contains='LYNKXF_1.02')
        firm_var.set(get_filename_with_parent_dir(firmware_file))

        test_firmware_file = recent_file('*.bin',contains='LYNKX_test_firmware_HARD_12_Debug')
        firm_test_var.set(get_filename_with_parent_dir(test_firmware_file))

def select_firmwares_update_file():
    global hardware_version, firm_update_var, firm_backup_var, firmware_backup_file, firmware_update_file
    hard_version = hardware_version.get()
    if (hard_version=="1.04"):
        firmware_backup_file = recent_file('*.blf', contains='LYNKXF_01.04')
        firm_backup_var.set(get_filename_with_parent_dir(firmware_backup_file))

        firmware_update_file = '/Volumes/LYNKX_drive/rep/LYNKX_firmware/output/LYNKX_firmware_HARD_14_Debug.bin'
        firm_update_var.set(get_filename_with_parent_dir(firmware_update_file))
    else:
        firmware_backup_file = recent_file('*.blf', contains='LYNKXF_01.02')
        firm_backup_var.set(get_filename_with_parent_dir(firmware_backup_file))

        firmware_update_file = '/Volumes/LYNKX_drive/rep/LYNKX_firmware/output/LYNKX_firmware_HARD_12_Debug.bin'
        firm_update_var.set(get_filename_with_parent_dir(firmware_update_file))

def clear_all_terminals():
    if not term_views:  # Vérifier que term_views est initialisé
        return
    for view in term_views:
        view.clearT()

def add_terminal_line_all(line, pos=END, prefix=""):
    if not term_views:  # Vérifier que term_views est initialisé
        return
    for view in term_views:
        view.add_terminal_line(line, pos, prefix=prefix)

def decode_escape_sequences(text):
    """Decode escape sequences like \\xf0\\x9f\\x93\\xa6 to actual UTF-8 characters (emojis)"""
    try:
        # Decode unicode escape sequences then re-encode as latin-1 and decode as UTF-8
        return text.encode('latin-1').decode('unicode_escape').encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text

def printT(text, pos=END, prefix=""):
    # Supprimer les wrappers de type b'...'
    text = text.replace("b'", "").replace("b\"", "").replace("'", "")

    # Décoder les séquences d'échappement (emojis UTF-8)
    text = decode_escape_sequences(text)

    # Split sur les séquences "\r\n"
    parts = text.split("\\r\\n")

    for i, part in enumerate(parts):
        # Si ce n'est pas le premier bloc, on ajoute une ligne vide (signal du \r\n précédent)
        if i > 0:
            # Règle : si le texte est vide ET ce bloc n'est pas le dernier vide => skip
            if not (i == len(parts) - 1 and part.strip() == ""):
                add_terminal_line_all("", pos, prefix="")

        # Nettoyage de la partie
        clean = part.replace("\\n", "").replace("\\r", "").replace("\\t", "       ").strip()

        # Afficher seulement si non vide
        if clean:
            add_terminal_line_all(clean, pos, prefix=prefix)


        
def set_lynkx_type(tab_ID):
    global lynkx_type
    if int(tab_ID[1])==0:
        lynkx_type=0
    elif int(tab_ID[1])==1:
        lynkx_type=1

def get_device_type_name():
    if lynkx_type==0:
        device_type = "LYNKX+ SUMMIT"
    else :
        device_type = "LYNKX+"
    return device_type

def get_ID_from_QR_Code(QR_Code):
    tab_ID = []
    code = QR_Code.split('=')[1]
    for i in range(len(code)):
        tab_ID.append(code[i])
    return tab_ID

def get_ID_from_Bar_Code(Bar_Code):
    tab_ID = []
    for i in range(len(Bar_Code)):
        tab_ID.append(Bar_Code[i])
    return tab_ID

def checkMacAddress(qr_code, bar_code):
    global MAC_ADDRESS
    if (qr_code=="" or bar_code==""):
        messagebox.showinfo("Device ID Error", "Scan QR Code and Bar Code")
        return FALSE
  
    tab_ID_QR_Code = get_ID_from_QR_Code(qr_code)
    tab_ID_Bar_Code = get_ID_from_Bar_Code(bar_code)

    if (tab_ID_QR_Code!=tab_ID_Bar_Code):
        messagebox.showinfo("Device ID Error", "QR Code and Bar Code are not matching")
        return FALSE

    set_lynkx_type(tab_ID_QR_Code)
    MAC_ADDRESS = "8C:1F:64:EE"
    for i in range(0,len(tab_ID_QR_Code),2):
        MAC_ADDRESS = MAC_ADDRESS+':'+tab_ID_QR_Code[i]+tab_ID_QR_Code[i+1]
    
    return TRUE
    
def erase_int_mem():
    printT("Erasing INT MEM...")
    ser.reset_input_buffer()  # 🧹 vide les données résiduelles du buffer

    ser.write(b'E')
    rsp = ser.read()
    if rsp != b'E':
        printT(f"Error ACK : Expected 'E', car is {rsp} (int: {ord(rsp) if rsp else 'None'})")
        exit()
    rsp = ser.read()
    if rsp != b'Y':
        printT(f"Error rsp : Expected 'Y', car is {rsp} (int: {ord(rsp) if rsp else 'None'})")
        exit()


def write_firmware_to_int_mem(Path_to_firmware_uncrypted):
    printT("Writing firmware to INT MEM")
    with open(Path_to_firmware_uncrypted, mode="rb") as firmware:
        content = firmware.read()
        table_len = len(content)
        page_number = math.floor(table_len / 256)
        orphan_number = table_len % 256
        
        if (orphan_number!=0):
            content = list(content)
            padding = [0] * (256 - orphan_number)
            content.extend(padding)
            table_len_padded = len(content)
            page_number = math.floor(table_len_padded / 256)
            orphan_number = table_len_padded % 256

        # write full pages
        ser.serial.timeout = 4.0
        ser.reset_input_buffer()  # 🧹 vide les données résiduelles du buffer
        ser.write(b'W')
        rsp = ser.read()
        if rsp != (b'W'):
            printT("Error")
            #terminal_listbox.insert(END, "")
            exit()
        # address MSB first
        ser.write([((0x08006000) >> 24) & 0xff])
        ser.write([((0x08006000) >> 16) & 0xff])
        ser.write([((0x08006000) >> 8 ) & 0xff])
        ser.write([ (0x08006000)        & 0xff])
        ser.read() #wait for ack


        # page number MSB first
        ser.write([(page_number >> 24)  & 0xff])
        ser.write([(page_number >> 16)  & 0xff])
        ser.write([(page_number >> 8 )  & 0xff])
        ser.write([(page_number      )  & 0xff])
        ser.read() #wait for ack

        printT("Number of pages to write : "+str(page_number))
        printT("Writing page n° : ")
        # # data to write
        for i in range(page_number):
            printT(str(i+1), START)
            ser.write(content[(i * 256):(i * 256) + 256])
            ser.read() #wait for ack
        printT("")
        ser.read() #wait for ack

def erase_ext_mem():
    printT("Erasing EXT MEM...")
    ser.serial.timeout = 4.0
    ser.reset_input_buffer()  # 🧹 vide les données résiduelles du buffer
    # Erase command
    ser.write(b'F')
    rsp = ser.read()
    if rsp != (b'F'):
        printT("Error")
        exit()
    # number of pages to erase MSB first (0xFFFF to mass erase)
    ser.write([0xff])
    ser.write([0xff])
    
    ser.read() #wait for ack
    time.sleep(4.0)

def configure_device(config):

    printT("Configure device")
    product_str = config.ProductReference.decode('utf-8').strip()
    mac_str = ':'.join(f'{b:02X}' for b in config.MACAddress)
    printT("Product ref : " +product_str)
    printT("Hardware ver : " + str(config.HardwareVersion_Major) + str(config.HardwareVersion_Minor))
    printT("MAC : " + mac_str)

    # Erase command
    ser.write(b'C')
    rsp = ser.read()
    if rsp != (b'C'):
        printT("Error")
        exit()
    
    ser.write(config.ProductReference)
    ser.read() #wait for ack

    ser.write([config.HardwareVersion_Major])
    ser.write([config.HardwareVersion_Minor])
    ser.read() #wait for ack

    for i in range(8):
        ser.write([config.MACAddress[i]])
    ser.read() #wait for ack

def write_backup_firmware_to_ext_mem(Path_to_backup_firmware):
    printT("Writing back up firmware to EXT MEM")
    try:
        with open(Path_to_backup_firmware, mode="rb") as firmware:
            content = firmware.read()
    except FileNotFoundError:
        printT(f"[ERREUR] Fichier non trouvé : {Path_to_backup_firmware}\n")
        return
    except IOError as e:
        printT(f"[ERREUR] Impossible d'ouvrir le fichier : {e}\n")
        return

    table_len = len(content)
    page_number = math.floor(table_len / 256)
    orphan_number = table_len % 256
    
    if (orphan_number!=0):
        content = list(content)
        padding = [0] * (256 - orphan_number)
        content.extend(padding)
        table_len_padded = len(content)
        page_number = math.floor(table_len_padded / 256)
        orphan_number = table_len_padded % 256

    # write full pages
    ser.write(b'X')
    rsp = ser.read()
    if rsp != (b'X'):
        exit()
    # address MSB first
    ser.write([((0x001C0000) >> 24) & 0xff])
    ser.write([((0x001C0000) >> 16) & 0xff])
    ser.write([((0x001C0000) >> 8)  & 0xff])
    ser.write([ (0x001C0000)        & 0xff])
    ser.read() #wait for ack

    # # page number MSB first
    ser.write([(page_number >> 24)  & 0xff])
    ser.write([(page_number >> 16)  & 0xff])
    ser.write([(page_number >> 8 )  & 0xff])
    ser.write([(page_number      )  & 0xff])
    ser.read() #wait for ack

    printT("Number of pages to write : "+str(page_number))
    # # data to write
    for i in range(page_number):
        printT(str(i+1), START)
        ser.write(content[(i * 256):(i * 256) + 256])
        ser.read() #wait for ack
    printT("")
    ser.read() #wait for ack



def jump_to_main_app():
    printT("Jumping to MAIN APP...")
    ser.reset_input_buffer()  # 🧹 vide les données résiduelles du buffer
    # # Go command
    ser.write(b'G')
    rsp = ser.read()
    if rsp != (b'G'):
        printT("Error jump")
        exit()

def update_firmware():
    ser.write(b'U')
    rsp = ser.read()
    if rsp != (b'U'):
        printT(" update_firmware - command error")
        exit()
    rsp = ser.read() # waitintg end of INT flash erase
    if rsp != (b'Y'):
        printT("update_firmware - error")
        exit()
    rsp = ser.read()
    if rsp != (b'Y'): # waiting end of copy
        printT("update_firmware - error")
        exit()

def shipping_mode():
    ser.write(b'H')
    rsp = ser.read()
    if rsp != (b'H'):
        printT("command error")
        exit()

def update_pressure(result):
    global current_pressure
    pressure_label_var.set("Pressure = {} mbar".format(current_pressure))
    
    if (result) :
        test_vars_dict["PRESSURE"].set(1)
        pressure_label_widget.config(fg="green") 
    else :
        test_vars_dict["PRESSURE"].set(1)
        pressure_label_widget.config(fg="red")         
    #ble_label_var.set("BLE: Freq = 0 Hz / Puissance = 0 dBm")
    #lora_label_var.set("LORA: Freq = 0 Hz / Puissance = 0 dBm")
    

def check_pressure_status():
    global current_pressure
    global sensor_pressure
    relativ_error = (abs(current_pressure-sensor_pressure)/current_pressure)*100
    if relativ_error<1.0:
        printT("       -> Pressure OK")
        update_pressure(1)
        ser.write(b'T')
    else :
        printT("       -> Pressure NOT OK ... Check altitude in script")
        update_pressure(0)
        ser.write(b'S')



def get_env_carac():
    api_key = "d388abe96ec97541bde0a9fd799f6ddb"
    base_url = "http://api.openweathermap.org/data/2.5/weather?"
    city_name = "Meylan"
    complete_url = base_url + "&q=" + city_name + "&appid=" + api_key
    response = requests.get(complete_url)
    x = response.json()
    if x["cod"] != "404":
        y = x["main"]
        altitude = 1000
        current_press = (y["grnd_level"]) - (altitude*.0115)*100
        return current_press
    else :
        return 0
    
def calculate_power(signal):
    rms = np.sqrt(np.mean(signal**2))  # Calcul de la valeur efficace (RMS)
    power = 20 * np.log10(rms)  # Conversion en décibels (dB)
    return power

#0,36 sec
def verif_power_audio(power_1,power_2,power_3):
    # A calibrer avec un mic externe USB if((power_1>-6.5)and(power_2>-9.5)and(power_3>-12)):
    if((power_1>-35)and(power_2>-35)and(power_3>-35)):
        test_vars_dict["SOUND"].set(1)
        printT("       -> Sound OK")
        ser.write(b'T')
    else:
        printT(str(power_1) + "dB, " + str(power_2) + "dB, " + str(power_3) + "dB   -> Sound NOT OK")
        ser.write(b'S')

def warmup_microphone():
    try:
        sd.default.device = ('USB Audio', None)
        dummy = sd.rec(10, samplerate=44100, channels=1)
        sd.wait()
    except Exception as e:
        printT(f"[AUDIO INIT] Erreur warmup : {e}")

def record_audio():

    #duration = 1 # Durée d'enregistrement en secondes
    #sample_rate = 44100  # Fréquence d'échantillonnage en Hz
    #recording_1 = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
    #sd.wait()
    #recording_2 = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
    #sd.wait()
    #recording_3 = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
    #sd.wait()
    duration = 3  # total duration
    sample_rate = 44100
    full_recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
    sd.wait()

    one_sec = int(sample_rate)
    recording_1 = full_recording[0:one_sec]
    recording_2 = full_recording[one_sec:2*one_sec]
    recording_3 = full_recording[2*one_sec:3*one_sec]

    sound_1 = recording_1.flatten()
    sound_2 = recording_2.flatten()
    sound_3 = recording_3.flatten()

    # Calcul de la puissance du signal en dB
    power_1 = calculate_power(sound_1)
    power_2 = calculate_power(sound_2)
    power_3 = calculate_power(sound_3)

    verif_power_audio(power_1,power_2,power_3)

# return 1D numpy array with power as dBm
def get_tinysa_dBm( s_port, f_low, f_high, points, rbw=0, verbose=None ) -> np.array:
    with serial.Serial( port=s_port, baudrate=115200 ) as tinySA:
        tinySA.timeout = 1
        while tinySA.inWaiting():
            tinySA.read_all() # keep the serial buffer clean
            time.sleep( 0.1 )

        span_k = ( f_high - f_low ) / 1e3
        if 0 == rbw: # calculate from scan range and steps
            rbw_k = span_k / points # RBW / kHz
        else:
            rbw_k = rbw / 1e3

        if rbw_k < 3:
            rbw_k = 3
        elif rbw_k > 600:
            rbw_k = 600

        rbw_command = f'rbw {int(rbw_k)}\r'.encode()
        tinySA.write( rbw_command )
        tinySA.read_until( b'ch> ' ) # skip command echo and prompt

        # set timeout accordingly - can be very long - use a heuristic approach
        timeout = int( span_k / ( rbw_k * rbw_k ) + points / 1e3 + 5)
        tinySA.timeout = timeout

        if verbose:
            sys.stderr.write( f'frequency step: {int( span_k / ( points-1 ) )} kHz\n' )
            sys.stderr.write( f'RBW: {int(rbw_k)} kHz\n' )
            sys.stderr.write( f'serial timeout: {timeout} s\n' )

        scan_command = f'scanraw {int(f_low)} {int(f_high)} {int(points)}\r'.encode()
        tinySA.write( scan_command )
        tinySA.read_until( b'{' ) # skip command echoes
        raw_data = tinySA.read_until( b'}ch> ' )
        tinySA.write( 'rbw auto\r'.encode() ) # switch to auto RBW for faster tinySA screen update

    raw_data = struct.unpack( '<' + 'xH'*points, raw_data[:-5] ) # ignore trailing '}ch> '
    raw_data = np.array( raw_data, dtype=np.uint16 )
    # tinySA:  SCALE = 128
    # tinySA4: SCALE = 174
    SCALE = 174
    dBm_power = raw_data / 32 - SCALE # scale 0..4095 -> -128..-0.03 dBm
    return dBm_power


# Get tinysa device automatically
def getTinysaPort() -> str:
    device_list = serial.tools.list_ports.comports()
    for device in device_list:
        printT(device.name)
        if device.vid == VID and device.pid == PID:
            return device.device
    return "Error"


def measure_freq_power_zoom(F_LOW, F_HIGH, POINTS, rbw=0, verbose=False, repeats=1, zoom_span=200_000):
    """
    Mesure fréquence et puissance max avec TinySA en double passe :
    - Sweep large pour détecter le pic.
    - Sweep zoomé autour du pic pour plus de précision.
    
    Args:
        F_LOW (float): fréquence de départ (Hz)
        F_HIGH (float): fréquence de fin (Hz)
        POINTS (int): nombre de points
        rbw (float): resolution bandwidth en Hz (0 = auto)
        verbose (bool): log TinySA
        repeats (int): nombre de sweeps pour stabiliser (médiane)
        zoom_span (int): largeur (±) du zoom autour du pic détecté (Hz)
    """

    device = getTinysaPort()
    if device == "Error":
        return None, None

    max_freqs = []
    max_powers = []

    for _ in range(repeats):
        # --- Sweep large ---
        meas_power = get_tinysa_dBm(device, F_LOW, F_HIGH, POINTS, rbw, verbose)
        frequencies = np.linspace(F_LOW, F_HIGH, POINTS)

        rough_max_power = float(max(meas_power))
        rough_max_freq = int(frequencies[meas_power.tolist().index(max(meas_power))])

        # --- Sweep zoomé autour du pic détecté ---
        zoom_low = max(rough_max_freq - zoom_span, F_LOW)
        zoom_high = min(rough_max_freq + zoom_span, F_HIGH)
        meas_power_zoom = get_tinysa_dBm(device, zoom_low, zoom_high, POINTS, rbw, verbose)
        frequencies_zoom = np.linspace(zoom_low, zoom_high, POINTS)

        fine_max_power = float(max(meas_power_zoom))
        fine_max_freq = int(frequencies_zoom[meas_power_zoom.tolist().index(max(meas_power_zoom))])

        max_freqs.append(fine_max_freq)
        max_powers.append(fine_max_power)

    final_freq = int(np.median(max_freqs))
    final_power = round(np.median(max_powers), 1)

    return final_freq, final_power

def measure_freq_power_old(F_LOW,F_HIGH,POINTS):
    ap = argparse.ArgumentParser( description='Get a raw scan from tinySA, formatted as csv (freq, power)')
    ap.add_argument( '-d', '--device', dest = 'device', default=None, help = 'connect to serial device' )
    ap.add_argument( '-s', '--start', type=float, default=F_LOW, help=f'start frequency, default = {F_LOW} Hz' )
    ap.add_argument( '-e', '--end', type=float, default=F_HIGH, help=f'end frequency, default = {F_HIGH} Hz' )
    ap.add_argument( '-p', '--points', type=int, default=POINTS, help=f'Number of sweep points, default = {POINTS}' )
    ap.add_argument( '-r', '--rbw', type=float, default=0,
                    help='resolution bandwidth / Hz, default = 0 (calculate RBW from scan steps)')
    ap.add_argument( '-c', '--comma', action='store_true', help='use comma as decimal separator' )
    ap.add_argument( '-v', '--verbose', action='store_true', help='provide info about scan parameter and timing' )
    options = ap.parse_args()

    meas_power = get_tinysa_dBm( options.device or getTinysaPort(),
                                options.start, options.end, options.points, options.rbw, options.verbose )

    # create a 1D numpy array with scan frequencies
    frequencies = np.linspace( options.start, options.end, options.points )

    max_power = max(meas_power).round(1)
    max_freq = int(frequencies[meas_power.tolist().index(max(meas_power))])

    return max_freq, max_power

def get_LoRa_freq_power():
    if getTinysaPort()=="Error":
        messagebox.showerror("Error", "Device not found")
    else :
        global max_freq_lora
        global max_power_lora
        F_LOW = 867750000
        F_HIGH = 868250000
        POINTS = 1000    
        #max_freq_lora, max_power_lora =  measure_freq_power(F_LOW,F_HIGH,POINTS)
        max_freq_lora, max_power_lora = measure_freq_power_zoom(F_LOW, F_HIGH, POINTS) 
        lora_label_var.set("Freq = {} Hz / Power = {} dBm".format(max_freq_lora,max_power_lora))
        check_lora_freq()

def get_BLE_freq_power():
    if getTinysaPort()=="Error":
        messagebox.showerror("Error", "Device not found")
    else :
        global max_freq_ble
        global max_power_ble
        F_LOW = 2439500000
        F_HIGH = 2440500000
        POINTS = 2000
        max_freq_ble, max_power_ble =  measure_freq_power_zoom(F_LOW, F_HIGH, POINTS) 
        ble_label_var.set("Freq = {} Hz / Power = {} dBm".format(max_freq_ble, max_power_ble)) 
        check_ble_freq()

def box_state_update():
    status = []
    for i, name in enumerate(test_names):
        if test_vars[i].get():
            status.append("OK")
        else:
            status.append("NOT OK")
    return status

def deselect_all():
    global cnt
    cnt = 0  # Reset compteur

    for i, name in enumerate(test_names):
        test_vars[i].set(0)  # Décocher
        test_checkboxes[name].config(state=NORMAL)  # Réactiver
        test_checkboxes[name].bind('<Button-1>', click_checkbutton if i == 0 else lambda e: None)  # Rebind uniquement la première



def calculate_env_carac():
    global current_pressure
    current_pressure = get_env_carac()

def calc_lora_exp_bw():
    tab_freq = []
    tab_power = []
    for i in range(10):
        get_LoRa_freq_power()
        tab_freq.append(max_freq_lora)
        tab_power.append(max_power_lora)
    print("Freq_mean : {}".format(np.mean(tab_freq)))
    print("Power_mean : {}".format(np.mean(tab_power)))

def calc_ble_exp_bw():
    tab_freq = []
    tab_power = []
    for i in range(10):
        get_BLE_freq_power()
        tab_freq.append(max_freq_ble)
        tab_power.append(max_power_ble)
    print("Freq_mean : {}".format(np.mean(tab_freq)))
    print("Power_mean : {}".format(np.mean(tab_power)))


def check_lora_freq():
    if max_power_lora>-80: #experimental value
        printT("       -> LoRa OK")
        lora_label_widget.config(fg="green")
        test_vars_dict["LORA"].set(1)
        ser.write(b'T')
    else:
        printT("       -> LoRa NOT OK")
        lora_label_widget.config(fg="red")
        ser.write(b'S')

def check_ble_freq():
    if max_power_ble>-50: #experimental value
        printT("       -> BLE OK")
        ble_label_widget.config(fg="green")
        test_vars_dict["BLE"].set(1)
        ser.write(b'T')
    else : 
        printT("       -> BLE NOT OK")
        ble_label_widget.config(fg="red")
        ser.write(b'S')

def init_serial_port():
    global COM_PORT
    serial_port = serial.Serial()
    serial_port.port = COM_PORT.get()
    serial_port.baudrate = 921600
    serial_port.timeout = 0.2
    
    # 🔥 Vide les buffers après ouverture
    #serial_port.reset_input_buffer()
    #serial_port.reset_output_buffer()
    return serial_port

class VerboseSerial:
    def __init__(self, serial_obj, verbose=0):
        self.serial = serial_obj
        self.verbose = verbose

    def write(self, data):
        if self.verbose:
            if isinstance(data, (list, bytearray)):
                data_bytes = bytes(data)
            elif isinstance(data, bytes):
                data_bytes = data
            else:
                data_bytes = bytes([data])  # pour un int seul éventuel

            #sys.stderr.write(f"[TX] {data_bytes.hex()} | {data_bytes}\n")
        return self.serial.write(data)

    def read(self, size=1):
        try:
            result = self.serial.read(size)
            #if not result:
                #raise serial.SerialException("No data received from device (timeout or disconnected?)")          
            if self.verbose and result:
                sys.stderr.write(f"[RX] {result.hex()} | {result}\n")
            return result
        except serial.SerialException as e:
            print(f"[ERREUR SERIE] {e}")
            return ""  

    def readline(self):
        try:
            result = self.serial.readline()
            #if not result:
            #    raise serial.SerialException("No data received from device (timeout or disconnected?)")     
            if self.verbose and result:
                sys.stderr.write(f"[RX line] {result}\n")
            return result
        except serial.SerialException as e:
            print(f"[ERREUR SERIE] {e}")
            return ""          

    def __getattr__(self, attr):
        return getattr(self.serial, attr)


def test_application():
    global lynkx_type
    global sensor_pressure
    global ser
    global reset_flag
    global cnt
    cnt=0

    if (ser.is_open):
        ser.close()
    raw_serial = init_serial_port()
    ser = VerboseSerial(raw_serial, verbose=0)
    ser.open()
    time.sleep(0.1) 
    ser.serial.timeout = 0.2

    warmup_microphone()

    while(1):
        sys.stderr.write(".")
        time.sleep(0.1) 

        line = ser.readline()
        chaine = str(line)
        chaine = chaine.replace("b'",'')
        chaine = chaine.replace("\\r",'')
        chaine = chaine.replace("\\n",'')
        chaine = chaine.replace("b\"",'')
        chaine = chaine.replace("'",'')

        if "LED_GREEN1" in chaine:
            test_checkboxes["LED_GREEN1"].config(state=NORMAL)
            test_checkboxes["LED_GREEN1"].bind('<Button-1>', click_checkbutton)

        if "BC State OK" in chaine:
            test_vars_dict["BC_STATE"].set(1)
            ser.write(b'T')

        if "No barometer" in chaine:
            if (lynkx_type==0):
                chaine = ""
            ser.write(b'T')

        if "Barometer" in chaine:
            if (lynkx_type==1):
                chaine = ""
            else:
                tab = chaine.split()
                sensor_pressure = round(int(tab[7])/100)
                chaine = chaine.replace("\\t",'')
                printT("       "+chaine)
                chaine = ""
                calculate_env_carac()
                check_pressure_status()

        if "Accelerometer OK" in chaine:
            test_vars_dict["ACCELEROMETER"].set(1)
            ser.write(b'T')

        if "BLE Initialized" in chaine:
            get_BLE_freq_power()
            chaine = ""
        if "LoRa Initialized" in chaine:
            get_LoRa_freq_power()
            chaine = ""

        if "GNSS OK" in chaine:
            test_vars_dict["GNSS"].set(1)
            ser.write(b'T')

        if "Flash OK" in chaine:
            test_vars_dict["FLASH"].set(1)
            ser.write(b'T')

        if "Emergency tab OK" in chaine:
            test_vars_dict["EMERGENCY_TAB"].set(1)
            ser.write(b'T')

        if "\\x" in chaine:
            chaine = ""
        if chaine!="":
            if "\\t" in chaine :
                chaine = chaine.replace("\\t",'')
                printT("       "+chaine, prefix="[RX]")
            else :
                printT(chaine, prefix="[RX]")


        if "Production tests complete" in chaine:

            printT("Click the button once to go to update step")

            while(1):
                line = ser.readline()
                chaine = str(line)
                if "Button pressed" in chaine:
                    break

            printT("Unplug and plug again")
            ser.serial.timeout = 0.5
            while(1):
                try:
                    ser.write(b'?')
                except Exception as e:
                    ()
                else:
                    rsp = ser.read()
                    if rsp == (b'Y'):
                        ser.serial.timeout = None
                        break
                    pass
         
            printT("Updating firmware from EXT flash...")
            update_firmware()
            shipping_mode()
            printT("Firmware updated !")

            save_checking()
            reset_flag=1
            ser.close()
            break

def terminal_log():
    global lynkx_type
    global sensor_pressure
    global ser
    global reset_flag
    global cnt
    global command_in_progress
    cnt=0

    if (ser.is_open):
        ser.close()
    raw_serial = init_serial_port()
    ser = VerboseSerial(raw_serial, verbose=0)
    ser.open()
    time.sleep(0.1)
    ser.serial.timeout = 0.2

    while(1):
        # Ne pas lire si une commande est en cours
        if not command_in_progress:
            with serial_lock:
                line = ser.readline()
            if line:
                printT(str(line), prefix="[RX]")
        else:
            time.sleep(0.01)  # Petite pause pour éviter de consommer du CPU


def center_string(str,pdf,pdf_width):
    str_width = pdf.get_string_width(str)
    pdf.set_x((pdf_width-str_width)/2)

def width(str,pdf):
    str_width = pdf.get_string_width(str)
    return str_width

def save_checking():
        global Device_ID_Bar_Code


        name = "Operator name : " + operator_name.get()
        device_type = get_device_type_name()
        device_description = " Device type : " + device_type
        ID = Device_ID_Bar_Code.get()
        hard_version = hardware_version.get()
        serial = device_description + " " + hard_version + " : " + ID



        status = box_state_update()

        pdf = FPDF('P','mm','A4')
        pdf_width = pdf.w
        pdf.add_page()

        pdf.set_font('Helvetica','',16)
        title = 'Production check list'
        center_string(title,pdf,pdf_width)
        pdf.cell(width(title,pdf),12,title)
        pdf.ln()

        pdf.set_font('Helvetica','',12)

        center_string(serial,pdf,pdf_width)
        pdf.cell(width(serial,pdf),10,serial)
        pdf.ln()

        data_table_1 = {"Components": test_names,
                    "Status": status,
                }
        create_table(pdf,table_data = data_table_1,title=name, align_header='C', align_data='C', cell_width=[60,60], x_start='C', emphasize_data=["OK","NOT OK"], emphasize_color=[(0,255,0),(255,0,0)])
        pdf.ln()

        data_table_2 = {"Technology": ["BLE","LoRa"],
                    "Frequency (Hz)": [max_freq_ble,max_freq_lora],
                    "Power (dBm)" : [max_power_ble,max_power_lora],
                    "Status": ["OK","OK"]
                }
        create_table(pdf,table_data = data_table_2,title='RF Testing',align_header='C', align_data='C', cell_width=[30,30,30,30], x_start='C', emphasize_data=["OK","NOT OK"], emphasize_color=[(0,255,0),(255,0,0)])
        pdf.ln()

        if lynkx_type==0:
            data_table_3 = {"Environment caracteristics": ["Pressure (mbar)"],
                        "Value": [current_pressure],
                        "Status": ["OK"]
                    }
            create_table(pdf,table_data = data_table_3,title='Testing environment',align_header='C', align_data='C', cell_width=[40,40,40], x_start='C', emphasize_data=["OK","NOT OK"], emphasize_color=[(0,255,0),(255,0,0)])
        
        pdf.output("./Reports/Device_ID_"+ID+"_OK.pdf")    
        messagebox.showinfo("Saving", "File saved as Device_ID_"+ID+"_OK.pdf")

#Create table
def create_table(pdf, table_data, title='', data_size = 9, title_size=11, align_data='L', align_header='L', cell_width='even', x_start='x_default',emphasize_data=[], emphasize_style=None,emphasize_color=(0,0,0)): 
        """
        table_data: 
                    list of lists with first element being list of headers
        title: 
                    (Optional) title of table (optional)
        data_size: 
                    the font size of table data
        title_size: 
                    the font size fo the title of the table
        align_data: 
                    align table data
                    L = left align
                    C = center align
                    R = right align
        align_header: 
                    align table data
                    L = left align
                    C = center align
                    R = right align
        cell_width: 
                    even: evenly distribute cell/column width
                    uneven: base cell size on lenght of cell/column items
                    int: int value for width of each cell/column
                    list of ints: list equal to number of columns with the widht of each cell / column
        x_start: 
                    where the left edge of table should start
        emphasize_data:  
                    which data elements are to be emphasized - pass as list 
                    emphasize_style: the font style you want emphaized data to take
                    emphasize_color: emphasize color (if other than black) 
        
        """
        default_style = pdf.font_style
        if emphasize_style == None:
            emphasize_style = default_style
        # default_font = pdf.font_family
        # default_size = pdf.font_size_pt
        # default_style = pdf.font_style
        # default_color = pdf.color # This does not work

        # Get Width of Columns
        def get_col_widths():
            col_width = cell_width
            if col_width == 'even':
                col_width = pdf.epw / len(data[0]) - 1  # distribute content evenly   # epw = effective page width (width of page not including margins)
            elif col_width == 'uneven':
                col_widths = []

                # searching through columns for largest sized cell (not rows but cols)
                for col in range(len(table_data[0])): # for every row
                    longest = 0 
                    for row in range(len(table_data)):
                        cell_value = str(table_data[row][col])
                        value_length = pdf.get_string_width(cell_value)
                        if value_length > longest:
                            longest = value_length
                    col_widths.append(longest + 4) # add 4 for padding
                col_width = col_widths



                        ### compare columns 

            elif isinstance(cell_width, list):
                col_width = cell_width  # TODO: convert all items in list to int        
            else:
                # TODO: Add try catch
                col_width = int(col_width)
            return col_width

        # Convert dict to lol
        # Why? because i built it with lol first and added dict func after
        # Is there performance differences?
        if isinstance(table_data, dict):
            header = [key for key in table_data]
            data = []
            for key in table_data:
                value = table_data[key]
                data.append(value)
            # need to zip so data is in correct format (first, second, third --> not first, first, first)
            data = [list(a) for a in zip(*data)] #matrice

        else:
            header = table_data[0]
            data = table_data[1:]

        line_height = pdf.font_size * 2.5

        col_width = get_col_widths()
        pdf.set_font(size=title_size)

        # Get starting position of x
        # Determin width of table to get x starting point for centred table
        if x_start == 'C':
            table_width = 0
            if isinstance(col_width, list):
                for width in col_width:
                    table_width += width
            else: # need to multiply cell width by number of cells to get table width 
                table_width = col_width * len(table_data[0])
            # Get x start by subtracting table width from pdf width and divide by 2 (margins)
            margin_width = pdf.w - table_width
            # TODO: Check if table_width is larger than pdf width

            center_table = margin_width / 2 # only want width of left margin not both
            x_start = center_table
            pdf.set_x(x_start)
        elif isinstance(x_start, int):
            pdf.set_x(x_start)
        elif x_start == 'x_default':
            x_start = pdf.set_x(pdf.l_margin)


        # TABLE CREATION #

        # add title
        if title != '':
            pdf.multi_cell(0, line_height, title, border=0, align='j',new_x=XPos.RIGHT, new_y=YPos.TOP, max_line_height=pdf.font_size)
            pdf.ln(line_height) # move cursor back to the left margin

        pdf.set_font(size=data_size)
        # add header
        y1 = pdf.get_y()
        if x_start:
            x_left = x_start
        else:
            x_left = pdf.get_x()
        x_right = pdf.epw + x_left
        if  not isinstance(col_width, list):
            if x_start:
                pdf.set_x(x_start)
            for datum in header:
                pdf.multi_cell(col_width, line_height, datum, border=0, align=align_header,new_x=XPos.RIGHT, new_y=YPos.TOP, max_line_height=pdf.font_size)
                x_right = pdf.get_x()
            pdf.ln(line_height) # move cursor back to the left margin
            y2 = pdf.get_y()
            pdf.line(x_left,y1,x_right,y1)
            pdf.line(x_left,y2,x_right,y2)

            for row in data:
                if x_start: # not sure if I need this
                    pdf.set_x(x_start)
                for datum in row:
                    if datum in emphasize_data:
                        pdf.set_text_color(*(emphasize_color[emphasize_data.index(datum)]))
                        pdf.set_font(style=emphasize_style)
                        pdf.multi_cell(col_width, line_height, datum, border=0, align=align_data,new_x=XPos.RIGHT, new_y=YPos.TOP, max_line_height=pdf.font_size)
                        pdf.set_text_color(0,0,0)
                        pdf.set_font(style=default_style)
                    else:
                        pdf.multi_cell(col_width, line_height, datum, border=0, align=align_data,new_x=XPos.RIGHT, new_y=YPos.TOP, max_line_height=pdf.font_size) # ln = 3 - move cursor to right with same vertical offset # this uses an object named pdf
                pdf.ln(line_height) # move cursor back to the left margin
        
        else:
            if x_start:
                pdf.set_x(x_start)
            for i in range(len(header)):
                datum = header[i]
                pdf.multi_cell(col_width[i], line_height, datum, border=0, align=align_header,new_x=XPos.RIGHT, new_y=YPos.TOP, max_line_height=pdf.font_size)
                x_right = pdf.get_x()
            pdf.ln(line_height) # move cursor back to the left margin
            y2 = pdf.get_y()
            pdf.line(x_left,y1,x_right,y1)
            pdf.line(x_left,y2,x_right,y2)


            for i in range(len(data)):
                if x_start:
                    pdf.set_x(x_start)
                row = data[i]
                for i in range(len(row)):
                    datum = row[i]
                    if not isinstance(datum, str):
                        datum = str(datum)
                    adjusted_col_width = col_width[i]
                    if datum in emphasize_data:
                        pdf.set_text_color(*(emphasize_color[emphasize_data.index(datum)]))
                        pdf.set_font(style=emphasize_style)
                        pdf.multi_cell(adjusted_col_width, line_height, datum, border=0, align=align_data,new_x=XPos.RIGHT, new_y=YPos.TOP, max_line_height=pdf.font_size)
                        pdf.set_text_color(0,0,0)
                        pdf.set_font(style=default_style)
                    else:
                        pdf.multi_cell(adjusted_col_width, line_height, datum, border=0, align=align_data,new_x=XPos.RIGHT, new_y=YPos.TOP, max_line_height=pdf.font_size) # ln = 3 - move cursor to right with same vertical offset # this uses an object named pdf
                pdf.ln(line_height) # move cursor back to the left margin
        y3 = pdf.get_y()
        pdf.line(x_left,y3,x_right,y3)


def calculate_crc8(data):
    """Calculate CRC8 for LYNKX protocol (polynomial 0x07)"""
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
        crc &= 0xFF
    return crc

def send_lynkx_command(cmd_id, payload=b''):
    """Send a LYNKX command and wait for response"""
    global ser

    if not ser or not hasattr(ser, 'is_open') or not ser.is_open:
        printT("❌ Port série non ouvert.")
        return None

    cmd_data = bytes([cmd_id]) + payload
    response = send_lynkx_packet(cmd_data)
    return response

def read_battery_level():
    """Read battery level from LYNKX beacon"""
    global battery_label_var

    printT("Lecture niveau de batterie...")

    # Send command: CMD_ID=LYNKX_GET_BAT_LEVEL (0x03)
    response = send_lynkx_command(LYNKX_GET_BAT_LEVEL)

    if not response:
        battery_label_var.set("Batterie: ???")
        return

    printT(f"Longueur réponse: {len(response)} octets")

    # Erreurs possibles
    error_codes = {
        0x00: "OK",
        0x01: "KO",
        0x02: "BAD_PARAMETER",
        0x03: "NOT_SUPPORTED",
        0x04: "BAD_CRC8",
        0x05: "FIRM_BAD_CRC32",
        0x06: "FIRM_LOW_BAT",
        0x07: "VERS",
        0x08: "BOOT_BAD_CRC32",
        0x09: "BOOT_LOW_BAT",
        0x0A: "UNKNWON_PARAMETER"
    }

    if len(response) >= 4:
        # Format: [ID_COUNT, STATUS, BAT_LEVEL, CRC8]
        status = response[1]
        bat_level = response[2]
        crc_received = response[3]

        # Verify CRC (ID_COUNT + DATA)
        crc_calc = calculate_crc8(response[0:3])

        if crc_calc != crc_received:
            printT(f"❌ CRC invalide (calc={crc_calc:02X}, reçu={crc_received:02X})")
            battery_label_var.set("Batterie: Erreur CRC")
            return

        if status == LYNKX_ERROR_OK:
            printT(f"✅ Niveau de batterie: {bat_level}%")
            battery_label_var.set(f"Batterie: {bat_level}%")
        else:
            error_name = error_codes.get(status, f"UNKNOWN_{status:02X}")
            printT(f"❌ Erreur status: {error_name} (0x{status:02X})")
            battery_label_var.set(f"Batterie: Erreur {error_name}")
    else:
        printT(f"❌ Réponse invalide: {len(response)} octets")
        battery_label_var.set("Batterie: ???")

def next_cmd_id():
    global cmd_id_counter
    cmd_id_counter = (cmd_id_counter + 1) & 0xFF
    return cmd_id_counter

def send_lynkx_packet(payload, response_timeout=1.0, expected_len=None):
    global ser
    global command_in_progress

    if not ser or not hasattr(ser, 'is_open') or not ser.is_open:
        printT("❌ Port série non ouvert.")
        return None

    cmd_id = next_cmd_id()
    cmd_body = bytes([cmd_id]) + payload
    crc = calculate_crc8(cmd_body)
    frame = cmd_body + bytes([crc])
    packet = b'@' + bytes([len(frame)]) + frame

    try:
        # Désactiver terminal_log pendant la commande
        command_in_progress = True

        with serial_lock:
            ser.reset_input_buffer()
            ser.write(packet)

            hex_display = ' '.join(f'{b:02X}' for b in packet)
            add_terminal_line_all(
                f"@ [len={len(frame)} id={cmd_id:02X}] {hex_display}",
                END,
                prefix="[TX]",
            )

            # Lire et afficher les données brutes
            old_timeout = ser.serial.timeout
            ser.serial.timeout = 0.1  # 100ms entre chaque tentative de lecture

            start_time = time.time()
            response = bytearray()
            last_data_time = None
            idle_timeout = 0.3  # Attendre 300ms de silence avant d'arrêter

            # Lire tant que des données arrivent ou timeout global atteint
            while time.time() - start_time < response_timeout:
                chunk = ser.read(256)
                if chunk:
                    # Afficher immédiatement les bytes bruts reçus
                    chunk_hex = ' '.join(f'{b:02X}' for b in chunk)
                    add_terminal_line_all(f"{chunk_hex}", END, prefix="[RX]")
                    response.extend(chunk)
                    last_data_time = time.time()

                    # Si expected_len spécifié et atteint, sortir immédiatement
                    if expected_len and len(response) >= expected_len:
                        break
                elif len(response) > 0 and last_data_time and not expected_len:
                    # Arrêt anticipé seulement si expected_len n'est PAS fourni
                    # Sinon on attend le timeout complet pour laisser le temps au firmware
                    if time.time() - last_data_time >= idle_timeout:
                        break

            response = bytes(response)
            ser.serial.timeout = old_timeout

        if response:
            # Format RX: [counter] [data...] [CRC] (pas de wrapper '@' en réponse)
            return response

        printT("❌ Timeout: Aucune réponse reçue")
        return None
    except Exception as e:
        printT(f"❌ Erreur envoi commande: {e}")
        return None
    finally:
        # Toujours réactiver terminal_log
        command_in_progress = False

def build_fm_command(cmd_id, payload=b''):
    return bytes([cmd_id]) + payload

def parse_fm_response(response):
    if not response or len(response) < 3:
        return None, "Réponse vide ou trop courte"

    crc_calc = calculate_crc8(response[:-1])
    crc_recv = response[-1]
    if crc_calc != crc_recv:
        return None, f"CRC invalide (calc={crc_calc:02X}, reçu={crc_recv:02X})"

    payload = response[1:-1]
    if not payload:
        return None, "Réponse vide"
    status = payload[0]
    data = payload[1:]
    if status != LYNKX_ERROR_OK:
        error_labels = {
            LYNKX_ERROR_OK: "OK",
            LYNKX_ERROR_KO: "KO",
            LYNKX_ERROR_BAD_PARAMETER: "BAD_PARAMETER",
            LYNKX_ERROR_NOT_SUPPORTED: "NOT_SUPPORTED",
            LYNKX_ERROR_BAD_CRC8: "BAD_CRC8",
            LYNKX_ERROR_FIRM_BAD_CRC32: "FIRM_BAD_CRC32",
            LYNKX_ERROR_FIRM_LOW_BAT: "FIRM_LOW_BAT",
            LYNKX_ERROR_VERS: "VERS",
            LYNKX_ERROR_BOOT_BAD_CRC32: "BOOT_BAD_CRC32",
            LYNKX_ERROR_BOOT_LOW_BAT: "BOOT_LOW_BAT",
            LYNKX_ERROR_UNKNWON_PARAMETER: "UNKNWON_PARAMETER",
        }
        return data, f"Erreur status: {error_labels.get(status, f'0x{status:02X}')}"

    return data, None

def parse_fm_count_response(response):
    if not response or len(response) < 4:
        return None, "Réponse vide ou trop courte"

    crc_calc = calculate_crc8(response[:-1])
    crc_recv = response[-1]
    if crc_calc != crc_recv:
        return None, f"CRC invalide (calc={crc_calc:02X}, reçu={crc_recv:02X})"

    payload = response[1:-1]
    if len(payload) < 3:
        return None, "Réponse invalide (taille)"

    count = (payload[0] << 8) | payload[1]
    status = payload[2]
    if status != LYNKX_ERROR_OK:
        return None, f"Erreur status: 0x{status:02X}"

    return count, None

def parse_fm_info_response(response):
    if not response or len(response) < 3:
        return None, "Réponse vide ou trop courte"

    crc_calc = calculate_crc8(response[:-1])
    crc_recv = response[-1]
    if crc_calc != crc_recv:
        return None, f"CRC invalide (calc={crc_calc:02X}, reçu={crc_recv:02X})"

    payload = response[1:-1]
    entry_size = FM_LOG_INFO_STRUCT.size
    if len(payload) < entry_size + 1:
        return None, "Réponse invalide (taille payload)"

    data = payload[:entry_size]
    status = payload[entry_size]
    if status != LYNKX_ERROR_OK:
        return None, f"Erreur status: 0x{status:02X}"

    entries = parse_fm_log_entries(data)
    if not entries:
        return None, "Réponse vide"
    return entries[0], None

def parse_fm_log_entries(payload):
    entries = []
    entry_size = FM_LOG_INFO_STRUCT.size
    usable = len(payload) - (len(payload) % entry_size)
    for offset in range(0, usable, entry_size):
        fields = FM_LOG_INFO_STRUCT.unpack_from(payload, offset)
        entry = dict(zip(FM_LOG_INFO_FIELDS, fields))
        entries.append(entry)
    return entries

def parse_fm_list_response(response):
    if not response or len(response) < 3:
        return None, "Réponse vide ou trop courte"

    crc_calc = calculate_crc8(response[:-1])
    crc_recv = response[-1]
    if crc_calc != crc_recv:
        return None, f"CRC invalide (calc={crc_calc:02X}, reçu={crc_recv:02X})"

    payload = response[1:-1]
    if len(payload) < 1:
        return None, "Réponse vide"

    status = payload[-1]
    data = payload[:-1]
    entry_size = FM_LOG_INFO_STRUCT.size
    if len(data) % entry_size != 0:
        return None, "Réponse invalide (taille payload)"
    if status != LYNKX_ERROR_OK:
        return None, f"Erreur status: 0x{status:02X}"
    return parse_fm_log_entries(data), None

def fm_is_busy():
    """Vérifie si le File Manager est occupé (logger actif ou effacement en cours)"""
    response = send_lynkx_packet(build_fm_command(LYNKX_CMD_FM_IS_ERASING))
    if not response or len(response) < 4:
        return None, "Réponse vide ou trop courte"

    crc_calc = calculate_crc8(response[:-1])
    crc_recv = response[-1]
    if crc_calc != crc_recv:
        return None, f"CRC invalide (calc={crc_calc:02X}, reçu={crc_recv:02X})"

    busy_flag = response[1]  # 0 = libre, 1 = occupé
    status = response[2]

    if status != LYNKX_ERROR_OK:
        return None, f"Erreur status: 0x{status:02X}"

    return busy_flag == 1, None

def fm_get_log_count():
    response = send_lynkx_packet(build_fm_command(LYNKX_CMD_FM_GET_LOG_COUNT))
    count, err = parse_fm_count_response(response)
    if err:
        return None, err
    return count, None

def fm_get_log_list_page(start_index, out_max):
    out_max = min(out_max, FM_LIST_PAGE_MAX)
    payload = struct.pack(">HB", start_index, out_max)
    response = send_lynkx_packet(build_fm_command(LYNKX_CMD_FM_GET_LIST_PAGE, payload))
    entries, err = parse_fm_list_response(response)
    if entries is None:
        return None, err
    return entries, err

def fm_get_log_info(log_id):
    payload = struct.pack(">I", log_id)
    response = send_lynkx_packet(build_fm_command(LYNKX_CMD_FM_GET_LOG_INFO, payload))
    entry, err = parse_fm_info_response(response)
    if err:
        return None, err
    return entry, None

def fm_read_log_chunk(log_id, offset, length):
    payload = struct.pack(">I I H", log_id, offset, length)
    # Expected RX length: [counter] + data + [out_read_MSB][out_read_LSB][status][CRC]
    expected_len = 1 + length + 4
    response = send_lynkx_packet(
        build_fm_command(LYNKX_CMD_FM_READ_LOG_CHUNK, payload),
        response_timeout=10.0,   # Augmenté pour laisser le temps au firmware
        expected_len=expected_len,
    )

    # Format RX: [counter] [data] [out_read_MSB] [out_read_LSB] [status] [CRC]
    # Minimum: [counter][out_read_MSB][out_read_LSB][status][CRC] = 5 bytes
    if not response or len(response) < 5:
        return None, "Réponse vide ou trop courte"

    crc_calc = calculate_crc8(response[:-1])
    crc_recv = response[-1]
    if crc_calc != crc_recv:
        return None, f"CRC invalide (calc={crc_calc:02X}, reçu={crc_recv:02X})"

    # Extraire status (avant-dernier byte avant CRC)
    status = response[-2]
    if status != LYNKX_ERROR_OK:
        return None, f"Erreur status: 0x{status:02X}"

    # Extraire out_read (2 bytes avant status, big-endian)
    out_read = (response[-4] << 8) | response[-3]

    # Extraire les données (entre counter et footer)
    data = response[1:-4]
    actual_data_len = len(data)

    # Debug: afficher les valeurs extraites
    printT(f"🔍 DEBUG READ_CHUNK: total_len={len(response)}, counter=0x{response[0]:02X}, out_read={out_read}, actual_data={actual_data_len}, status=0x{status:02X}")

    # BUG FIRMWARE CONNU: Le firmware annonce out_read mais est limité par max_resp_len
    # On utilise la longueur réelle des données reçues
    if actual_data_len != out_read:
        printT(f"⚠️  BUG FIRMWARE: out_read={out_read} mais seulement {actual_data_len} bytes reçus (limite max_resp_len)")
        printT(f"   → Utilisation de la longueur réelle: {actual_data_len} bytes")
        # Retourner les données réelles, pas out_read annoncé
        return data, None

    return data, None

def fm_delete_log(log_id):
    payload = struct.pack(">I", log_id)
    response = send_lynkx_packet(build_fm_command(LYNKX_CMD_FM_DELETE_LOG, payload))
    _, err = parse_fm_response(response)
    if err:
        return False, err
    return True, None

def fm_erase_all_logs():
    response = send_lynkx_packet(build_fm_command(LYNKX_CMD_FM_ERASE_ALL_BLOCKING), response_timeout=20.0)
    _, err = parse_fm_response(response)
    if err:
        return False, err
    return True, None

def fm_get_debug_info():
    """Récupère les informations de debug du FileManager

    Retourne un dictionnaire contenant:
    - s_data_wr_ptr: Pointeur d'écriture dans LOG_DATA
    - s_dir_wr_ptr: Pointeur d'écriture dans LOG_DIR
    - s_next_log_id: Prochain log_id qui sera assigné
    - s_dir_seq: Numéro de séquence du répertoire (nombre d'entrées)
    """
    response = send_lynkx_packet(build_fm_command(LYNKX_CMD_FM_GET_DEBUG_INFO))

    if not response or len(response) < 17:  # [CMD_ID] + 14 bytes data + [status] + [CRC]
        return None, "Réponse vide ou trop courte"

    crc_calc = calculate_crc8(response[:-1])
    crc_recv = response[-1]
    if crc_calc != crc_recv:
        return None, f"CRC invalide (calc={crc_calc:02X}, reçu={crc_recv:02X})"

    # Extraire status (avant-dernier byte avant CRC)
    status = response[-2]
    if status != LYNKX_ERROR_OK:
        return None, f"Erreur status: 0x{status:02X}"

    # Parser les données (big-endian)
    # [1..4]   : s_data_wr_ptr   (4 bytes)
    # [5..8]   : s_dir_wr_ptr    (4 bytes)
    # [9..12]  : s_next_log_id   (4 bytes)
    # [13..14] : s_dir_seq       (2 bytes)
    data = response[1:-2]  # Enlever CMD_ID et status+CRC

    if len(data) < 14:
        return None, f"Données insuffisantes ({len(data)} bytes, attendu 14)"

    debug_info = {
        's_data_wr_ptr': struct.unpack_from(">I", data, 0)[0],
        's_dir_wr_ptr': struct.unpack_from(">I", data, 4)[0],
        's_next_log_id': struct.unpack_from(">I", data, 8)[0],
        's_dir_seq': struct.unpack_from(">H", data, 12)[0]
    }

    return debug_info, None

def logger_get_status():
    """Récupère l'état du logger

    Retourne un dictionnaire contenant:
    - running: True si le logger est actif, False sinon
    - last_error: Code d'erreur du dernier échec
    """
    response = send_lynkx_packet(build_fm_command(LYNKX_CMD_LOGGER_GET_STATUS))

    if not response or len(response) < 5:  # [CMD_ID] + 2 bytes data + [status] + [CRC]
        return None, "Réponse vide ou trop courte"

    crc_calc = calculate_crc8(response[:-1])
    crc_recv = response[-1]
    if crc_calc != crc_recv:
        return None, f"CRC invalide (calc={crc_calc:02X}, reçu={crc_recv:02X})"

    # Extraire status
    status = response[-2]
    if status != LYNKX_ERROR_OK:
        return None, f"Erreur status: 0x{status:02X}"

    # Parser les données
    running = response[1]  # 0=stopped, 1=running
    last_error = response[2]  # Code d'erreur du dernier échec

    logger_status = {
        'running': running == 1,
        'last_error': last_error
    }

    return logger_status, None

def logger_stop():
    """Arrête le logger"""
    response = send_lynkx_packet(build_fm_command(LYNKX_CMD_LOGGER_STOP))

    if not response or len(response) < 4:  # [CMD_ID] + [status] + [error] + [CRC]
        return False, None, "Réponse vide ou trop courte"

    crc_calc = calculate_crc8(response[:-1])
    crc_recv = response[-1]
    if crc_calc != crc_recv:
        return False, None, f"CRC invalide (calc={crc_calc:02X}, reçu={crc_recv:02X})"

    status = response[1]
    error_code = response[2] if len(response) > 2 else 0

    if status != LYNKX_ERROR_OK:
        return False, error_code, f"Erreur status: 0x{status:02X}"

    return True, error_code, None

def logger_start(log_type=LOG_TYPE_DEBUG):
    """Démarre le logger

    Args:
        log_type: Type de log (0=DEBUG par défaut)
    """
    payload = struct.pack(">B", log_type)
    response = send_lynkx_packet(build_fm_command(LYNKX_CMD_LOGGER_START, payload))

    if not response or len(response) < 4:  # [CMD_ID] + [status] + [error] + [CRC]
        return False, None, "Réponse vide ou trop courte"

    crc_calc = calculate_crc8(response[:-1])
    crc_recv = response[-1]
    if crc_calc != crc_recv:
        return False, None, f"CRC invalide (calc={crc_calc:02X}, reçu={crc_recv:02X})"

    status = response[1]
    error_code = response[2] if len(response) > 2 else 0

    if status != LYNKX_ERROR_OK:
        return False, error_code, f"Erreur status: 0x{status:02X}"

    return True, error_code, None

def fm_update_listbox(entries):
    fm_listbox.delete(0, END)
    for entry in entries:
        log_id = entry.get("log_id", 0)
        size = entry.get("size_bytes", 0)
        state = entry.get("state", 0)
        fm_listbox.insert(END, f"ID {log_id} | {size} B | state {state}")

def fm_check_busy_status():
    """Vérifie et affiche le statut busy du File Manager"""
    def run():
        busy, err = fm_is_busy()
        if err:
            fm_busy_var.set(f"Erreur: {err}")
            fm_busy_label.config(bg="orange")
            return

        if busy:
            fm_busy_var.set("⚠️ OCCUPÉ")
            fm_busy_label.config(bg="red")
        else:
            fm_busy_var.set("✓ LIBRE")
            fm_busy_label.config(bg="green")

    threading.Thread(target=run, daemon=True).start()

def fm_refresh_list():
    def run():
        global fm_entries
        fm_status_var.set("Lecture liste...")
        fm_progress_var.set("")

        # Vérifier le statut busy automatiquement
        busy, err_busy = fm_is_busy()
        if not err_busy:
            window.after(0, lambda: (
                fm_busy_var.set("⚠️ OCCUPÉ" if busy else "✓ LIBRE"),
                fm_busy_label.config(bg="red" if busy else "green")
            ))

        count, err = fm_get_log_count()
        if err:
            fm_status_var.set(err)
            return

        entries = []
        had_error = False
        if count:
            start = 0
            while start < count:
                page_size = min(FM_LIST_PAGE_MAX, count - start)
                page_entries, err = fm_get_log_list_page(start, page_size)
                if err and not page_entries:
                    fm_status_var.set(err)
                    return
                if not page_entries:
                    break
                entries.extend(page_entries)
                start += len(page_entries)
                if err:
                    had_error = True

        fm_entries = entries
        fm_count_var.set(f"{len(entries)} / {count}")
        if had_error:
            fm_status_var.set("Liste partielle (status KO)")
        else:
            fm_status_var.set("Liste mise a jour")
        window.after(0, lambda: fm_update_listbox(entries))

    threading.Thread(target=run, daemon=True).start()

def fm_on_select(event):
    global fm_selected_id
    selection = fm_listbox.curselection()
    if not selection:
        fm_selected_id = None
        fm_info_var.set("Aucun fichier selectionne")
        return
    index = selection[0]
    if index >= len(fm_entries):
        fm_selected_id = None
        return
    entry = fm_entries[index]
    fm_selected_id = entry.get("log_id")
    info = ", ".join(f"{k}={entry.get(k)}" for k in FM_LOG_INFO_FIELDS if k in entry)
    fm_info_var.set(info)

def fm_show_info():
    if fm_selected_id is None:
        fm_status_var.set("Selectionnez un fichier")
        return

    def run():
        fm_status_var.set("Lecture infos...")
        entry, err = fm_get_log_info(fm_selected_id)
        if err:
            fm_status_var.set(err)
            return
        info = ", ".join(f"{k}={entry.get(k)}" for k in FM_LOG_INFO_FIELDS if k in entry)
        fm_info_var.set(info)
        fm_status_var.set("Infos mises a jour")

    threading.Thread(target=run, daemon=True).start()

def fm_delete_selected():
    if fm_selected_id is None:
        fm_status_var.set("Selectionnez un fichier")
        return
    if not messagebox.askyesno("Supprimer", f"Supprimer le fichier ID {fm_selected_id} ?"):
        return

    def run():
        # Vérifier si le système est occupé
        fm_status_var.set("Verification systeme...")
        busy, err = fm_is_busy()
        if err:
            fm_status_var.set(f"Erreur verification: {err}")
            return
        if busy:
            fm_status_var.set("⚠️ SYSTEME OCCUPE - Logger actif ou effacement en cours")
            messagebox.showwarning("Système occupé", "Le système de logs est actuellement occupé.\nArrêtez le logger avant de supprimer des fichiers.")
            return

        fm_status_var.set("Suppression...")
        ok, err = fm_delete_log(fm_selected_id)
        if not ok:
            fm_status_var.set(err or "Erreur suppression")
            return
        fm_status_var.set("Supprime")
        fm_refresh_list()

    threading.Thread(target=run, daemon=True).start()

def fm_erase_all():
    if not messagebox.askyesno("Effacer tout", "⚠️ ATTENTION ⚠️\n\nEffacer TOUS les logs de manière DÉFINITIVE ?\n\nCette opération est IRRÉVERSIBLE !"):
        return

    def run():
        # Vérifier si le système est occupé
        fm_status_var.set("Verification systeme...")
        busy, err = fm_is_busy()
        if err:
            fm_status_var.set(f"Erreur verification: {err}")
            return
        if busy:
            fm_status_var.set("⚠️ SYSTEME OCCUPE - Logger actif ou effacement en cours")
            messagebox.showwarning("Système occupé", "Le système de logs est actuellement occupé.\nArrêtez le logger avant d'effacer les logs.")
            return

        fm_status_var.set("Effacement en cours (bloquant)...")
        ok, err = fm_erase_all_logs()
        if not ok:
            fm_status_var.set(err or "Erreur effacement")
            return
        fm_status_var.set("Effacement termine")
        fm_refresh_list()

    threading.Thread(target=run, daemon=True).start()

def fm_show_debug_info():
    """Affiche les informations de diagnostic du FileManager"""
    def run():
        fm_status_var.set("Lecture debug info...")
        debug_info, err = fm_get_debug_info()
        if err:
            fm_status_var.set(f"Erreur debug: {err}")
            # Utiliser window.after pour afficher le messagebox dans le thread principal
            window.after(0, lambda: messagebox.showerror("Erreur", f"Impossible de lire les infos de debug:\n{err}"))
            return

        # Constantes pour l'interprétation
        LOG_DATA_BASE = 0x00046000
        LOG_DIR_BASE = 0x001F0000
        LOG_DIR_END = 0x00200000

        s_data_wr_ptr = debug_info['s_data_wr_ptr']
        s_dir_wr_ptr = debug_info['s_dir_wr_ptr']
        s_next_log_id = debug_info['s_next_log_id']
        s_dir_seq = debug_info['s_dir_seq']

        # Calculs utiles
        data_used = s_data_wr_ptr - LOG_DATA_BASE
        dir_used = s_dir_wr_ptr - LOG_DIR_BASE
        dir_remaining = LOG_DIR_END - s_dir_wr_ptr

        # Détection d'états
        is_virgin = (s_data_wr_ptr == LOG_DATA_BASE and
                     s_dir_wr_ptr == LOG_DIR_BASE and
                     s_next_log_id == 1 and
                     s_dir_seq == 0)

        dir_full = s_dir_wr_ptr >= LOG_DIR_END

        # Construction du message
        msg = "═══ FILE MANAGER DEBUG INFO ═══\n\n"
        msg += f"📊 État général:\n"
        if is_virgin:
            msg += "   ✅ Système vierge (après ERASE_ALL)\n\n"
        elif dir_full:
            msg += "   ⚠️ RÉPERTOIRE PLEIN!\n\n"
        else:
            msg += "   🔧 Système actif\n\n"

        msg += f"📍 Pointeurs mémoire:\n"
        msg += f"   s_data_wr_ptr  = 0x{s_data_wr_ptr:08X}\n"
        msg += f"   s_dir_wr_ptr   = 0x{s_dir_wr_ptr:08X}\n\n"

        msg += f"🔢 Compteurs:\n"
        msg += f"   s_next_log_id  = {s_next_log_id}\n"
        msg += f"   s_dir_seq      = {s_dir_seq} entrées\n\n"

        msg += f"💾 Utilisation mémoire:\n"
        msg += f"   DATA utilisée  = {data_used} bytes ({data_used/1024:.1f} KB)\n"
        msg += f"   DIR utilisée   = {dir_used} bytes ({dir_used/1024:.1f} KB)\n"
        msg += f"   DIR restante   = {dir_remaining} bytes ({dir_remaining/1024:.1f} KB)\n\n"

        msg += f"🔍 Diagnostic:\n"
        if is_virgin:
            msg += "   • Système initialisé correctement\n"
            msg += "   • Prêt pour le premier log\n"
        else:
            if s_next_log_id == 1:
                msg += "   ⚠️ s_next_log_id = 1 (anormal après utilisation)\n"
            if s_dir_seq == 0:
                msg += "   ⚠️ s_dir_seq = 0 (aucune entrée DIR)\n"
            elif s_dir_seq > 100:
                msg += f"   ⚠️ s_dir_seq = {s_dir_seq} (trop d'entrées, possible corruption)\n"

            # Vérifier cohérence s_next_log_id vs s_dir_seq
            # Chaque log créé = 2 entrées DIR (OPEN + CLOSE) dans le cas nominal
            expected_min_logs = s_dir_seq // 2
            if s_next_log_id < expected_min_logs:
                msg += f"   ⚠️ Incohérence: next_log_id={s_next_log_id} mais {s_dir_seq} entrées DIR\n"

            if dir_full:
                msg += "   ❌ Répertoire saturé - ERASE_ALL nécessaire\n"

        fm_status_var.set("Debug info OK")
        # Utiliser window.after pour afficher le messagebox dans le thread principal
        window.after(0, lambda: messagebox.showinfo("FileManager Debug Info", msg))

    threading.Thread(target=run, daemon=True).start()

def logger_show_status():
    """Affiche l'état du logger"""
    def run():
        fm_status_var.set("Lecture statut logger...")
        status_info, err = logger_get_status()
        if err:
            fm_status_var.set(f"Erreur statut logger: {err}")
            window.after(0, lambda: messagebox.showerror("Erreur", f"Impossible de lire le statut du logger:\n{err}"))
            return

        running = status_info['running']
        last_error = status_info['last_error']

        error_labels = {
            LOGGER_OK: "Aucune erreur",
            LOGGER_ERR_NOT_RUNNING: "Logger pas démarré",
            LOGGER_ERR_ALREADY_RUNNING: "Logger déjà actif",
            LOGGER_ERR_FM: "Échec FileManager ⚠️",
            LOGGER_ERR_SERIALIZE: "Erreur sérialisation",
            LOGGER_ERR_QUEUE_EMPTY: "File vide"
        }

        msg = "═══ LOGGER STATUS ═══\n\n"
        msg += f"🔄 État actuel:\n"
        if running:
            msg += "   ✅ RUNNING (Logger actif)\n\n"
        else:
            msg += "   ⏸️ STOPPED (Logger arrêté)\n\n"

        msg += f"⚠️ Dernière erreur:\n"
        msg += f"   Code: {last_error}\n"
        msg += f"   Message: {error_labels.get(last_error, f'Erreur inconnue (0x{last_error:02X})')}\n\n"

        if last_error == LOGGER_ERR_FM:
            msg += "🔍 Diagnostic:\n"
            msg += "   ❌ Le FileManager a échoué!\n"
            msg += "   → Cliquez sur '🔍 Debug Info' pour analyser\n"
            msg += "   → Vérifiez que la mémoire n'est pas pleine\n"
            msg += "   → Vérifiez que le système n'est pas busy\n"

        fm_status_var.set(f"Logger: {'RUNNING' if running else 'STOPPED'}")
        window.after(0, lambda: messagebox.showinfo("Logger Status", msg))

    threading.Thread(target=run, daemon=True).start()

def logger_do_start():
    """Démarre le logger"""
    def run():
        fm_status_var.set("Démarrage logger...")
        success, error_code, err = logger_start(LOG_TYPE_DEBUG)

        if not success or err:
            error_labels = {
                LOGGER_ERR_NOT_RUNNING: "Logger pas démarré",
                LOGGER_ERR_ALREADY_RUNNING: "Logger déjà actif",
                LOGGER_ERR_FM: "Échec FileManager",
                LOGGER_ERR_SERIALIZE: "Erreur sérialisation",
                LOGGER_ERR_QUEUE_EMPTY: "File vide"
            }
            error_msg = error_labels.get(error_code, f"Erreur inconnue (code {error_code})")
            if err:
                error_msg += f"\n{err}"

            fm_status_var.set(f"❌ Échec démarrage: {error_msg}")
            window.after(0, lambda: messagebox.showerror("Échec démarrage", f"Impossible de démarrer le logger:\n\n{error_msg}"))
            return

        fm_status_var.set("✅ Logger démarré")
        window.after(0, lambda: messagebox.showinfo("Succès", "Logger démarré avec succès!"))

        # Rafraîchir le debug info automatiquement
        fm_show_debug_info()

    threading.Thread(target=run, daemon=True).start()

def logger_do_stop():
    """Arrête le logger"""
    def run():
        fm_status_var.set("Arrêt logger...")
        success, error_code, err = logger_stop()

        if not success or err:
            error_labels = {
                LOGGER_ERR_NOT_RUNNING: "Logger déjà arrêté",
                LOGGER_ERR_ALREADY_RUNNING: "Logger déjà actif",
                LOGGER_ERR_FM: "Échec FileManager",
                LOGGER_ERR_SERIALIZE: "Erreur sérialisation",
                LOGGER_ERR_QUEUE_EMPTY: "File vide"
            }
            error_msg = error_labels.get(error_code, f"Erreur inconnue (code {error_code})")
            if err:
                error_msg += f"\n{err}"

            fm_status_var.set(f"❌ Échec arrêt: {error_msg}")
            window.after(0, lambda: messagebox.showerror("Échec arrêt", f"Impossible d'arrêter le logger:\n\n{error_msg}"))
            return

        fm_status_var.set("⏸️ Logger arrêté")
        window.after(0, lambda: messagebox.showinfo("Succès", "Logger arrêté avec succès!"))

        # Rafraîchir le debug info automatiquement
        fm_show_debug_info()

    threading.Thread(target=run, daemon=True).start()

def fm_download_selected():
    global window

    if fm_selected_id is None:
        fm_status_var.set("Selectionnez un fichier")
        return

    # Forcer la fenêtre au premier plan (fix macOS)
    window.lift()
    window.attributes('-topmost', True)
    window.after_idle(window.attributes, '-topmost', False)

    save_path = filedialog.asksaveasfilename(
        parent=window,
        title="Enregistrer le fichier",
        defaultextension=".bin",
        filetypes=[("Binary", "*.bin"), ("All files", "*.*")]
    )
    if not save_path:
        return

    def run():
        fm_status_var.set("Telechargement...")
        entry = next((e for e in fm_entries if e.get("log_id") == fm_selected_id), None)
        if not entry:
            entry, err = fm_get_log_info(fm_selected_id)
            if err:
                fm_status_var.set(err)
                return

        total_size = entry.get("size_bytes")
        printT(f"📥 Début téléchargement: log_id={fm_selected_id}, size={total_size} bytes")

        try:
            chunk_size = int(fm_chunk_size_var.get())
        except ValueError:
            chunk_size = FM_READ_CHUNK_MAX

        if chunk_size <= 0:
            chunk_size = FM_READ_CHUNK_MAX
        if chunk_size > 255:
            chunk_size = 255

        printT(f"   Chunk size: {chunk_size} bytes")

        offset = 0
        with open(save_path, "wb") as f:
            while True:
                printT(f"📤 Requête chunk: offset={offset}, len={chunk_size}")
                data, err = fm_read_log_chunk(fm_selected_id, offset, chunk_size)
                if err:
                    fm_status_var.set(err)
                    printT(f"❌ Erreur: {err}")
                    return
                if not data:  # EOF détecté (out_read == 0)
                    printT(f"✅ EOF détecté (data vide)")
                    break
                printT(f"📥 Reçu {len(data)} bytes")
                f.write(data)
                offset += len(data)
                if total_size:
                    fm_progress_var.set(f"{offset} / {total_size} octets")
                    if offset >= total_size:
                        printT(f"✅ Taille totale atteinte ({offset}/{total_size})")
                        break
                else:
                    fm_progress_var.set(f"{offset} octets")

        fm_status_var.set("Telechargement termine")

    threading.Thread(target=run, daemon=True).start()

def open_com():
    global ser
    try:
        if (ser):
            ser.close()
        raw_serial = init_serial_port()
        ser = VerboseSerial(raw_serial, verbose=0)
        ser.open()
        time.sleep(0.1)
        printT(f"✅ Connexion série sur {COM_PORT.get()} établie")
    except Exception as e:
        printT(f"❌ Erreur connexion série : {e}")
        return

def close_com():
    global ser
    try:
        if ser and hasattr(ser, 'is_open') and ser.is_open:
            ser.close()
            printT(f"✅ Port série {COM_PORT.get()} fermé proprement")
        else:
            printT("ℹ️ Aucun port série ouvert")
    except Exception as e:
        printT(f"❌ Erreur fermeture port série : {e}")

def send_uart_command(event=None):
    global ser, uart_entry
    try:
        if not ser or not hasattr(ser, 'is_open') or not ser.is_open:
            printT("❌ Port série non ouvert. Cliquez sur 'Open serial' d'abord.")
            return

        command = uart_entry.get().strip()

        if not command:
            return

        # Détection du format de commande
        if command.startswith('@'):
            # Format hexadécimal: @01A2B3... (envoie des octets binaires)
            # Enlever le @ et convertir les paires hexa en bytes
            hex_string = command[1:]

            try:
                # Convertir la chaîne hexa en bytes
                data_bytes = bytes.fromhex(hex_string)

                # Envoyer via le protocole standard (ajoute id + crc)
                send_lynkx_packet(data_bytes)

            except ValueError:
                printT("❌ Format hexadécimal invalide. Utilisez: @01A2B3...")
                return
        else:
            # Commande texte simple (0-3 ou autre)
            ser.write(command.encode())
            add_terminal_line_all(command, END, prefix="[TX]")

        # Effacer le champ de saisie
        uart_entry.delete(0, END)

    except Exception as e:
        printT(f"❌ Erreur envoi commande : {e}")
        import traceback
        printT(f"Traceback: {traceback.format_exc()}")

def open_tiny():
    printT("[🔍] Recherche de l'analyseur de spectre (tinySA)...")
    found = False
    for port in serial.tools.list_ports.comports():
        if port.vid == VID and port.pid == PID:
            found = True
            break
    if not found:
        printT("❌ tinySA non détecté.")
        return
    printT("✅ tinySA détecté.")

# -----------------------------
# Test and Program the LYNKX device
# -----------------------------
def run_full_configuration(Device_ID_QR_Code, Device_ID_Bar_Code, operator_name, hardware_version):
    global ser, read_thread, term

    clear_all_terminals()

    if (checkMacAddress(Device_ID_QR_Code.get(), Device_ID_Bar_Code.get())==FALSE):
        return

    if (firmware_file=="")or(test_firmware_file==""):
        messagebox.showinfo("Files Error", "Select files")
        return    

    # Étape 1 : Connexion au port série
    open_com()

    # Étape 2 : Attente présence tinySA
    open_tiny()

    # Étape 3 : Attente appareil LYNKX+
    printT("[🔌] Waiting for LYNKX+, please plug device with back port cable...")
    while True:
        try:
            time.sleep(0.2) 
            ser.write(b'?')
            if ser.read() == b'Y':
                break
        except:
            return
    printT("✅ Balise LYNKX connectée.")

    config = LYNKXConfig(MAC_ADDRESS,lynkx_type, hardware_version.get())

    time.sleep(2.0)
    ser.serial.timeout = 10.0
    erase_int_mem()
    erase_ext_mem()
    write_firmware_to_int_mem(test_firmware_file)
    write_backup_firmware_to_ext_mem(firmware_file)
    configure_device(config)
    jump_to_main_app()

    reset_flag=0
    read_thread = threading.Thread(target = test_application, args=())
    read_thread.daemon = True
    read_thread.start()

    return

# -----------------------------
# Update beacon
# -----------------------------
def update_beacon(Device_ID_QR_Code, Device_ID_Bar_Code, hardware_version):
    global ser, read_thread, term, en_backup_var

    clear_all_terminals()

    if (checkMacAddress(Device_ID_QR_Code.get(), Device_ID_Bar_Code.get())==FALSE):
        return

    if (firmware_update_file==""):
        messagebox.showinfo("Files Error", "Select files")
        return    
    if en_backup_var and en_backup_var.get() and (firmware_backup_file==""):
        messagebox.showinfo("Files Error", "Select backup file")
        return

    # Étape 1 : Connexion au port série
    open_com()

    # Étape 3 : Attente appareil LYNKX+
    printT("[🔌] Waiting for LYNKX+, please plug device with back port cable...")
    while True:
        try:
            time.sleep(0.4) 
            ser.write(b'?')
            if ser.read() == b'Y':
                break
        except:
            return
    printT("✅ Balise LYNKX connectée.")

    config = LYNKXConfig(MAC_ADDRESS,lynkx_type, hardware_version.get())

    time.sleep(2.0)
    ser.serial.timeout = 10.0
    erase_int_mem()
    write_firmware_to_int_mem(firmware_update_file)
    if en_backup_var and en_backup_var.get():
        erase_ext_mem()
        write_backup_firmware_to_ext_mem(firmware_backup_file)
    configure_device(config)
    jump_to_main_app()

    read_thread = threading.Thread(target = terminal_log, args=())
    read_thread.daemon = True
    read_thread.start()

    return

# -----------------------------
# Update beacon
# -----------------------------
def terminal_logger():
    global ser, read_thread, term

    clear_all_terminals()

    open_com()

    read_thread = threading.Thread(target = terminal_log, args=())
    read_thread.daemon = True
    read_thread.start()

    return

################################################################################
######################    LYNK SETTINGS    #####################################
################################################################################
class LYNKXConfig():
    def __init__(self,MAC_ADDRESS,lynkx_type, hardware_version):
        if lynkx_type==0:
            self.ProductReference = bytearray(b'LYNKX+          ')
        else:
            self.ProductReference = bytearray(b'LYNKX+ SUMMIT   ')
        if (hardware_version == "1.04"):
            self.HardwareVersion_Major = 1
            self.HardwareVersion_Minor = 4
        else:
            self.HardwareVersion_Major = 1
            self.HardwareVersion_Minor = 2

        self.MACAddress = self.parse_mac_address(MAC_ADDRESS)
        self.RFU0 = 0
        self.RFU1 = 0
        self.RFU2 = 0
        self.RFU3 = 0
        self.RFU4 = 0

    @staticmethod
    def parse_mac_address(mac_str):
        mac_parts = mac_str.split(":")
        mac_bytes = bytearray(int(part, 16) for part in mac_parts)
        return mac_bytes

if __name__ == "__main__":
    try:
        checking_window()
    except Exception as e:
        import traceback
        print(f"Erreur lors du lancement de l'application: {e}")
        traceback.print_exc()
        input("Appuyez sur Entrée pour quitter...")
