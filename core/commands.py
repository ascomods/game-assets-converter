import os, stat
import shutil
import subprocess
import core.common as cm

base_paths = [
    '',
    os.path.join(cm.run_path, 'misc')
]

paths = {
    'dbrb_compressor': "dbrb_compressor.exe",
    'nvtri_stripper': "nvtri_stripper.exe"
}

def dbrb_compressor(input_path, output_path):
    for base_path in base_paths:
        exe_path = os.path.join(base_path, paths['dbrb_compressor'])
        if (shutil.which(exe_path) != None):
            subprocess.run([
                exe_path,
                input_path,
                output_path
            ],
            stdout=subprocess.DEVNULL)
            os.chmod(output_path, stat.S_IWRITE | stat.S_IREAD)
            break

def nvtri_stripper(input_path, output_path):
    for base_path in base_paths:
        exe_path = os.path.join(base_path, paths['nvtri_stripper'])
        if (shutil.which(exe_path) != None):
            subprocess.run([
                exe_path,
                input_path,
                output_path
            ],
            stdout=subprocess.DEVNULL)
            break