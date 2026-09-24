import imaplib
import smtplib
import email
import json
import os
import re
import base64
import urllib.error
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from typing import Annotated
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = FastMCP(
    "email-manager",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    )
)

ACCOUNTS = {
    "lucaso": {
        "imap_host": "imap.gmail.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "user": os.getenv("PERSONAL_USER"),
        "password": os.getenv("PERSONAL_PASSWORD"),
        "refresh_token": os.getenv("PERSONAL_REFRESH_TOKEN"),
    },
    "jazer": {
        "imap_host": "imap.gmail.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "user": os.getenv("SPAM_USER"),
        "password": os.getenv("SPAM_PASSWORD"),
        "refresh_token": os.getenv("SPAM_REFRESH_TOKEN"),
    },
}

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")

# Max UIDs per IMAP command, to keep command lines short
BATCH_SIZE = 200


def extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                payload = part.get_payload(decode=True)
                return payload.decode('utf-8', errors='ignore') if isinstance(payload, bytes) else str(payload)
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                return payload.decode('utf-8', errors='ignore') if isinstance(payload, bytes) else str(payload)
        return ""
    else:
        payload = msg.get_payload(decode=True)
        if payload is None:
            return ""
        return payload.decode('utf-8', errors='ignore') if isinstance(payload, bytes) else str(payload)


def fetch_summary(mail, uid: bytes) -> dict:
    _, msg_data = mail.uid("FETCH", uid, "(RFC822)")
    msg = email.message_from_bytes(msg_data[0][1])
    body = extract_body(msg)
    return {
        "From": msg['From'],
        "Subject": msg['Subject'],
        "Abstract": body[:50],
        "emailId": uid.decode(),
    }


def find_trash_folder(mail) -> str:
    """Locate the trash mailbox by its \\Trash flag, since Gmail localizes its name."""
    _, folders = mail.list()
    for raw in folders:
        line = raw.decode() if isinstance(raw, bytes) else raw
        if "\\Trash" in line:
            return line.rsplit(' "/" ', 1)[-1].strip().strip('"')
    return "[Gmail]/Trash"


def move_to_trash(mail, uids: list[str]) -> str:
    """Move the given UIDs to Trash in batches; returns the trash folder name."""
    trash = find_trash_folder(mail)
    for i in range(0, len(uids), BATCH_SIZE):
        uid_set = ",".join(uids[i:i + BATCH_SIZE])
        try:
            typ, _ = mail.uid("MOVE", uid_set, f'"{trash}"')
        except imaplib.IMAP4.error:
            typ = "BAD"
        if typ != "OK":
            # Fallback for servers without MOVE: expunge only these UIDs, not every \Deleted message
            mail.uid("COPY", uid_set, f'"{trash}"')
            mail.uid("STORE", uid_set, "+FLAGS", "(\\Deleted)")
            mail.uid("EXPUNGE", uid_set)
    return trash


def send_via_gmail_api(cfg: dict, msg: MIMEText) -> None:
    """Send through the Gmail REST API over HTTPS, since Render blocks SMTP ports."""
    token_req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode({
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "refresh_token": cfg["refresh_token"],
            "grant_type": "refresh_token",
        }).encode(),
    )
    with urllib.request.urlopen(token_req, timeout=15) as resp:
        access_token = json.load(resp)["access_token"]

    send_req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(send_req, timeout=15):
        pass


def send_via_smtp(cfg: dict, msg: MIMEText) -> None:
    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=15) as server:
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("Server is OK", status_code=200)


@mcp.tool()
def list_emails(account: str, folder: str = "INBOX", limit: Annotated[int, "Max number of emails to fetch"] = 10) -> str:
    """List recent emails from a given account and folder"""
    cfg = ACCOUNTS.get(account)
    if not cfg:
        return f"Account '{account}' not found"

    mail = imaplib.IMAP4_SSL(cfg["imap_host"])
    mail.login(cfg["user"], cfg["password"])
    try:
        mail.select(folder)
        _, data = mail.uid("SEARCH", None, "ALL")
        uids = data[0].split()[-limit:]
        results = [fetch_summary(mail, uid) for uid in reversed(uids)]
        return json.dumps(results, ensure_ascii=False, indent=2)
    finally:
        mail.logout()


@mcp.tool()
def send_email(account: str, to: str, subject: str, body: str) -> str:
    """Send an email from the specified account."""
    cfg = ACCOUNTS.get(account)
    if not cfg:
        return f"Account '{account}' not found."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = cfg["user"]
    msg["To"] = to

    try:
        if cfg["refresh_token"]:
            send_via_gmail_api(cfg, msg)
        else:
            send_via_smtp(cfg, msg)
    except urllib.error.HTTPError as e:
        return f"Gmail API error {e.code}: {e.read().decode(errors='ignore')}"
    except OSError as e:
        return f"Failed to send email: {e}"

    return f"Email sent to {to} successfully."


