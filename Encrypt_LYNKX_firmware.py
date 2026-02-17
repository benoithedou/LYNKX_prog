from Cryptodome.Cipher import AES #python3 -m pip install pycryptodomex
from Cryptodome.Util.Padding import pad
import binascii
import time
import os

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


# Récupérer le chemin absolu du script en cours d'exécution
script_path = os.path.abspath(__file__)

# Déterminer le dossier (répertoire parent) de ce script
script_dir = os.path.dirname(script_path)

# Se placer dans ce dossier
os.chdir(script_dir)

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
    global version_major
    global version_minor 
    global hardware_version
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
                    hardware_version = data[0x4b]

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
    return OK

    print("Encryption completed.")
    print("hardware_version_min : " + str(hardware_version) )
    print("version : " + str(version_major) + '.' + str(version_minor))


input_file = '../LYNKX_firmware/output/LYNKX_firmware_HARD_14_Debug.bin'
#input_file = '/Volumes/LYNKX_drive/rep/LYNKX_firmware/STM32CubeIDE/Debug/LYNKX_firmware.bin'
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
Status = encrypt_file(input_padded_file, temp_file)

if (Status==0):
    # compute CRC32 of encrypted file
    bytes = read_bytes_from_file(temp_file)
    crc32_crypted = calculate_crc32(list(bytes))

    # rename output file 
    # add EPOCH timestamp to filename to uniquify
    timestamp = int(time.time())
    output_file = 'firmwares/LYNKXF' +  str(f"{hardware_version:02d}") + '_' + str(timestamp) + '_' +  str(f"{version_major:02d}") + '.' + str(f"{version_minor:02d}") + '_' + str(format(crc32_clear, 'x')).zfill(8) + '_' + str(format(crc32_crypted, 'x')).zfill(8) +'.blf'
    print(output_file)
    os.rename(temp_file, output_file)
    os.remove(input_padded_file)

else:
    print("check padding of clear file")