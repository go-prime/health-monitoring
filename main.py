import json, os
import time
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from graph_generator import generate_graphic
from hardware_metrics import get_cpu_usage, get_disk_usage, get_load_average, get_ram_usage
from mailer import send_email


# Set up logging
logging.basicConfig(filename='logs/ping.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if not os.path.exists('config/config.json'):
    raise FileNotFoundError("Config file not found")

with open('config/config.json') as config_file:
    config = json.load(config_file)

# Setting parameters  
PING_URL = config.get('PING_URL', 'www.example.com')
PING_INTERVAL = config.get('PING_INTERVAL', 60)
MAILING_LIST = config.get('MAILING_LIST', [])
MAX_RETRY_ATTEMPTS = config.get('MAX_RETRY_ATTEMPTS', 4)
SITE_NAME = config.get('SITE_NAME')
MAX_FOLDER_SIZE = config.get('MAX_FOLDER_SIZE', 1000) # in MB

# Get max thresholds for hardware
RAM_USAGE_MAX_THRESH_HOLD = config.get('RAM_USAGE_MAX_THRESH_HOLD', 80)
CPU_USAGE_MAX_THRESH_HOLD = config.get('CPU_USAGE_MAX_THRESH_HOLD', 80)
HDD_USAGE_MAX_THRESH_HOLD = config.get('HDD_USAGE_MAX_THRESH_HOLD', 80)

# Get maximum number of alarm state triggers
MAXIMUM_NO_OF_TRIGGERS = config.get('MAXIMUM_NO_OF_ALARM_STATE_TRIGGERS', 3)


def prune_graphs(site_name):
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
    while folder_size > MAX_FOLDER_SIZE:
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


def send_warning_email(ping_alarm_triggered, hardware_alarm_triggered, metrics_map):
    issues = []
    subject = ""
    attachments = []

    if not ping_alarm_triggered and not hardware_alarm_triggered:
        logging.info("No need to send warning email")
        return

    logging.info("Sending warning email")
    # generate new graphic
    if not SITE_NAME:
        raise ValueError("SITE_NAME not provided in config")

    logging.info("Generating graphics")
    prune_graphs(SITE_NAME)
    
    if ping_alarm_triggered:
        # Prune graphs before generating new graphic
        generate_graphic(SITE_NAME, metric='ping')
        issues.append(f"{SITE_NAME} has not been reachable after {MAX_RETRY_ATTEMPTS + 1} attempts to connect.\n")
        subject += f"Site {SITE_NAME} is not accessible. "
        
        # Get latest graphic from site folder
        logging.info("Getting latest graphic")
        img_file = get_latest_graphic(SITE_NAME, metric='ping')
        logging.info(f"Graphic file: {img_file}")
        attachments.append(img_file)
        
    if hardware_alarm_triggered:
        generate_graphic(SITE_NAME, metric='hardware')
        for metric, value in metrics_map.items():
            issues.append(f"{metric.upper()} currently has a value of {value} %.\n")
            logging.info(f"Getting latest graphic for {metric}")
            attachments.append(get_latest_graphic(SITE_NAME, metric='hardware', metric_param=metric))
            
        subject += f"{len(metrics_map.items())} Hardware metrics exceeded."
        
    issue_message = ''
    for num, issue in enumerate(issues, start=1):
        issue_message += f"{num}. {issue}\n"
    
    msg = (
        f"Greetings,\n\n"
        f"Kindly note that the site {SITE_NAME}'s Metrics are not optimal. Please check the attached graphics for more details.\n\n"
        f"The following parameters have been breached:\n\n"
        f"{issue_message}\n"
        f"Regards"
    )


    # send email with graphic attachment
    logging.info("Sending email")
    send_email(MAILING_LIST, subject, msg, attachments)


def ping_retry(url):
    retries = 0
    s = requests.Session()
    logging.info(f'Retrying connection to {url}')
    
    logging.info('Setting up retry strategy')
    # Set up retry strategy
    retry_strategy = Retry(
        total=MAX_RETRY_ATTEMPTS,
        backoff_factor=0.1,
        status_forcelist=[500, 502, 503, 504]
    )

    s.mount('https://', HTTPAdapter(max_retries=retry_strategy))
    logging.info('Retry strategy set')
    
    while retries < MAX_RETRY_ATTEMPTS:
        logging.info('Retrying to connect.....')
        logging.info(f'Retry count: {retries + 1}')
        try:
            response = s.get(url)
            if response.status_code == 200:
                return True
            else:
                retries += 1
                time.sleep(5)
        except requests.RequestException:
            retries += 1
            if retries <= MAX_RETRY_ATTEMPTS:
                time.sleep(5)
    # When max number of retries is reached, return False
    # Send warning email
    return False


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


def ping_url(url, output_file):
    results = []
    connected = False

    logging.info(f'Pinging: {url}')
    try:
        response = requests.get(url)
        if response.status_code == 200:
            logging.info(f'Successfully reached {url}')
            connected = True
            results.append({"timestamp": time.time(), "status": "success"})
        else:
            logging.info(f'Failed to reach {url}')
            logging.info('Retrying to connect')
            logging.info(f'Status Code: {response.status_code}')
            # retry ping
            results.append({"timestamp": time.time(), "status": "failure", "status_code": response.status_code})
            connected = ping_retry(url)
    except requests.RequestException as e:
        logging.info(f'Error - {e}')
        results.append({"timestamp": time.time(), "status": "failure", "error": str(e)})
        # retry ping
        connected = ping_retry(url)
        
    logging.info(f'Logging to {output_file}')
    logging.info(f'Logging to {os.path.exists(output_file)}')
    
    export_to_json_file(results, output_file)

    return connected


def record_hardware_metrics(output_file):
    results = []
    threshold_exceeded = False
    exceeded_metric_map =  {}
    
    gb_size = (1024 * 1024 * 1024) 
    # Get Metrics
    cpu_usage = get_cpu_usage()
    ram_usage = get_ram_usage()

    # load avgs
    load_avg =  get_load_average()
    disk_usage = get_disk_usage()
    timestamp = time.time()

    results.append({
        "timestamp": timestamp,
        "cpu_usage": cpu_usage.get('cpu_usage', 0.0),
        "ram_usage_free": ram_usage.free / gb_size,
        "ram_usage_used": ram_usage.used / gb_size,
        "ram_usage_percentage": ram_usage.percent,
        "load_avg_last_5_mins": load_avg.get("Last 5 Mins", 0.0),
        "load_avg_last_10_mins": load_avg.get("Last 10 Mins", 0.0),
        "load_avg_last_15_mins": load_avg.get("Last 15 Mins", 0.0),
        "disk_usage_free": disk_usage.get('free', 0.0),
        "disk_usage_used": disk_usage.get('used', 0.0)
    })

    logging.info(f'Logging to {output_file}')
    export_to_json_file(results, output_file)
        
    if cpu_usage.get('cpu_usage', 0.0) > CPU_USAGE_MAX_THRESH_HOLD:
        threshold_exceeded = True
        exceeded_metric_map['cpu_usage'] = cpu_usage.get('cpu_usage', 0.0)
        logging.info(f'CPU usage exceeded threshold: {cpu_usage.get("cpu_usage", 0.0)}')

    if ram_usage.percent > RAM_USAGE_MAX_THRESH_HOLD:
        threshold_exceeded = True
        exceeded_metric_map['ram_usage'] = ram_usage.percent
        logging.info(f'RAM usage exceeded threshold: {ram_usage.percent}')


    used = disk_usage.get('used', 0.0)
    free = disk_usage.get('free', 0.0)
    total = used + free
    total = total or 1
    used_percentage = (used / total) * 100
    if used_percentage > HDD_USAGE_MAX_THRESH_HOLD:
        threshold_exceeded = True
        exceeded_metric_map['disk_usage'] = round(used_percentage, 3)
        logging.info(f'Disk usage exceeded threshold: {disk_usage.get("used", 0)}')

    return threshold_exceeded, exceeded_metric_map


def process_metrics(url, interval, ping_output_file, hardware_output_file):
    ping_alarm_stage_triggered = False
    hardware_alarm_stage_triggered = False

    while True:
        url_accessed = ping_url(url, ping_output_file)
        threshhold_exceeded, exceeded_metrics = record_hardware_metrics(hardware_output_file)
        hardware_triggers = 0

        # map metrics to their thresholds
        threshhold_map = {
            'cpu_usage': CPU_USAGE_MAX_THRESH_HOLD,
            'disk_usage': HDD_USAGE_MAX_THRESH_HOLD,
            'ram_usage': RAM_USAGE_MAX_THRESH_HOLD
        }


        if not url_accessed or threshhold_exceeded:
            # Get last 10 ping results
            with open(ping_output_file, 'r') as file:
                ping_results = json.load(file)[-10:]

            # Get last 10 hardware metrics results
            with open(hardware_output_file, 'r') as file:
                hardware_results = json.load(file)[-10:]

            logging.info(f'Ping Results: Last 3 {ping_results[:3]}')
            logging.info(f'Hardware Results: Last 3 {hardware_results[:3]}')
            logging.info(f'Maximum number of triggers permitted: {MAXIMUM_NO_OF_TRIGGERS}')


            logging.info(f'Assessing Ping Triggers:')
            logging.info(f'{str(["x" for r in ping_results if r.get("status") == "failure"])}')

            fail_list = [result for result in ping_results if result.get('status') == 'failure']

            # logging.info(f'Ping failures: {fail_list}')

            no_of_ping_failures = len(fail_list)

            logging.info(f'Number of ping failures: {no_of_ping_failures}')
            if no_of_ping_failures >= MAXIMUM_NO_OF_TRIGGERS:
                ping_alarm_stage_triggered = True

            logging.info(f'Ping Alarm Stage Triggered: {ping_alarm_stage_triggered}')

            logging.info(f'Assessing Hardware Triggers:')
            for metric, value in exceeded_metrics.items():
                logging.info(f'Checking {metric}')
                logging.info(f'Value: {value}')
                for result in hardware_results:
                    if metric == "cpu_usage":
                        logging.info(f'CPU USAGE: {result.get("cpu_usage", 0.00)}')
                        logging.info(f'Max Threshold: {threshhold_map[metric]}')
                        if result.get("cpu_usage", 0) > threshhold_map[metric]:
                            logging.info('cpu_usage exceeded')
                            hardware_triggers += 1

                    if metric == "ram_usage":
                        logging.info(f'RAM USAGE: {result.get("ram_usage_percentage", 0.00)}')
                        logging.info(f'Max Threshold: {threshhold_map[metric]}')
                        if result.get("ram_usage_percentage") > threshhold_map[metric]:
                            logging.info('ram usage exceeded')
                            hardware_triggers += 1

                    if metric == "disk_usage":
                        total_usage = result.get('disk_usage_free', 0.0) + result.get('disk_usage_used', 0.0)
                        used_percentage = (result.get('disk_usage_used') / total_usage or 1) * 100
                        logging.info(f'DISK USAGE: {result.get("disk_usage_used", 0.00)}')
                        logging.info(f'Max Threshold: {threshhold_map[metric]}')
                        logging.info(f'Total Usage: {total_usage}')
                        logging.info(f'FREE: {result.get("disk_usage_free", 0.0)}')
                        logging.info(f'USED %: {used_percentage}')
                        if result.get("disk_usage_used", 0) > threshhold_map[metric]:
                            logging.info('disk usage exceeded')
                            hardware_triggers += 1


            logging.info('Finished assessing hardware triggers')
            hardware_alarm_stage_triggered = hardware_triggers >= (MAXIMUM_NO_OF_TRIGGERS/len(exceeded_metrics.items()))
            logging.info(f'Ping Alarm Stage Triggered: {ping_alarm_stage_triggered}')
            logging.info(f'Hardware Alarm Stage Triggered: {hardware_alarm_stage_triggered}')
            logging.info(f'Number of hardware triggers: {hardware_triggers}')
            logging.info(f'Exceeded Metrics: {len(exceeded_metrics.items())}')

            send_warning_email(ping_alarm_stage_triggered, hardware_alarm_stage_triggered, exceeded_metrics)

        time.sleep(interval)


if __name__ == "__main__":
    url_to_ping = PING_URL
    ping_interval = PING_INTERVAL

    # create sites results folder if it doesn't exist
    ping_results_folder = os.path.join('results', SITE_NAME, 'ping_metrics')
    if not os.path.exists(ping_results_folder):
        os.makedirs(ping_results_folder)    
        # Create file
        with open(os.path.join(ping_results_folder, 'ping_results.json'), 'w') as file:
            json.dump([], file)

    hardware_metrics_folder = os.path.join('results', SITE_NAME, 'hardware_metrics')
    if not os.path.exists(hardware_metrics_folder):
        os.makedirs(hardware_metrics_folder)
        # Create file
        with open(os.path.join(hardware_metrics_folder, 'hardware_metrics.json'), 'w') as file:
            json.dump([], file)

    ping_output_file = ping_results_folder + '/ping_results.json'
    hardware_output_file = hardware_metrics_folder + '/hardware_metrics.json'

    logging.info('Starting Up')
    process_metrics(url_to_ping, ping_interval, ping_output_file, hardware_output_file)
