"""Generate a pip-compatible requirements.txt from the pixi dependencies.

Creates a temporary venv, pip-installs the direct deps pinned to the versions
from the pixi environment, freezes the result, and writes it to requirements.txt.
This ensures only pip-installable packages end up in the file, with all transitive
deps pinned for reproducibility.
"""

import importlib.metadata as meta
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

with open("pyproject.toml", "rb") as f:
    deps = tomllib.load(f)["tool"]["pixi"]["dependencies"]

skip = {"pip"}
pinned = []
for pkg in sorted(deps):
    if pkg in skip:
        continue
    version = meta.version(pkg)
    pinned.append(f"{pkg}=={version}")

print(f"Direct deps from pixi env: {', '.join(pinned)}")

with tempfile.TemporaryDirectory() as tmpdir:
    venv_path = Path(tmpdir) / "venv"
    pip_path = venv_path / "bin" / "pip"

    print("Creating temporary venv...")
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

    print("Installing pinned deps...")
    subprocess.run(
        [str(pip_path), "install", "--quiet", *pinned],
        check=True,
    )

    result = subprocess.run(
        [str(pip_path), "freeze"],
        capture_output=True, text=True, check=True,
    )

with open("requirements.txt", "w") as f:
    f.write(result.stdout)

n = len(result.stdout.strip().splitlines())
print(f"Updated requirements.txt with {n} packages")
