"""Check flag_email (star / unstar) and unsubscribe in dry-run mode.

WARNING: uses the real 'lucaso' account in .env and SENDS 1 real email to itself,
stars/unstars it, then moves it to Trash. unsubscribe runs with dry_run=True only:
nothing is POSTed or sent.

Run: python tests/flag_unsubscribe.py
"""
import imaplib
import json
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from dotenv import load_dotenv
load_dotenv(PROJECT / ".env")

from src.mcp.tools import (  # noqa: E402
    ACCOUNTS, send_email, search_emails_by_subject, flag_email, delete_email, unsubscribe,
)

account = "lucaso"
cfg = ACCOUNTS[account]


def read_flags(uid: str) -> str:
    mail = imaplib.IMAP4_SSL(cfg["imap_host"])
    mail.login(cfg["user"], cfg["password"])
    try:
        mail.select("INBOX")
        _, data = mail.uid("FETCH", uid, "(FLAGS)")
        return data[0].decode()
    finally:
        mail.logout()


# --- flag_email ---
subject = f"mailMCP flag test {int(time.time())}"
print(send_email(account, cfg["user"], subject, "Flag test."))
found = []
for _ in range(6):
    found = json.loads(search_emails_by_subject(account, subject))
    if found:
        break
    time.sleep(5)
uid = found[0]["emailId"]
print("test UID:", uid)
print(flag_email(account, uid))
print("  flags:", read_flags(uid))
print(flag_email(account, uid, flagged=False))
print("  flags:", read_flags(uid))
print(delete_email(account, uid))
print(flag_email(account, "999999999"))

# --- unsubscribe dry run on the latest 20 INBOX emails (PEEK only, nothing sent) ---
mail = imaplib.IMAP4_SSL(cfg["imap_host"])
mail.login(cfg["user"], cfg["password"])
mail.select("INBOX", readonly=True)
_, data = mail.uid("SEARCH", None, "ALL")
mail.logout()
methods = Counter()
examples = {}
for u in data[0].split()[-20:]:
    res = json.loads(unsubscribe(account, u.decode(), dry_run=True))
    methods[res["method"]] += 1
    examples.setdefault(res["method"], (u.decode(), res))
print("\nunsubscribe dry run over last 20 emails:", dict(methods))
for method, (u, res) in examples.items():
    print(f"  example {method} (UID {u}): {res['result']}")
