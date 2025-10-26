import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure the application package is importable when running tests directly
sys.path.append(str(Path(__file__).resolve().parent / "app"))


_REQUIRED_MODULES = ("boto3", "pydantic")


def _missing_modules() -> list[str]:
    missing: list[str] = []
    for module in _REQUIRED_MODULES:
        if importlib.util.find_spec(module) is None:
            missing.append(module)
    return missing


def _install_requirements() -> None:
    requirements = Path(__file__).resolve().parent / "requirements.txt"
    if not requirements.exists():
        raise pytest.UsageError("requirements.txt not found; cannot install dependencies")

    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def pytest_sessionstart(session: pytest.Session) -> None:  # pragma: no cover - test harness hook
    missing = _missing_modules()
    if not missing:
        return

    try:
        _install_requirements()
    except subprocess.CalledProcessError as exc:
        raise pytest.UsageError(
            "Required dependencies missing and automatic installation failed: "
            f"{', '.join(missing)}"
        ) from exc

    still_missing = _missing_modules()
    if still_missing:
        raise pytest.UsageError(
            "Required dependencies are unavailable even after installation: "
            f"{', '.join(still_missing)}"
        )
