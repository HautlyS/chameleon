from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class ChameleonClient:
    def __init__(self, project_root: str | Path):
        self.root = Path(project_root).resolve()
        sys.path.insert(0, str(self.root))

    def _run_script(self, module: str, args: list[str] | None = None) -> subprocess.CompletedProcess:
        cmd = [sys.executable, "-m", module]
        if args:
            cmd.extend(args)
        return subprocess.run(
            cmd,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def scan_jobs(
        self,
        query: str = "",
        platforms: str = "remoteok,remotive,hn_hiring",
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        args = ["--json"]
        if query:
            args.extend(["--query", query])
        if platforms:
            args.extend(["--platforms", platforms])
        if limit:
            args.extend(["--limit", str(limit)])

        result = self._run_script("scripts.job_scanner", args)

        if result.returncode != 0:
            return [{"error": f"Scanner failed: {result.stderr.strip()}"}]

        try:
            jobs = json.loads(result.stdout)
            if isinstance(jobs, dict) and "error" in jobs:
                return [jobs]
            return jobs if isinstance(jobs, list) else []
        except json.JSONDecodeError:
            return [{"error": f"Failed to parse scan output: {result.stdout[:500]}"}]

    def score_job(self, title: str, company: str, description: str) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"title": title, "company": company, "description": description}, f)
            input_path = f.name

        try:
            result = self._run_script("scripts.job_matcher", [input_path, "--json"])
            if result.returncode == 0:
                return json.loads(result.stdout)
            return {"error": result.stderr.strip(), "score": 0}
        except json.JSONDecodeError:
            return {"error": "Failed to parse score output", "score": 0}
        finally:
            Path(input_path).unlink(missing_ok=True)

    def list_analyses(self) -> list[dict[str, str]]:
        analyses_dir = self.root / "output" / "job_analyses"
        if not analyses_dir.exists():
            return []

        results = []
        for f in sorted(analyses_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                results.append({
                    "id": data.get("analysis_id", f.stem),
                    "company": data.get("company_name", f.stem.split("__")[1] if "__" in f.stem else "unknown"),
                    "role": data.get("role_title", f.stem.split("__")[2] if "__" in f.stem else "unknown"),
                    "path": str(f),
                    "created": data.get("created_at", ""),
                })
            except (json.JSONDecodeError, IndexError):
                continue
        return results

    def list_tailored_cvs(self) -> list[dict[str, str]]:
        templates_dir = self.root / "templates"
        if not templates_dir.exists():
            return []

        results = []
        from scripts.db import get_tailored_cvs
        for row in get_tailored_cvs():
            results.append({
                "id": str(row["id"]),
                "title": row["title"],
                "company": row["company"],
                "score": row.get("score", 0),
                "yaml_path": row.get("yaml_path", ""),
                "pdf_path": row.get("pdf_path", ""),
            })
        return results

    def get_job_analysis(self, analysis_id_or_path: str) -> dict[str, Any] | None:
        p = Path(analysis_id_or_path)
        if p.exists():
            path = p
        else:
            analyses_dir = self.root / "output" / "job_analyses"
            matches = list(analyses_dir.glob(f"*{analysis_id_or_path}*.json"))
            if not matches:
                return None
            path = matches[0]

        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def tailor_cv(
        self,
        jd_text: str,
        company: str = "",
        title: str = "",
        skip_render: bool = False,
    ) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(jd_text)
            jd_path = f.name

        try:
            args = [jd_path]
            if company:
                args.extend(["--company", company])
            if title:
                args.extend(["--title", title])
            if skip_render:
                args.append("--no-render")

            result = self._run_script("scripts.tailor_cv", args)
            if result.returncode == 0:
                return {"success": True, "output": result.stdout.strip()}
            return {"success": False, "error": result.stderr.strip() or result.stdout.strip()}
        finally:
            Path(jd_path).unlink(missing_ok=True)

    def render_cv(self, yaml_path: str | Path) -> dict[str, Any]:
        result = self._run_script("scripts.render", [str(yaml_path)])
        stem = Path(yaml_path).stem
        return {
            "success": result.returncode == 0,
            "yaml": str(yaml_path),
            "pdf": str(self.root / "output" / f"{stem}.pdf"),
            "md": str(self.root / "output" / f"{stem}.md"),
            "error": result.stderr.strip() if result.returncode != 0 else None,
        }

    def cover_letter(self, jd_text: str, cv_path: str | Path | None = None) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(jd_text)
            jd_path = f.name

        try:
            args = [jd_path, "--json"]
            if cv_path:
                args.extend(["--cv", str(cv_path)])
            result = self._run_script("scripts.cover_letter", args)
            if result.returncode == 0:
                return json.loads(result.stdout)
            return {"success": False, "error": result.stderr.strip() or result.stdout.strip()}
        except (json.JSONDecodeError, Exception) as e:
            return {"success": False, "error": str(e)}
        finally:
            Path(jd_path).unlink(missing_ok=True)

    def answer_question(self, question_text: str, jd_text: str = "", cv_path: str | Path | None = None) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(question_text)
            q_path = f.name

        try:
            args = [q_path, "--json"]
            if jd_text:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as jf:
                    jf.write(jd_text)
                    jd_path = jf.name
                args.extend(["--jd", jd_path])
            if cv_path:
                args.extend(["--cv", str(cv_path)])
            result = self._run_script("scripts.question", args)
            if result.returncode == 0:
                return json.loads(result.stdout)
            return {"success": False, "error": result.stderr.strip() or result.stdout.strip()}
        except (json.JSONDecodeError, Exception) as e:
            return {"success": False, "error": str(e)}
        finally:
            Path(q_path).unlink(missing_ok=True)
