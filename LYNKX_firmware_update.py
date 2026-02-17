import serial
import time
import math
import os
import glob
import re

################################################################################
######################    LYNK SETTINGS    #####################################
################################################################################
class LYNKXConfig:
    MAC_ADDRESS = "8C:1F:64:EE:61:00:01:CF"

    def __init__(self):
        self.ProductReference = bytearray(b'LYNKX+          ')
        #self.ProductReference = bytearray(b'LYNKX+ SUMMIT   ')
        self.HardwareVersion_Major = 1
        self.HardwareVersion_Minor = 4
        self.MACAddress = self.parse_mac_address(self.MAC_ADDRESS)
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


################################################################################
###############    PROGRAMMING TOOL  SETTINGS    ###############################
################################################################################

#COM_PORT = 'COM4'
#for mac : ls /dev/cu.usbserial-*
COM_PORT = '/dev/cu.usbserial-1120'

# ERASE_EXT_MEM = 1
# WRITE_FIRMWARE_TO_EXT_MEM = 1
# WRITE_BACKUP_FIRMWARE_TO_EXT_MEM = 1
# CONFIGURE_DEVICE = 1
# UPDATE_FIRMWARE = 1
# JUMP_TO_MAIN_APP = 1
# SHIPPING_MODE = 1

ERASE_EXT_MEM = 0 #Not necessary if already programmed
CONFIGURE_DEVICE = 1 #Not necessay if already programmed
WRITE_BACKUP_FIRMWARE_TO_EXT_MEM = 0
ERASE_INT_MEM = 1 #A commenter si planté, permet de l'éteindre
WRITE_FIRMWARE_TO_INT_MEM = 1 #A commenter si planté, permet de l'éteindre
JUMP_TO_MAIN_APP = 1
SHIPPING_MODE = 1
# READ_EXT_MEM = 1

################################################################################
#################    PROGRAMMING TOOL  CODE    #################################
################################################################################

def recent_blf():
    repertoire_courant = os.getcwd()
    fichiers = glob.glob(os.path.join(repertoire_courant + "/firmwares", '*.blf'))
    fichiers_tries = sorted(fichiers, key=lambda x: os.path.getmtime(x))
    
    if not fichiers_tries:
        return None  # Aucun fichier trouvé
    
    return fichiers_tries[-1]


Path_to_firmware_uncrypted = '/Users/benoit/rep/prog LYNKX/LYNKX_firmware.bin'
Path_to_firmware_uncrypted = '/Volumes/LYNKX_drive/rep/LYNKX_firmware/output/LYNKX_firmware_HARD_14_Debug.bin'
#Path_to_firmware_uncrypted = '/Volumes/LYNKX_drive/rep/LYNKX_prog/firmwares/LYNKX_firmware_V1_97.bin'
#Path_to_firmware_crypted = recent_blf()
Path_to_firmware_crypted = Path_to_backup_firmware = './firmwares/LYNKXF14_1758311611_01.99_78d12c2d_75a8ba2c.blf'
#Path_to_firmware_crypted = Path_to_backup_firmware = './firmwares/LYNKXF00_1758226448_01.97_dba617e9_9477528f.blf'
print(Path_to_firmware_crypted)

config = LYNKXConfig()

try:
    ser = serial.Serial(COM_PORT, 921600, serial.EIGHTBITS, serial.PARITY_EVEN, serial.STOPBITS_ONE)
except Exception as e:
    print(COM_PORT , " not available")
    exit()

ser.timeout = 0.2

print("power off the beacon before pluggin it")
while(1):
    try:
        ser.write(b'?')
    except Exception as e:
        print("error")
    else:
        print("waiting for LYNK+")
        rsp = ser.read()
        if rsp == (b'Y'):
            print("LYNKX+ connected")
            ser.timeout = None
            break
        pass

try:
    ERASE_EXT_MEM   # Full EXT MEM erase
    print("Erasing EXT MEM")
    # Erase command
    ser.write(b'F')
    rsp = ser.read()
    if rsp != (b'F'):
        print("command error")
        exit()
    # number of pages to erase MSB first (0xFFFF to mass erase)
    ser.write([0xff])
    ser.write([0xff])

    ser.read() #wait for ack

except NameError:
    pass

try:
    ERASE_INT_MEM   # Full EXT MEM erase
    print("Erasing INT MEM")
    # Erase command
    ser.write(b'E')
    rsp = ser.read()
    if rsp != (b'E'):
        print("command error")
        exit()
    rsp = ser.read()
    if rsp != (b'Y'):
        print("error")
        exit()

except NameError:
    pass

try:
    WRITE_FIRMWARE_TO_EXT_MEM   # write firmware.bin @ 0x0000000
    print("Writing firmware to EXT MEM")
    with open(Path_to_firmware_crypted, mode="rb") as firmware:
        content = firmware.read()
        table_len = len(content)
        page_number = math.floor(table_len / 256)
        orphan_number = table_len % 256
        print(page_number,' pages')
        print(orphan_number, ' orphan bytes')
        
        if (orphan_number!=0):
            content = list(content)
            padding = [0] * (256 - orphan_number)
            content.extend(padding)
            table_len_padded = len(content)
            page_number = math.floor(table_len_padded / 256)
            orphan_number = table_len_padded % 256
            print(page_number,' pages after padding')
            print(orphan_number, ' orphan bytes after padding')

        # write full pages
        ser.write(b'X')
        rsp = ser.read()
        if rsp != (b'X'):
            print("command error")
            exit()
        # address MSB first
        ser.write([((0) >> 24) & 0xff])
        ser.write([((0) >> 16) & 0xff])
        ser.write([((0) >> 8)  & 0xff])
        ser.write([ (0)        & 0xff])
        ser.read() #wait for ack

        # # page number MSB first
        ser.write([(page_number >> 24)  & 0xff])
        ser.write([(page_number >> 16)  & 0xff])
        ser.write([(page_number >> 8 )  & 0xff])
        ser.write([(page_number      )  & 0xff])
        ser.read() #wait for ack

        # # data to write
        print('writing page n°', end = '')
        for i in range(page_number):
            print(' ' ,i , ' ', end = '')
            ser.write(content[(i * 256):(i * 256) + 256])
            # print(content[(i * 256):(i * 256) + 256])
            ser.read() #wait for ack
        print('done')

        ser.read() #wait for ack

