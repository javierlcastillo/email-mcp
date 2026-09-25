"""End-to-end check: list, get, send, search and delete (to Trash).

WARNING: uses the real accounts in .env and SENDS a real email to each account's own address,
then moves it to Trash.

Run: python tests/e2e_mail.py [account ...]   (no args = every account)
"""
import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from dotenv import load_dotenv
load_dotenv(PROJECT / ".env")

from src.mcp.tools import (  # noqa: E402  (must import after load_dotenv)
    ACCOUNTS, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET,
    list_emails, get_email, send_email, search_emails_by_subject, delete_email,
)

print(f"GMAIL_CLIENT_ID set: {bool(GMAIL_CLIENT_ID)} | GMAIL_CLIENT_SECRET set: {bool(GMAIL_CLIENT_SECRET)}")

for account, cfg in ACCOUNTS.items():
    if len(sys.argv) > 1 and account not in sys.argv[1:]:
        continue
    print(f"\n==================== {account} ====================")
    print(f"[1] user set: {bool(cfg['user'])} | password set: {bool(cfg['password'])} | "
          f"refresh_token set: {bool(cfg['refresh_token'])} -> send via "
          f"{'Gmail API' if cfg['refresh_token'] else 'SMTP'}")

    listed = json.loads(list_emails(account, limit=3))
    print("[2] list_emails UIDs:", [e["emailId"] for e in listed])

    if listed:
        first = json.loads(get_email(account, listed[0]["emailId"]))
        match = first["Subject"] == listed[0]["Subject"]
        print(f"[3] get_email({listed[0]['emailId']}) subject matches list: {match}")

    subject = f"mailMCP test {account} {int(time.time())}"
    print("[4] send_email:", send_email(account, cfg["user"], subject, "Test from local e2e script."))

    found = []
    for attempt in range(6):
        found = json.loads(search_emails_by_subject(account, subject))
        if found:
            break
        time.sleep(5)
    print(f"[5] search_emails_by_subject found: {[e['emailId'] for e in found]} (attempts: {attempt + 1})")

    if len(found) == 1:
        print("[6] delete_email:", delete_email(account, found[0]["emailId"]))
        after = json.loads(search_emails_by_subject(account, subject))
        print(f"    still in INBOX after delete: {bool(after)}")
    else:
        print("[6] skipped delete: expected exactly one match")
