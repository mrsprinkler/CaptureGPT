"""Build CaptureGPT with PyInstaller and PaddleOCR runtime assets."""

import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path

import paddlex


ROOT = Path(__file__).resolve().parent


def clean_build_outputs() -> None:
    root = ROOT.resolve()
    for name in ("build", "dist"):
        target = ROOT / name
        if target.resolve().parent != root:
            raise RuntimeError(f"Refusing to clean path outside project: {target}")
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def main() -> int:
    clean_build_outputs()

    installed_names = {
        dist.metadata.get("Name", "").lower(): dist.metadata.get("Name", "")
        for dist in importlib.metadata.distributions()
    }
    required_metadata = {
        name.lower(): name
        for name in paddlex.utils.deps.BASE_DEP_SPECS
    }
    metadata_names = sorted(
        installed_names[name]
        for name in required_metadata
        if name in installed_names
    )

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--console",
        "--name",
        "CaptureGPT",
        "--collect-data",
        "paddlex",
        "--collect-binaries",
        "paddle",
        "--collect-binaries",
        "nvidia",
    ]

    for name in metadata_names:
        command.extend(["--copy-metadata", name])

    command.append(str(ROOT / "main.pyw"))

    print("Building CaptureGPT with PaddleOCR and CUDA binaries...")
    print("Output: dist/CaptureGPT/CaptureGPT.exe")
    subprocess.run(command, cwd=ROOT, check=True)

    # Frozen apps resolve settings.json beside the executable.
    output_dir = ROOT / "dist" / "CaptureGPT"
    (output_dir / "settings.json").write_bytes(
        (ROOT / "settings.json").read_bytes()
    )
    print("Build complete. Keep settings.json beside CaptureGPT.exe.")
    print("The first launch may download OCR model files into the user cache.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"PyInstaller failed with exit code {exc.returncode}.", file=sys.stderr)
        raise SystemExit(exc.returncode)
