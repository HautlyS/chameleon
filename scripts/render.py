#!/usr/bin/env python3
"""Render a RenderCV YAML file to output/, using the venv rendercv binary."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_BIN = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
RENDERCV = VENV_BIN / ("rendercv.exe" if sys.platform == "win32" else "rendercv")


def _find_rendercv() -> Path | None:
    """Locate the rendercv binary, checking venv, PATH, and common locations."""
    if RENDERCV.exists():
        return RENDERCV
    # Check if rendercv is on PATH
    import shutil as _shutil
    on_path = _shutil.which("rendercv")
    if on_path:
        return Path(on_path)
    return None


def render_yaml(yaml_path: Path) -> tuple[bool, str]:
    """Render a YAML file to PDF. Returns (success, message_or_pdf_path)."""
    rendercv = _find_rendercv()
    if rendercv is None:
        return False, "rendercv not found. Run: make install-tools"

    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)

    stem = yaml_path.stem
    tmp = ROOT / yaml_path.name
    shutil.copy2(yaml_path, tmp)

    try:
        result = subprocess.run(
            [
                str(rendercv), "render", str(tmp),
                "--pdf-path",      str(output_dir / f"{stem}.pdf"),
                "--typst-path",    str(output_dir / f"{stem}.typ"),
                "--markdown-path", str(output_dir / f"{stem}.md"),
                "--html-path",     str(output_dir / f"{stem}.html"),
                "--png-path",      str(output_dir / f"{stem}.png"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        tmp.unlink(missing_ok=True)

    if result.returncode == 0:
        pdf_path = output_dir / f"{stem}.pdf"
        return True, str(pdf_path) if pdf_path.exists() else "Rendered (no PDF)"
    else:
        err = (result.stderr or result.stdout or "unknown error").strip()[:300]
        return False, err


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/render.py <path-to-yaml>")
        sys.exit(1)

    source = Path(sys.argv[1].strip())
    if not source.exists():
        print(f"Error: {source} not found")
        sys.exit(1)

    ok, msg = render_yaml(source)
    if ok:
        print(f"Rendered: {msg}")
    else:
        print(f"Error: {msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
