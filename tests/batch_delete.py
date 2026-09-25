"""Check delete_emails: moves several UIDs to Trash in one call and reports bad IDs.

WARNING: uses the real 'lucaso' account in .env and SENDS 3 real emails to itself,
then moves them to Trash.

Run: python tests/batch_delete.py
"""
import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from dotenv import load_dotenv
load_dotenv(PROJECT / ".env")

from src.mcp.tools import ACCOUNTS, send_email, search_emails_by_subject, delete_emails  # noqa: E402

account = "lucaso"
tag = f"mailMCP batch {int(time.time())}"
for n in range(3):
    print(send_email(account, ACCOUNTS[account]["user"], f"{tag} #{n}", "Batch delete test."))

found = []
for _ in range(6):
    found = json.loads(search_emails_by_subject(account, tag))
    if len(found) == 3:
        break
    time.sleep(5)
uids = [e["emailId"] for e in found]
print("found UIDs:", uids)

print(delete_emails(account, uids + ["999999999", "abc"]))
print("still in INBOX after delete:", json.loads(search_emails_by_subject(account, tag)))
