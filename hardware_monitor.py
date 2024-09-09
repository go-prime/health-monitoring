import json
import logging
import os
import time
import datetime

from hardware_metrics import get_cpu_usage, get_disk_usage, get_load_average, get_ram_usage
from utils import check_load_if_avg_exceeded, current_time_within_business_hours, export_to_json_file, get_config, send_warning_email_for_metric, update_alert_file


logging.basicConfig(filename='logs/ping.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

config = get_config()


# Get max thresholds for hardware
RAM_USAGE_MAX_THRESH_HOLD = config.get('RAM_USAGE_MAX_THRESH_HOLD', 80)
CPU_USAGE_MAX_THRESH_HOLD = config.get('CPU_USAGE_MAX_THRESH_HOLD', 80)
HDD_USAGE_MAX_THRESH_HOLD = config.get('HDD_USAGE_MAX_THRESH_HOLD', 80)

# Get hardware check interval in seconds
HARDWARE_CHECK_INTERVAL = config.get('HARDWARE_CHECK_INTERVAL', 60)

# Site name
SITE_NAME = config.get('SITE_NAME', '')

# MAILING_LIST
MAILING_LIST = config.get('MAILING_LIST', [])


def record_hardware_metrics(output_file):
    results = []
    metric_map = {
        "timestamp": None,
        "load_avg_last_10_mins ": 0.0,
        "load_avg_last_10_mins_exceeded": False,
        "load_avg_last_10_mins_trigger_count": 0,
        "ram_usage": 0.0,
        "ram_usage_exceeded": False,
        "ram_usage_last_trigger_time": None,
        "ram_usage_trigger_count": 0,
        "disk_usage": 0.0,
        "disk_usage_exceeded": False,
        "disk_usage_trigger_count": 0,
        "disk_usage_last_trigger_time": None,
    }

    gb_size = (1024 * 1024 * 1024)
    # Get Metrics
    cpu_usage = get_cpu_usage()
    ram_usage = get_ram_usage()

    # load avgs
    load_avg = get_load_average()
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

    # Recording time stamp
    logging.info(f"Recording Hardware record timestamp: {timestamp}")
    metric_map['timestamp'] = timestamp

    # load Average
    load_avg_exceeded , number_of_cores = check_load_if_avg_exceeded(load_avg.get("Last 10 Mins", 0.0))
    metric_map['load_avg_last_10_mins'] = round(load_avg.get("Last 10 Mins", 0.0) / number_of_cores * 100, 2)
    metric_map['load_avg_last_10_mins_exceeded'] = load_avg_exceeded
    logging.info(f'Load usage exceeded threshold: {load_avg_exceeded} at {load_avg.get("Last 10 Mins", 0.0)} .')

    # Ram Usage
    ram_usage_exceeded = ram_usage.percent > RAM_USAGE_MAX_THRESH_HOLD
    metric_map['ram_usage'] = ram_usage.percent
    metric_map['ram_usage_exceeded'] = ram_usage_exceeded
    logging.info(f'RAM usage exceeded threshold: {ram_usage_exceeded} at {ram_usage.percent} %.')

    # Disk Usage
    used = disk_usage.get('used', 0.0)
    free = disk_usage.get('free', 0.0)
    total = used + free
    total = total or 1
    used_percentage = (used / total) * 100

    disk_usage_exceeded = used_percentage > HDD_USAGE_MAX_THRESH_HOLD
    metric_map['disk_usage'] = round(used_percentage, 3)
    metric_map['disk_usage_exceeded'] = disk_usage_exceeded
    logging.info(f'Disk usage exceeded threshold: {disk_usage_exceeded} at {used_percentage} %.')

    return metric_map


def evaulate_metric(previous_state, current_state, metric, output_file):
    logging.info(f'Now Assessing: {metric}')
    
    previous_state_exceeded = previous_state.get(f'{metric}_exceeded', False)
    # previous_state_metric = previous_state.get(metric, 0.0)
    current_state_exceeded = current_state.get(f'{metric}_exceeded', False)
    # current_state_metric = current_state.get(metric, 0.0)
    
    logging.info(f'Previous state: {previous_state_exceeded} Current state: {current_state_exceeded}')
    
    if not previous_state_exceeded and current_state_exceeded:
        logging.info(f'Hardware alarm triggered for {metric}')
        send_warning_email_for_metric(
            site_name=SITE_NAME,
            cc=MAILING_LIST,
            metric=metric,
            metric_measure=current_state.get(metric, 0.0),
            previous_alert_data=previous_state,
            source_file=output_file,
            scoped_time_stamp=current_state.get("timestamp")
        )
    elif previous_state_exceeded and not current_state_exceeded:
        logging.info(f'Hardware alarm no longer triggered for {metric}')
    else:
        if current_state_exceeded:
            logging.info(f'Hardware alarm still triggered for {metric}')
        else:
            logging.info(f'No hardware issues detected for {metric}')


def evaluate_hardware_metrics(metric_map, previous_alert_state, output_file):
    for metric in ["ram_usage", "disk_usage", "load_avg_last_10_mins"]:
        evaulate_metric(previous_alert_state, metric_map, metric, output_file)


def process_metrics(interval, hardware_metrics_folder, alert_status_folder):    
    curr_time = time.strftime("%H:%M")
    curr_date = datetime.datetime.now().date().strftime("%a")

    while True:
        if current_time_within_business_hours():
            logging.info(f'Current TIME:{curr_time} DAY:{curr_date} is within business hours. Checking hardware metrics.')
            
            date_string = datetime.date.today().strftime("%Y_%m_%d")
            output_file = os.path.join(hardware_metrics_folder,
                                f'hardware_metrics_{date_string}.json')
            monitored_metrics = record_hardware_metrics(output_file)

            alert_file = os.path.join(alert_status_folder, f'alert_status_{date_string}.json')

            with open(alert_file, 'r') as file:
                previous_alert_data = json.load(file)

            evaluate_hardware_metrics(monitored_metrics, previous_alert_data, output_file)
            logging.info('Hardware evaluation completed.')
            logging.info('Now Updating alert file')
            update_alert_file(alertFile=alert_file, hardware_metrics=monitored_metrics)
            logging.info('Alert file updated')
            logging.info('Hardware check complete.')            
        else:
            logging.info(f'Current TIME:{curr_time} DAY:{curr_date} is outside business hours. Skipping hardware monitoring.')

        time.sleep(interval)


if __name__ == "__main__":
    hardware_check_interval = HARDWARE_CHECK_INTERVAL
    site_alert_folder = os.path.join('alert_status', SITE_NAME, "hardware_alert_status")
    hardware_metrics_folder = os.path.join('results', SITE_NAME, 'hardware_metrics')
    date_string = datetime.date.today().strftime("%Y_%m_%d")

    if not os.path.exists(hardware_metrics_folder):
        os.makedirs(hardware_metrics_folder)
        # Create file
        path = os.path.join(hardware_metrics_folder, f'hardware_metrics_{date_string}.json')
        with open(path, 'w') as file:
            json.dump([], file)

    trigger_defaults = {
        "load_avg_last_10_mins": 0.0,
        "load_avg_last_10_mins_exceeded": False,
        "load_avg_last_10_mins_trigger_count": 0,
        "load_avg_last_10_mins_last_trigger_time": 0,
        "ram_usage": 0.0,
        "ram_usage_trigger_count": 0,
        "ram_usage_exceeded": False,
        "ram_usage_last_trigger_time": None,
        "disk_usage": 0.0,
        "disk_usage_exceeded": False,
        "disk_usage_trigger_count": 0,
        "disk_usage_last_trigger_time": None,
    }

    if not os.path.exists(site_alert_folder):
        os.makedirs(site_alert_folder)
        # Create file

    alert_file = os.path.join(site_alert_folder, f'alert_status_{date_string}.json')

    if not os.path.exists(alert_file):
        with open(alert_file, 'w') as file:
            json.dump(trigger_defaults, file, indent=4)


    logging.info('Starting Up Hardware Monitoring.')
    process_metrics(hardware_check_interval, hardware_metrics_folder, site_alert_folder)
