import secrets
import smtplib
from email.mime.text import MIMEText
from configs import SENDER_EMAIL, SENDER_PASSWORD

def generate_verification_code():
    return secrets.token_hex(4)  # 8-значный код

def send_email(email: str, code: str):
    sender = SENDER_EMAIL
    password = SENDER_PASSWORD
    
    message = MIMEText(f"Ваш код подтверждения: {code}")
    message['Subject'] = "Подтверждение регистрации"
    message['From'] = sender
    message['To'] = email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(message)