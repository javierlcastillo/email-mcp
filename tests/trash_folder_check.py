"""Offline check of find_trash_folder against fake IMAP LIST responses. No network, no .env needed.

Run: python tests/trash_folder_check.py
Expected output: [Gmail]/Papelera, then the [Gmail]/Trash fallback.
"""
import importlib.util
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "src" / "mcp" / "tools.py"
spec = importlib.util.spec_from_file_location("t", TOOLS)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class M:
    def __init__(self, lines):
        self.lines = lines

    def list(self):
        return "OK", self.lines


print(t.find_trash_folder(M([b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Trash) "/" "[Gmail]/Papelera"'])))
print(t.find_trash_folder(M([b'(\\HasNoChildren) "/" "INBOX"'])))
