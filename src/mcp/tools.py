import imaplib
import smtplib
import email
import json
import os
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
        "password": os.getenv("PERSONAL_PASSWORD")
    },
    "jazer": {
        "imap_host": "imap.gmail.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "user": os.getenv("SPAM_USER"),
        "password": os.getenv("SPAM_PASSWORD")
    },
}


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
        _, data = mail.search(None, "ALL")
        ids = data[0].split()[-limit:]
        results = []
        for eid in reversed(ids):
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            body = extract_body(msg)
            results.append({
                "From": msg['From'],
                "Subject": msg['Subject'],
                "Abstract": body[:50],
                "emailId": eid.decode(),
            })
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

    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)

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
        _, data = mail.search(None, f'SUBJECT "{query}"')
        ids = data[0].split()
        results = []
        for eid in reversed(ids):
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            body = extract_body(msg)
            results.append({
                "From": msg['From'],
                "Subject": msg['Subject'],
                "Abstract": body[:50],
                "emailId": eid.decode(),
            })
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
        _, data = mail.search(None, f'FROM "{query}"')
        ids = data[0].split()
        results = []
        for eid in reversed(ids):
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            body = extract_body(msg)
            results.append({
                "From": msg['From'],
                "Subject": msg['Subject'],
                "Abstract": body[:50],
                "emailId": eid.decode(),
            })
        return json.dumps(results, ensure_ascii=False, indent=2)
    finally:
        mail.logout()


@mcp.tool()
def get_email(account: str, email_id: str, folder: str = "INBOX") -> str:
    """Retrieve a full email by ID"""
    cfg = ACCOUNTS.get(account)
    if not cfg:
        return f"Account '{account}' not found."

    mail = imaplib.IMAP4_SSL(cfg["imap_host"])
    mail.login(cfg["user"], cfg["password"])
    try:
        mail.select(folder)
        _, msg_data = mail.fetch(email_id, "(RFC822)")
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
    """Delete an email by ID"""
    cfg = ACCOUNTS.get(account)
    if not cfg:
        return f"Account '{account}' not found."

    mail = imaplib.IMAP4_SSL(cfg["imap_host"])
    mail.login(cfg["user"], cfg["password"])
    try:
        mail.select(folder)
        _, msg_data = mail.fetch(email_id, "(RFC822)")
        if not msg_data[0]:
            return f"Email with ID '{email_id}' not found."

        mail.store(email_id, '+FLAGS', '\\Deleted')
        mail.expunge()
        return f"Email with ID '{email_id}' deleted successfully."
    finally:
        mail.logout()
