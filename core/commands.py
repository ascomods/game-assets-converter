import os, stat
import subprocess

paths = {
    'dbrb_compressor': "dbrb_compressor.exe"
}

def dbrb_compressor(input_path, output_path):
    subprocess.run([paths['dbrb_compressor'], input_path, output_path], stdout=subprocess.DEVNULL)
    os.chmod(output_path, stat.S_IWRITE)