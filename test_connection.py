import imaplib

try: 
    mail = imaplib.IMAP4_SSL("outlook.office365.com")
    mail.login("a01658415@tec.mx")
    print("Conexion exitosa")
    mail.logout()
except Exception as e:
    print(f"Error: {e}")

