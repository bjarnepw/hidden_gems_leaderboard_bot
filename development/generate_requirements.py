import subprocess
import sys

# Determine pip executable in current Python environment
pip_exe = [sys.executable, "-m", "pip"]

# Generate requirements.txt
with open("requirements.txt", "w") as f:
    subprocess.run(pip_exe + ["freeze"], stdout=f)

print("requirements.txt generated successfully!")
