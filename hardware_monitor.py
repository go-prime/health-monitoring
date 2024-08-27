import json
import logging
import os
import time
import datetime

from hardware_metrics import get_cpu_usage, get_disk_usage, get_load_average, get_ram_usage
from utils import current_time_within_business_hours, export_to_json_file, get_config, send_warning_email, update_alert_file


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




def record_hardware_metrics(output_file):
    results = []
    threshold_exceeded = False
    exceeded_metric_map = {}

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


def process_metrics(interval, hardware_metrics_folder, alert_status_folder):    
    curr_time = time.strftime("%H:%M")
    curr_date = datetime.datetime.now().date().strftime("%a")

    while True:
        if current_time_within_business_hours():
            logging.info(f'Current TIME:{curr_time} DAY:{curr_date} is within business hours. Checking hardware metrics.')
            
            date_string = datetime.date.today().strftime("%Y_%m_%d")
            output_file = os.path.join(hardware_metrics_folder,
                                f'hardware_metrics_{date_string}.json')
            threshhold_exceeded, exceeded_metrics = record_hardware_metrics(output_file)
            
            alert_file = os.path.join(alert_status_folder, f'alert_status_{date_string}.json')

            with open(alert_file, 'r') as file:
                previous_alert_data = json.load(file)

            previous_alert_state_triggered = previous_alert_data.get('alarm_triggered', False)
            
            if threshhold_exceeded:
                logging.info('Hardware alarm triggered.')
                send_warning_email(
                    site_name=SITE_NAME,
                    cc=config.get('MAILING_LIST', []),
                    hardware_alarm_triggered=True, 
                    metrics_map=exceeded_metrics
                )

                if not previous_alert_state_triggered:
                    logging.info(f"Setting alert from {previous_alert_state_triggered} to {threshhold_exceeded}")
                    update_alert_file(alert_file, True)
                else:
                    logging.info('Hardware alarm still triggered.')

            elif not threshhold_exceeded and previous_alert_state_triggered:
                logging.info('Hardware alarm no longer triggered.')
                logging.info(f"Setting alert from {previous_alert_state_triggered} to {threshhold_exceeded}")
                update_alert_file(alert_file, False)
            else:
                logging.info('No hardware issues detected.')
                    
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
        "alarm_triggered": False,
        "trigger_count": 0,
        "last_time_triggred": None
    }

    if not os.path.exists(site_alert_folder):
        os.makedirs(site_alert_folder)
        # Create file
        alert_file = os.path.join(site_alert_folder, f'alert_status_{date_string}.json')
        with open(alert_file, 'w') as file:
            json.dump(trigger_defaults, file)


    logging.info('Starting Up Hardware Monitoring.')
    process_metrics(hardware_check_interval, hardware_metrics_folder, site_alert_folder)
