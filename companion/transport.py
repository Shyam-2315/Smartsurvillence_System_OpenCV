from __future__ import annotations
import json, socket
from typing import Protocol
from urllib.request import Request, urlopen

class Transport(Protocol):
    def send(self, payload: dict) -> None: ...

class UdpTransport:
    def __init__(self, host: str, port: int) -> None: self.destination = (host, port)
    def send(self, payload: dict) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock: sock.sendto(json.dumps(payload, separators=(",", ":")).encode(), self.destination)

class HttpTransport:
    """Ground-backend transport; the device key is sent but never logged."""
    def __init__(self, url: str, device_key: str) -> None: self.url, self.device_key = url, device_key
    def send(self, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        request = Request(self.url, data=body, method="POST", headers={"Content-Type":"application/json", "X-Companion-Key":self.device_key})
        with urlopen(request, timeout=5): pass
