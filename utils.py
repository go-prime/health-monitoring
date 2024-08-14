import json
import os
import logging
import datetime

from graph_generator import generate_graphic
from mailer import send_email


logging.basicConfig(filename='logs/ping.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_config():
    if not os.path.exists('config/config.json'):
        raise FileNotFoundError("Config file not found")

    with open('config/config.json') as config_file:
        config = json.load(config_file)
    
    return config


def prune_graphs(site_name):
    config = get_config()
    max_folder_size = config.get('MAX_FOLDER_SIZE', 1000)
    logging.info(f"Pruning graphs for site: {site_name}")
    # get site folder
    site_folder = os.path.join('exports/images', site_name, 'ping_metrics')

    # if folder does not exist return
    if not os.path.exists(site_folder):
        logging.warning(f"Site folder does not exist: {site_folder}")
        return

    def get_folder_size(folder):
        return sum(os.path.getsize(os.path.join(folder, f)) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))) / (1024 * 1024)

    folder_size = get_folder_size(site_folder)
    logging.info(f"Initial folder size: {folder_size:.2f} MB")

    pruned_files_count = 0
    while folder_size > max_folder_size:
        logging.info("Folder size exceeds maximum limit")
        # sort files by modification time
        files = sorted((f for f in os.listdir(site_folder) if os.path.isfile(os.path.join(site_folder, f))),
                       key=lambda x: os.path.getmtime(os.path.join(site_folder, x)))

        if not files:
            break

        # delete the oldest file
        oldest_file = files[0]
        os.remove(os.path.join(site_folder, oldest_file))
        logging.info(f"Deleted file: {oldest_file}")
        pruned_files_count += 1
        folder_size = get_folder_size(site_folder)

    if pruned_files_count > 0:
        logging.info(f"Pruned {pruned_files_count} files")
    else:
        logging.info("No files were pruned, folder size is within the limit")

    # clear all metrics files
    metrics_folder = os.path.join('exports/images', site_name, 'hardware_metrics')
    for metric in ['cpu_usage', 'disk_usage', 'ram_usage', 'system_metrics']:
        sub_folder = os.path.join(metrics_folder, metric)
        if os.path.exists(sub_folder):
            for file in os.listdir(sub_folder):
                os.remove(os.path.join(sub_folder, file))


def get_latest_graphic(site_name, metric, metric_param=None):
    if metric == 'ping':
        site_folder = os.path.join('exports/images', site_name, 'ping_metrics')
        if not os.path.exists(site_folder):
            os.makedirs(site_folder)
        graphic_files = [f for f in os.listdir(site_folder) if f.endswith('.png')]

        if not graphic_files:
            return None
        graphic_files.sort(reverse=True)

        return os.path.join(site_folder, graphic_files[0])

    elif metric == 'hardware':
        logging.info(f"Getting latest graphic for {metric_param}")
        site_folder = os.path.join('exports/images', site_name, 'hardware_metrics', metric_param)
        logging.info(f"Site folder: {site_folder}")
        if not os.path.exists(site_folder):
            logging.warning(f"Site folder does not exist: {site_folder}")
            os.makedirs(site_folder)
        graphic_files = [f for f in os.listdir(site_folder) if f.endswith('.png')]

        if not graphic_files:
            return None
        graphic_files.sort(reverse=True)

        return os.path.join(site_folder, graphic_files[0])


def export_to_json_file(results, output_file):
    # Check if the file exists and load existing data
    if os.path.exists(output_file):
        with open(output_file, 'r') as file:
            try:
                existing_data = json.load(file)
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []

    # Append new results to the existing data
    existing_data.extend(results)

    with  open(output_file, 'w') as file:
        json.dump(existing_data, file, indent=4)


def send_warning_email(site_name, 
                       cc,
                       ping_alarm_triggered=None,
                       ping_retries=None,
                       hardware_alarm_triggered=None,
                       metrics_map=None):
    issues = []
    subject = ""
    attachments = []

    if not ping_alarm_triggered and not hardware_alarm_triggered:
        logging.info("No need to send warning email")
        return

    logging.info("Sending warning email")
    # generate new graphic
    if not site_name:
        raise ValueError("site_name not provided in config")

    logging.info("Generating graphics")
    prune_graphs(site_name)

    if ping_alarm_triggered:
        # Prune graphs before generating new graphic
        generate_graphic(site_name, metric='ping')
        issues.append(f"{site_name} has not been reachable after {ping_retries + 1} attempts to connect.\n")
        subject += f"Site {site_name} is not accessible. "

        # Get latest graphic from site folder
        logging.info("Getting latest graphic")
        img_file = get_latest_graphic(site_name, metric='ping')
        logging.info(f"Graphic file: {img_file}")
        attachments.append(img_file)

    if hardware_alarm_triggered:
        generate_graphic(site_name, metric='hardware')
        for metric, value in metrics_map.items():
            issues.append(f"{metric.upper()} currently has a value of {value} %.\n")
            logging.info(f"Getting latest graphic for {metric}")
            attachments.append(get_latest_graphic(site_name, metric='hardware', metric_param=metric))

        subject += f"{len(metrics_map.items())} Hardware metrics exceeded."

    issue_message = ''
    for num, issue in enumerate(issues, start=1):
        issue_message += f"{num}. {issue}\n"

    msg = (
        f"Greetings,\n\n"
        f"Kindly note that the site {site_name}'s Metrics are not optimal. Please check the attached graphics for more details.\n\n"
        f"The following parameters have been breached:\n\n"
        f"{issue_message}\n"
        f"Regards"
    )

    # send email with graphic attachment
    logging.info("Sending email")
    send_email(cc, subject, msg, attachments)


def get_base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def get_latest_json_file(site_name, metric):
    date_string = datetime.date.today().strftime("%Y_%m_%d")
    base_dir = os.path.join(get_base_dir(), 'results')
    site_folder = os.path.join(base_dir, site_name, f'{metric}_metrics')
    if not os.path.exists(site_folder):
        os.makedirs(site_folder)
        return None

    json_file = os.path.join(site_folder, f'{metric}_metrics_{date_string}.json')
    if not os.path.exists(json_file):
        return None

    return json_file


def get_abs_path(path):
    return os.path.join(os.path.dirname(__file__), path)
