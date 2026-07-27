from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any


class WhatsAppDispatcher:
    def __init__(self, evolution_api_url: str, api_key: str, instance_name: str = "chameleon", default_to: str = ""):
        self.api_url = evolution_api_url.rstrip("/")
        self.api_key = api_key
        self.instance_name = instance_name
        self.default_to = default_to

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

    def _request_multipart(self, endpoint: str, fields: dict[str, str], file_path: str) -> dict[str, Any] | None:
        """Send multipart/form-data request (for media)."""
        url = f"{self.api_url}/{endpoint}"
        boundary = "----ChameleonFormBoundary7MA4YW"
        body = bytearray()
        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body.extend(f"{value}\r\n".encode())
        if file_path and os.path.exists(file_path):
            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                file_data = f.read()
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
            body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
            body.extend(file_data)
            body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "apikey": self.api_key}
        try:
            req = urllib.request.Request(url, data=bytes(body), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None

    def send_message(self, to: str, text: str) -> bool:
        if to == "*" and self.default_to:
            return self.send_message(self.default_to, text)
        if to == "*ALL*":
            results = [self.send_message(n, text) for n in self.broadcast_numbers]
            return any(results)
        result = self._request(f"message/sendText/{self.instance_name}", {
            "number": to,
            "text": text,
        })
        return result is not None and result.get("status") in ("success", 200, "200")

    @property
    def broadcast_numbers(self) -> list[str]:
        return getattr(self, "_broadcast", [self.default_to] if self.default_to else [])

    @broadcast_numbers.setter
    def broadcast_numbers(self, numbers: list[str]):
        self._broadcast = numbers
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

    def send_media(self, to: str, file_path: str, caption: str = "") -> bool:
        """Send a file as media via Evolution API."""
        return self._request_multipart(
            f"message/sendMedia/{self.instance_name}",
            {"number": to, "caption": caption[:500]},
            file_path,
        ) is not None

    def send_error(self, to: str, error_msg: str) -> bool:
        return self.send_message(to, f"Chameleon Error: {error_msg}")