@mcp.tool()
def search_emails_by_subject(account: str, query: str, folder: str = "INBOX") -> str:
    """Search emails by subject keyword"""
    cfg = ACCOUNTS.get(account)
    if not cfg:
        return f"Account '{account}' not found."

    mail = imaplib.IMAP4_SSL(cfg["imap_host"])
    mail.login(cfg["user"], cfg["password"])
    try:
        mail.select(folder)
        _, data = mail.uid("SEARCH", None, f'SUBJECT "{query}"')
        results = [fetch_summary(mail, uid) for uid in reversed(data[0].split())]
        return json.dumps(results, ensure_ascii=False, indent=2)
    finally:
        mail.logout()


@mcp.tool()
def search_emails_by_sender(account: str, query: str, folder: str = "INBOX") -> str:
    """Search emails by sender address"""
    cfg = ACCOUNTS.get(account)
    if not cfg:
        return f"Account '{account}' not found."

    mail = imaplib.IMAP4_SSL(cfg["imap_host"])
    mail.login(cfg["user"], cfg["password"])
    try:
        mail.select(folder)
        _, data = mail.uid("SEARCH", None, f'FROM "{query}"')
        results = [fetch_summary(mail, uid) for uid in reversed(data[0].split())]
        return json.dumps(results, ensure_ascii=False, indent=2)
    finally:
        mail.logout()


@mcp.tool()
def get_email(account: str, email_id: str, folder: str = "INBOX") -> str:
    """Retrieve a full email by its UID"""
    cfg = ACCOUNTS.get(account)
    if not cfg:
        return f"Account '{account}' not found."

    mail = imaplib.IMAP4_SSL(cfg["imap_host"])
    mail.login(cfg["user"], cfg["password"])
    try:
        mail.select(folder)
        _, msg_data = mail.uid("FETCH", email_id, "(RFC822)")
        if not msg_data[0]:
            return f"Email with ID '{email_id}' not found."

        msg = email.message_from_bytes(msg_data[0][1])
        body = extract_body(msg)

        return json.dumps({
            "From": msg['From'],
            "To": msg['To'],
            "Subject": msg['Subject'],
            "Date": msg['Date'],
            "Body": body,
            "emailId": email_id,
        }, ensure_ascii=False, indent=2)
    finally:
        mail.logout()


@mcp.tool()
def delete_email(account: str, email_id: str, folder: str = "INBOX") -> str:
    """Move an email to Trash by its UID"""
    cfg = ACCOUNTS.get(account)
    if not cfg:
        return f"Account '{account}' not found."

    mail = imaplib.IMAP4_SSL(cfg["imap_host"])
    mail.login(cfg["user"], cfg["password"])
    try:
        mail.select(folder)
        _, msg_data = mail.uid("FETCH", email_id, "(UID)")
        if not msg_data[0]:
            return f"Email with ID '{email_id}' not found."

        trash = move_to_trash(mail, [email_id])
        return f"Email with ID '{email_id}' moved to {trash}."
    finally:
        mail.logout()


@mcp.tool()
def delete_emails(account: str, email_ids: list[str], folder: str = "INBOX") -> str:
    """Move several emails to Trash in one call, by their UIDs"""
    cfg = ACCOUNTS.get(account)
    if not cfg:
        return f"Account '{account}' not found."

    requested = list(dict.fromkeys(uid.strip() for uid in email_ids))
    valid = [uid for uid in requested if uid.isdigit()]
    invalid = [uid for uid in requested if not uid.isdigit()]

    mail = imaplib.IMAP4_SSL(cfg["imap_host"])
    mail.login(cfg["user"], cfg["password"])
    try:
        mail.select(folder)
        existing = set()
        for i in range(0, len(valid), BATCH_SIZE):
            _, data = mail.uid("FETCH", ",".join(valid[i:i + BATCH_SIZE]), "(UID)")
            for item in data:
                if item:
                    line = item.decode() if isinstance(item, bytes) else str(item)
                    existing.update(re.findall(r"UID (\d+)", line))

        to_move = [uid for uid in valid if uid in existing]
        trash = move_to_trash(mail, to_move) if to_move else None
        return json.dumps({
            "moved": to_move,
            "not_found": [uid for uid in valid if uid not in existing],
            "invalid": invalid,
            "trash": trash,
        }, ensure_ascii=False, indent=2)
    finally:
        mail.logout()
