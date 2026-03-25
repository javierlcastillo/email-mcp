import imaplib 
import smtplib
import email
import json
from email.mime.text import MIMEText
from mcp.server.fastmcp import FastMCP
from typing import Annotated
from dotenv import load_dotenv
import os

# nombre del servidor que sera mostrado en Claude
mcp = FastMCP("email-manager")
load_dotenv()
# Registro de cuentas y sus nombres en Claude
ACCOUNTS = {
    "personal": {
        "imap_host": "imap.gmail.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "user": os.getenv("PERSONAL_USER"),
        "password": os.getenv("PERSONAL_PASSWORD")
    },
    "spam": {
        "imap_host": "imap.gmail.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "user": os.getenv("SPAM_USER"),
        "password": os.getenv("SPAM_USER")
    },
    # "school": {
    #     "imap_host": "outlook.office365.com",
    #     "smtp_host": "smtp.gmail.com",
    #     "smtp_port": 587,
    #     "user": "A01658415@tec.mx",
    #     "password": ""
    # },
    # "work": {
    #     "imap_host": "outlook.office365.com",
    #     "smtp_host": "smtp.gmail.com",
    #     "smtp_port": 587,
    #     "user": "javier.luiscastillo@ibm.com",
    #     "password": ""
    # }
}

@mcp.tool()
def list_emails(account: str, folder: str = "INBOX", limit: Annotated[int, "Max number of emails to fetch "] = 10) -> str: 
    """Lis recent emails from a given account and folder"""
    cfg = ACCOUNTS.get(account)
    if not cfg:
        return f"Account '{account} not found"
    
    mail = imaplib.IMAP4_SSL(cfg["imap_host"]) #conexion SSL al servidor
    mail.login(cfg["user"], cfg["password"])
    mail.select(folder)

    _,data = mail.search(None, "ALL")
    ids = data[0].split()[-limit:] # devuelve unicmane el numero de elementos
    results = []
    for eid in reversed(ids):
        _, msg_data = mail.fetch(eid, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        if msg.is_multipart():
            payload = msg.get_payload(0).get_payload(decode=True)
            if payload is None:
                body = ""
            elif isinstance(payload, bytes):
                body = payload.decode('utf-8', errors='ignore')
            else:
                body = str(payload)
        else:
            payload = msg.get_payload(decode=True)
            if payload is None:
                body = ""
            elif isinstance(payload, bytes):
                body = payload.decode('utf-8', errors='ignore')
            else:
                body = str(payload)
        my_mail = {
            "From": msg['From'],
            "Subject": msg['Subject'],
            "Abstract": body[:50],
            "emailId": eid.decode(),
        }
        results.append(my_mail)

    mail.logout()
    return json.dumps(results, ensure_ascii=False, indent=2)

# No se si funciona. Ahorita unicamente probe list emails
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
def search_emails(account: str, query: str, folder: str = "INBOX"):
    """Search emails by subject keyword"""

@mcp.tool()
def get_email(): #debo de obtener un email por id
    """Still not functional"""

if __name__ == "__main__":
    mcp.run()