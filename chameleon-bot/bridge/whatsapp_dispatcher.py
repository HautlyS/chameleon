from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any


class WhatsAppDispatcher:
    def __init__(self, evolution_api_url: str, api_key: str, instance_name: str = "chameleon"):
        self.api_url = evolution_api_url.rstrip("/")
        self.api_key = api_key
        self.instance_name = instance_name

    def _request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        url = f"{self.api_url}/{endpoint}"
        data = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "apikey": self.api_key,
        }
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
            return None

    def send_message(self, to: str, text: str) -> bool:
        result = self._request(f"message/sendText/{self.instance_name}", {
            "number": to,
            "text": text,
        })
        return result is not None and result.get("status") in ("success", 200, "200")

    def send_job_alert(self, to: str, job: dict[str, Any], score: int | None = None) -> bool:
        lines = [
            f"*{job.get('title', 'Unknown Role')}* at {job.get('company', 'Unknown Company')}",
        ]
        if score is not None:
            lines.append(f"Score: {score}/100")
        if job.get("url"):
            lines.append(f"Link: {job['url']}")
        if job.get("salary"):
            lines.append(f"Salary: {job['salary']}")
        if job.get("location"):
            lines.append(f"Location: {job['location']}")
        if job.get("source"):
            lines.append(f"Source: {job['source']}")
        return self.send_message(to, "\n".join(lines))

    def send_tailor_result(self, to: str, title: str, company: str, score: int) -> bool:
        msg = (
            f"Tailored CV ready\n"
            f"Role: {title}\n"
            f"Company: {company}\n"
            f"Match Score: {score}/100"
        )
        return self.send_message(to, msg)

    def send_error(self, to: str, error_msg: str) -> bool:
        return self.send_message(to, f"Chameleon Error: {error_msg}")
