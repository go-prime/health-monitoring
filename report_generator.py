import logging
from graph_generator import generate_graphs_for_daily_report
from mailer import send_email
from utils import get_abs_path, get_latest_json_file, get_config
import os
import json


log_file = 'logs/daily_report.log'
log_file = get_abs_path(log_file)
config_file = 'config/config.json'
config_file = get_abs_path(config_file)

logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


with open(config_file) as config_file:
    conf = json.load(config_file)


def generate_report(site_name):
    ping_skipped = conf.get('EXCLUDE_PING_FROM_REPORTING')
    hardware_skipped = conf.get('EXCLUDE_HARDWARE_CHECK_FROM_REPORTING')
    stats_breakdown = ""

    if ping_skipped and hardware_skipped:
        logging.info("Skipping Daily Report Generation")
        return

    ping_source_file = get_latest_json_file(site_name, 'ping') if not ping_skipped else None
    hardware_source_file = get_latest_json_file(site_name, 'hardware') if not hardware_skipped else None

    if ping_source_file:
        ping_source_file = get_abs_path(ping_source_file)

    if hardware_source_file:
        hardware_source_file = get_abs_path(hardware_source_file)

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
    load_last_10_mins_avg = hardware_avg.get('load_last_10_mins_avg') if hardware_avg else 0.0
    
    if not ping_skipped:
        stats_breakdown += f"Average Ping Success: {avg_ping} %.\n"
        
    if not hardware_skipped:
        stats_breakdown += (
            f"Average Disk Usage: {disk_use_avg} %.\n"
            f"Average RAM Usage: {ram_use_avg} %.\n"
            f"Average CPU Usage: {cpu_use_avg} %.\n"
            f"Load Avg (10 Min): {load_last_10_mins_avg}."
        )

    subject = f"Daily Report for {site_name}"
    
    body = (
        f"Please find the attached graphics for the daily report for {site_name}.\n\n"
        f"Below is the breakdown of the site's performance:\n"
        f"{stats_breakdown}\n"
    )

    attachments = [ping_attachment, hardware_attachment]

    logging.info("Sending Email")
    logging.info(f"Subject: {subject}")
    logging.info(f"Body: {body}")

    send_email(conf.get('MAILING_LIST'), subject=subject, body=body, attachments=attachments)

generate_report(conf.get('SITE_NAME'))