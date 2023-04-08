import os, stat
import subprocess

base_paths = [
    '',
    os.path.abspath(os.path.dirname(__file__) + '/../misc') + '/'
]

paths = {
    'dbrb_compressor': "dbrb_compressor.exe",
    'nvtri_stripper': "NvTriStripper.exe"
}

def dbrb_compressor(input_path, output_path):
    for base_path in base_paths:
        try:
            subprocess.run([
                f"{base_path}{paths['dbrb_compressor']}",
                input_path,
                output_path
            ],
            stdout=subprocess.DEVNULL)
            os.chmod(output_path, stat.S_IWRITE | stat.S_IREAD)
            break
        except Exception as e:
            pass

def nvtri_stripper(input_path, output_path):
    for base_path in base_paths:
        try:
            status_code = subprocess.run([
                f"{base_path}{paths['nvtri_stripper']}",
                input_path,
                output_path
            ],
            stdout=subprocess.DEVNULL)
            
            if (status_code == 0):
                break
        except Exception as e:
            pass