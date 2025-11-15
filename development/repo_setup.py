# repo_setup.py
import os
import subprocess
import sys

VENV_DIR = "venv"

# Create venv if it doesn't exist
if not os.path.exists(VENV_DIR):
    print("Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", VENV_DIR])

# Build the path to the python executable inside the venv
if os.name == "nt":
    python_exe = os.path.join(VENV_DIR, "Scripts", "python.exe")
else:
    python_exe = os.path.join(VENV_DIR, "bin", "python")

# Upgrade pip
subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip"])

# Install requirements
subprocess.run([python_exe, "-m", "pip", "install", "-r", "requirements.txt"])

print("Setup complete! Virtual environment is ready.")

# after that run
# .\venv\Scripts\activate
