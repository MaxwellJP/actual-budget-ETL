import os
import zipfile
import smtplib
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email import encoders
from datetime import datetime

config_path = "/home/actual-project/scripts/Config.txt"
archive_path = "/home/actual-project/data/archives"
compressed_storage_path = "/home/actual-project/data/compressed-storage"
log_file_path = "/home/actual-project/data/actual-budget-updates.log"
zip_file = os.path.join(compressed_storage_path, f"actual-budget-{datetime.now().strftime('%Y%m%d')}.zip")

def read_config(file_path):

    config = {}

    with open(file_path, "r") as file:
        for line in file:
            key, value = line.strip().split("=", 1)
            config[key] = value

    return config

config = read_config(config_path)
env = os.environ.copy()

env["EMAIL_ADDRESS"] = config.get("email_address")
env["EMAIL_PASSWORD"] = config.get("email_password")
env["RECIPIENT_EMAIL"] = config.get("recipient_email")
env["SMTP_SERVER"] = config.get("smtp_server")
env["SMTP_PORT"] = config.get("smtp_port")

def compress_archives():

    os.makedirs(compressed_storage_path, exist_ok=True)

    with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(archive_path):
            for file in files:
                file_path = os.path.join(root, file)
                archive_name = os.path.relpath(file_path, archive_path)
                zipf.write(file_path, archive_name)

        if os.path.exists(log_file_path):
            zipf.write(log_file_path, os.path.basename(log_file_path))
            print(f"Added log file {log_file_path} to zip.")

    print(f"Compressed archives and log files were moved to {zip_file}")

    for root, dirs, files in os.walk(archive_path, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))

        for dir in dirs:
            os.rmdir(os.path.join(root, dir))

    if os.path.exists(log_file_path):
        os.remove(log_file_path)
        print(f"Removed log file: {log_file_path}.")

    print(f"Cleared archives folder: {archive_path}")

def send_email_with_attachment():

    time_stamp = datetime.now().strftime('%Y-%m-%d')
    email_address = env.get('EMAIL_ADDRESS')
    email_password = env.get('EMAIL_PASSWORD')
    recipient_email = env.get('RECIPIENT_EMAIL')
    smtp_server = env.get('SMTP_SERVER')
    smtp_port = int(env.get('SMTP_PORT'))

    try:
        msg = MIMEMultipart()
        msg['From'] = email_address
        msg['To'] = recipient_email
        msg['Subject'] = f"Budget Archive Backup - {time_stamp}"
        body = "Attached is the budget archive backup."
        msg.attach(MIMEText(body, 'plain'))

        with open(zip_file, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())

        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename={os.path.basename(zip_file)}',
        )
        msg.attach(part)

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.sendmail(email_address, recipient_email, msg.as_string())

        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    compress_archives()
    send_email_with_attachment()

if __name__ == "__main__":
    main()
