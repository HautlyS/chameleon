from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any


class TelegramDispatcher:
    def __init__(self, bot_token: str, allowed_user_ids: list[int] | None = None):
        self.bot_token = bot_token
        self.allowed_user_ids = allowed_user_ids or []
        self._api_base = f"https://api.telegram.org/bot{bot_token}"

    def _request(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        import urllib.parse
        url = f"{self._api_base}/{method}"
        data = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
            return None

    def send_message(self, text: str, chat_id: int | None = None, parse_mode: str = "Markdown") -> bool:
        targets = [chat_id] if chat_id else self.allowed_user_ids
        ok = True
        for uid in targets:
            result = self._request("sendMessage", {
                "chat_id": uid,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            })
            if result is None or not result.get("ok"):
                ok = False
        return ok

    def send_job_alert(self, job: dict[str, Any], score: int | None = None) -> bool:
        lines = [
            f"*{job.get('title', 'Unknown Role')}*",
            f" at {job.get('company', 'Unknown Company')}",
        ]
        if score is not None:
            badge = "🟢" if score >= 70 else "🟡" if score >= 40 else "⚪"
            lines.append(f" Score: {badge} {score}/100")
        if job.get("url"):
            lines.append(f"\n{job['url']}")
        if job.get("salary"):
            lines.append(f"💰 {job['salary']}")
        if job.get("location"):
            lines.append(f"📍 {job['location']}")
        if job.get("source"):
            lines.append(f"📡 {job['source']}")

        return self.send_message("\n".join(lines))

    def send_tailor_result(self, title: str, company: str, score: int, pdf_path: str | None = None) -> bool:
        msg = [
            f"✅ *Tailored CV ready*",
            f"",
            f"Role: *{title}*",
            f"Company: *{company}*",
            f"Match Score: *{score}/100*",
        ]
        if pdf_path:
            msg.append(f"📄 PDF: `{pdf_path}`")
        return self.send_message("\n".join(msg))

    def send_error(self, error_msg: str) -> bool:
        return self.send_message(f"⚠️ *Chameleon Error*\n{error_msg}")