except NameError:
    pass

try:
    WRITE_BACKUP_FIRMWARE_TO_EXT_MEM   # write backup firmware.bin @ 0x001C0000
    print("Writing back up firmware to EXT MEM")
    with open(Path_to_backup_firmware, mode="rb") as firmware:
        content = firmware.read()
        table_len = len(content)
        page_number = math.floor(table_len / 256)
        orphan_number = table_len % 256
        print(page_number,' pages')
        print(orphan_number, ' orphan bytes')
        
        if (orphan_number!=0):
            content = list(content)
            padding = [0] * (256 - orphan_number)
            content.extend(padding)
            table_len_padded = len(content)
            page_number = math.floor(table_len_padded / 256)
            orphan_number = table_len_padded % 256
            print(page_number,' pages after padding')
            print(orphan_number, ' orphan bytes after padding')

        # write full pages
        ser.write(b'X')
        rsp = ser.read()
        if rsp != (b'X'):
            print("command error")
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

        # # data to write
        print('writing page n°', end = '')
        for i in range(page_number):
            print(' ' ,i , ' ', end = '')
            ser.write(content[(i * 256):(i * 256) + 256])
            # print(content[(i * 256):(i * 256) + 256])
            ser.read() #wait for ack
        print('done')
        ser.read() #wait for ack

except NameError:
    pass

try:
    WRITE_FIRMWARE_TO_INT_MEM   # write firmware.bin @ 0x08005000
    print("Writing firmware to INT MEM")
    with open(Path_to_firmware_uncrypted, mode="rb") as firmware:
        content = firmware.read()
        table_len = len(content)
        page_number = math.floor(table_len / 256)
        orphan_number = table_len % 256
        print(page_number,' pages')
        print(orphan_number, ' orphan bytes')
        
        if (orphan_number!=0):
            content = list(content)
            padding = [0] * (256 - orphan_number)
            content.extend(padding)
            table_len_padded = len(content)
            page_number = math.floor(table_len_padded / 256)
            orphan_number = table_len_padded % 256
            print(page_number,' pages after padding')
            print(orphan_number, ' orphan bytes after padding')

        # write full pages
        ser.write(b'W')
        rsp = ser.read()
        if rsp != (b'W'):
            print("command error")
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

        # # data to write
        print('writing page n°', end = '')
        for i in range(page_number):
            print(' ' ,i , ' ', end = '')
            ser.write(content[(i * 256):(i * 256) + 256])
            ser.read() #wait for ack
        print('done')
        ser.read() #wait for ack

except NameError:
    pass

try:
    CONFIGURE_DEVICE   # ProductReference, MAC address, hardware rev in external MEM
    print("Configuring  ProductReference, MAC address, hardware rev")
    # Erase command
    ser.write(b'C')
    rsp = ser.read()
    if rsp != (b'C'):
        print("command error")
        exit()
    # ProductReference
    # for i in range(16):
    #     ser.write(b'config.ProductReference[i]')
    #     print(config.ProductReference[i])

    ser.write(config.ProductReference)
    ser.read() #wait for ack

    ser.write([config.HardwareVersion_Major])
    ser.write([config.HardwareVersion_Minor])
    ser.read() #wait for ack

    for i in range(8):
        ser.write([config.MACAddress[i]])
    ser.read() #wait for ack

except NameError:
    pass

try:
    UPDATE_FIRMWARE 
    print("Updating firmware from EXT flash :")
    ser.write(b'U')
    rsp = ser.read()
    if rsp != (b'U'):
        print("  - command error")
        exit()
    print("  - erasing INT flash")
    rsp = ser.read() # waitintg end of INT flash erase
    if rsp != (b'Y'):
        print("error")
        exit()
    print("  - INT flash erased")
    print('  - version = XX.XX')
    print("  - copying firmware from EXT MEM to INT flash")
    rsp = ser.read()
    if rsp != (b'Y'): # waiting end of copy
        print("  - error")
        exit()

except NameError:
    pass

try:
    READ_EXT_MEM 
    print("\nReading EXT MEM ")
    ser.write(b'S')
    rsp = ser.read()
    if rsp != (b'S'):
        print("command error")
        exit()
    rsp = ser.read()
    if rsp != (b'Y'):
        print("error")
        exit()

except NameError:
    pass

try:
    JUMP_TO_MAIN_APP  
    print("\nJumping to main APP")
    # # Go command
    ser.write(b'G')
    rsp = ser.read()
    if rsp != (b'G'):
        print("command error")
        exit()

except NameError:
    pass


try:
    SHIPPING_MODE  
    print("\nGoing to Shipping MODE")
    # # Go command
    ser.write(b'H')
    rsp = ser.read()
    if rsp != (b'H'):
        print("command error")
        exit()

except NameError:
    pass

ser.close()
