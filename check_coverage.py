import subprocess
import sys

result = subprocess.run([
    sys.executable, "-m", "pytest",
    "tests/",
    "--cov=utils",
    "--cov-report=term-missing",
    "--tb=no",
    "-q"
], capture_output=True, text=True)

print(result.stdout)
print(result.stderr)
