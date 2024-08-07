import logging
from graph_generator import generate_graphs_for_daily_report
from mailer import send_email
from utils import get_latest_json_file, get_config


logging.basicConfig(filename='logs/ping.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


conf = get_config()


def generate_report(site_name):
    ping_source_file = get_latest_json_file(site_name, 'ping')
    hardware_source_file = get_latest_json_file(site_name, 'hardware')

    logging.info(f"Generating Daily Report for {site_name}")
    logging.info(f"Ping Source File: {ping_source_file}")
    logging.info(f"Hardware Source File: {hardware_source_file}")

    logging.info("Generating Graphs for Daily Report")
    hardware_attachment, ping_attachment, stats = generate_graphs_for_daily_report(
        site_name=site_name,
        hardware_source_file=hardware_source_file,
        ping_source_file=ping_source_file
    )
    logging.info("Graphs Generated Successfully")

    logging.info("Preparing Email Body")
    ping_avg = stats.get('ping')
    avg_ping = ping_avg.get('status_avg_success') if ping_avg else 0.0
    hardware_avg = stats.get('hardware')
    disk_use_avg = hardware_avg.get('disk_usage_avg') if hardware_avg else 0.0
    ram_use_avg = hardware_avg.get('ram_usage_avg') if hardware_avg else 0.0
    cpu_use_avg = hardware_avg.get('cpu_usage_avg') if hardware_avg else 0.0
    
    stats_breakdown = f"""
    Average Ping Success to {site_name}: {avg_ping} %
    Average Disk Usage: {disk_use_avg} %
    Average RAM Usage: {ram_use_avg} %
    Average CPU Usage: {cpu_use_avg} %
    """

    subject = f"Daily Report for {site_name}"
    body = f"""
    Please find the attached graphics for the daily report for {site_name}.\n\n
    
    Below is the breakdown of the site's performance:\n
    {stats_breakdown}\n\n
    """
    attachments = [ping_attachment, hardware_attachment]

    logging.info("Sending Email")
    logging.info(f"Subject: {subject}")
    logging.info(f"Body: {body}")

    send_email(conf.get('MAILING_LIST'), subject=subject, body=body, attachments=attachments)

generate_report(conf.get('SITE_NAME'))