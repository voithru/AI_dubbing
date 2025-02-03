import os
import subprocess

def setup_folder_dir(folder_path):
    if os.path.exists(folder_path):
        subprocess.run(["rm", "-rf", folder_path])
    os.makedirs(folder_path)