import datetime
import json
import logging
import os
import time

from hardware_metrics import get_cpu_usage, get_disk_usage, get_load_average, get_ram_usage
from utils import current_time_within_business_hours, export_to_json_file, get_config, send_warning_email


logging.basicConfig(filename='logs/ping.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

config = get_config()


# Get max thresholds for hardware
RAM_USAGE_MAX_THRESH_HOLD = config.get('RAM_USAGE_MAX_THRESH_HOLD', 80)
CPU_USAGE_MAX_THRESH_HOLD = config.get('CPU_USAGE_MAX_THRESH_HOLD', 80)
HDD_USAGE_MAX_THRESH_HOLD = config.get('HDD_USAGE_MAX_THRESH_HOLD', 80)

# Get maximum number of alarm state triggers
MAXIMUM_NO_OF_TRIGGERS = config.get('MAXIMUM_NO_OF_ALARM_STATE_TRIGGERS', 3)

# Get hardware check interval in seconds
HARDWARE_CHECK_INTERVAL = config.get('HARDWARE_CHECK_INTERVAL', 60)

# Site name
SITE_NAME = config.get('SITE_NAME', '')


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


def process_metrics(interval, output_file):
    curr_time = time.strftime("%H:%M")
    curr_date = datetime.datetime.now().date().strftime("%a")
    if not current_time_within_business_hours():
        logging.info(f'Current TIME:{curr_time} DAY:{curr_date} is outside business hours. Skipping ping monitoring.')
        return
    
    logging.info(f'Current TIME:{curr_time} DAY:{curr_date} within business hours')


    hardware_alarm_stage_triggered = False
    threshhold_map = {
        'cpu_usage': CPU_USAGE_MAX_THRESH_HOLD,
        'disk_usage': HDD_USAGE_MAX_THRESH_HOLD,
        'ram_usage': RAM_USAGE_MAX_THRESH_HOLD
    }
    
    while True:
        threshhold_exceeded, exceeded_metrics = record_hardware_metrics(output_file)
        hardware_triggers = 0
        hardware_results = []
        
        if threshhold_exceeded:
            # Get last 10 hardware metrics results
            with open(output_file, 'r') as file:
                hardware_results = json.load(file)[-10:]
                
        logging.info(f'Hardware Results: Last 3 {hardware_results[:3]}')
        logging.info(f'Maximum number of triggers permitted: {MAXIMUM_NO_OF_TRIGGERS}')
        
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

        exceeded_pop = len(exceeded_metrics.items())
        if exceeded_pop:
            hardware_alarm_stage_triggered = hardware_triggers >= (MAXIMUM_NO_OF_TRIGGERS/exceeded_pop)
        else:
            hardware_alarm_stage_triggered = False
        
        logging.info(f'Hardware Alarm Stage Triggered: {hardware_alarm_stage_triggered}')
        logging.info(f'Number of hardware triggers: {hardware_triggers}')
        logging.info(f'Exceeded Metrics: {len(exceeded_metrics.items())}')
        
        if threshhold_exceeded:
            send_warning_email(
                site_name=SITE_NAME,
                cc=config.get('MAILING_LIST', []),
                hardware_alarm_triggered=hardware_alarm_stage_triggered, 
                metrics_map=exceeded_metrics
            )
        
        time.sleep(interval)
    


if __name__ == "__main__":
    hardware_check_interval = HARDWARE_CHECK_INTERVAL
    hardware_metrics_folder = os.path.join('results', SITE_NAME, 'hardware_metrics')
    if not os.path.exists(hardware_metrics_folder):
        os.makedirs(hardware_metrics_folder)
        # Create file
        with open(os.path.join(hardware_metrics_folder, 'hardware_metrics.json'), 'w') as file:
            json.dump([], file)
            
    output_file = os.path.join(hardware_metrics_folder, 'hardware_metrics.json')
    logging.info('Starting Up Hardware Monitoring.')
    process_metrics(hardware_check_interval, output_file)
