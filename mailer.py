import logging
import smtplib, json, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage


# Set up logging
logging.basicConfig(filename='logs/mailer.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if not os.path.exists('config/config.json'):
    raise FileNotFoundError("Config file not found")

with open('config/config.json') as config_file:
    config = json.load(config_file)
    
# LOAD MAILING CONFIG
MAILING_LIST = config.get('MAILING_LIST', [])
MAILER_EMAIL = config.get('MAILER_EMAIL')
MAILER_PASSWORD = config.get('MAILER_PASSWORD')
SMTP_PORT = config.get('SMTP_PORT', 587)
SMTP_SERVER = config.get('SMTP_SERVER', 'smtp.office365.com')


if not MAILER_EMAIL or not MAILER_PASSWORD:
    logging.error("Mailer email or password not provided in config file")
    raise ValueError("Mailer email or password not provided in config file")


def send_email(recipients, subject, body, attachments=None):
    logging.info(f"Sending email to {', '.join(recipients)}")
    logging.info(f"Subject: {subject}")
    logging.info(f"Body: {body}")
    logging.info(f"Images Attached No: {len(attachments)}")
    msg = MIMEMultipart()
    msg['From'] = MAILER_EMAIL
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    for image_path in attachments:
        if not image_path:
            logging.warning("Invalid image path provided")
            continue
        if os.path.exists(image_path):
            logging.info("Adding image to email")
            with open(image_path, 'rb') as f:
                image_data = f.read()
                image = MIMEImage(image_data, name=os.path.basename(image_path))
                msg.attach(image)
        else:
            logging.warning(f"Image file not found: {image_path}")

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
        logging.info("Logging in to SMTP server")
        smtp.login(MAILER_EMAIL, MAILER_PASSWORD)
        smtp.send_message(msg)
        logging.info("Email sent successfully")
