"""Static, same-origin UI for demonstrating the existing /chat API."""

from pathlib import Path

CHAT_DEMO_HTML = Path(__file__).with_name("chat_demo.html").read_text(encoding="utf-8")
