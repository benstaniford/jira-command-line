#!/usr/bin/python3

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class MyEmail:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 465
        self.smtp_username = os.environ.get('SMTP_USERNAME')
        self.smtp_password = os.environ.get('SMTP_PASSWORD')
        if self.smtp_username is None or self.smtp_password is None:
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD environment variables must be set.")

    def send(self, to_email, subject, body):
        msg = MIMEMultipart()
        msg['From'] = self.smtp_username
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(self.smtp_username, to_email, msg.as_string())
            server.quit()

