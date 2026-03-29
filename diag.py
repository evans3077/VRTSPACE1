import os
import sys

print(f"PATH: {os.getcwd()}")
print(f"PYTHON: {sys.executable}")
try:
    print(f"LIST: {os.listdir('.')}")
except Exception as e:
    print(f"ERROR listdir: {e}")

try:
    with open('config/settings.py', 'r') as f:
        print(f"READ line 4: {f.readlines()[3].strip()}")
except Exception as e:
    print(f"ERROR read file: {e}")
