"""Check send_html_email: sends a sample styled email and verifies its MIME structure.

WARNING: uses the real 'lucaso' account in .env and SENDS 1 real email to itself.
The email is LEFT in the inbox on purpose, so you can see how it renders on phone and web.

Run: python tests/html_email.py
"""
import email
import imaplib
import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from dotenv import load_dotenv
load_dotenv(PROJECT / ".env")

from src.mcp.tools import ACCOUNTS, html_to_text, send_html_email, search_emails_by_subject  # noqa: E402

account = "lucaso"
cfg = ACCOUNTS[account]

HTML = """\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;">
  <tr><td align="center" style="padding:24px 12px;">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0"
           style="max-width:600px;width:100%;background:#ffffff;border-radius:8px;font-family:Arial,Helvetica,sans-serif;">
      <tr><td style="background:#1f2a44;color:#ffffff;padding:24px;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;font-size:24px;">mailMCP HTML test</h1>
        <p style="margin:8px 0 0;color:#c9d1e6;">If you can read this styled, send_html_email works.</p>
      </td></tr>
      <tr><td style="padding:0;">
        <img src="https://placehold.co/600x160/png?text=mailMCP" width="600" alt="mailMCP banner"
             style="display:block;width:100%;max-width:600px;height:auto;">
      </td></tr>
      <tr><td style="padding:24px;color:#1b1b1b;font-size:15px;line-height:1.5;">
        <p style="margin:0 0 16px;">Sample content table:</p>
        <table role="presentation" width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
          <tr style="background:#eef1f8;"><td><b>Tool</b></td><td><b>Status</b></td></tr>
          <tr><td style="border-top:1px solid #dde2ee;">send_html_email</td><td style="border-top:1px solid #dde2ee;color:#1a7f37;">OK</td></tr>
          <tr><td style="border-top:1px solid #dde2ee;">flag_email</td><td style="border-top:1px solid #dde2ee;color:#1a7f37;">OK</td></tr>
        </table>
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0 0;">
          <tr><td style="background:#2f6fed;border-radius:6px;">
            <a href="https://mail.google.com" style="display:inline-block;padding:12px 24px;color:#ffffff;text-decoration:none;font-weight:bold;">Open Gmail</a>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </td></tr>
</table>
"""

print("plain-text fallback preview:\n" + html_to_text(HTML) + "\n")

subject = f"mailMCP HTML test {int(time.time())}"
print(send_html_email(account, cfg["user"], subject, HTML))

found = []
for _ in range(6):
    found = json.loads(search_emails_by_subject(account, subject))
    if found:
        break
    time.sleep(5)
uid = found[0]["emailId"]
print("UID:", uid)

mail = imaplib.IMAP4_SSL(cfg["imap_host"])
mail.login(cfg["user"], cfg["password"])
try:
    mail.select("INBOX", readonly=True)
    _, data = mail.uid("FETCH", uid, "(FLAGS BODY.PEEK[])")
    flags = data[0][0].decode()
    msg = email.message_from_bytes(data[0][1])
finally:
    mail.logout()

print("content types:", [part.get_content_type() for part in msg.walk()])
print("flags after search (PEEK should not add \\Seen, unless Gmail already marked it):", flags)
print("Left in INBOX for visual check.")
