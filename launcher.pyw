import os
import sys
import subprocess

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = os.path.join(base_dir, 'python_runtime', 'pythonw.exe')
    main_script = os.path.join(base_dir, 'main.py')
    
    subprocess.Popen([python_exe, main_script], cwd=base_dir, creationflags=subprocess.CREATE_NO_WINDOW)
