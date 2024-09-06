import json
import os
import logging
import datetime
import time

from graph_generator import generate_graphic, generate_graphs_for_daily_report, generate_hardware_graphic, get_datetime_string_from_timestamp
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
                       metrics_map=None,
                       last_trigger_time=None
                       ):
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
        
    last_trigger_time = get_datetime_string_from_timestamp(last_trigger_time) if last_trigger_time else "N/A"

    msg = (
        f"Greetings,\n\n"
        f"Kindly note that the site {site_name}'s Metrics are not optimal. Please check the attached graphics for more details.\n\n"
        f"The following parameters have been breached:\n\n"
        f"{issue_message}\n"
        f"Last trigger time: {last_trigger_time}\n\n"
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

def current_time_within_business_hours(check_working_days_only=False):
    conf = get_config()
    business_starting_hour = conf.get('BUSINESS_DAY_START', '08:00')
    business_finishing_hour = conf.get('BUSINESS_DAY_END', '17:00')
    business_weekstart_day = conf.get('BUSINESS_WEEK_START', "MONDAY")
    business_weekend_day = conf.get('BUSINESS_WEEK_END', "FRIDAY")

    # Return false if day outside business week
    days_of_week = {
        "MONDAY": 0,
        "TUESDAY": 1,
        "WEDNESDAY": 2,
        "THURSDAY": 3,
        "FRIDAY": 4,
        "SATURDAY": 5,
        "SUNDAY": 6
    }

    current_day = datetime.datetime.today().weekday()
    current_time = datetime.datetime.today().time()

    week_start = days_of_week[business_weekstart_day.upper()]
    week_end = days_of_week[business_weekend_day.upper()]

    # Check if the current day is within the business week
    if not (week_start <= current_day <= week_end):
        return False

    if check_working_days_only:
        return True

    business_starting_hour = datetime.datetime.strptime(business_starting_hour, "%H:%M").time()
    business_finishing_hour = datetime.datetime.strptime(business_finishing_hour, "%H:%M").time()

    return business_starting_hour <= current_time <= business_finishing_hour


def update_alert_file(alertFile, alert_triggered=None, hardware_metrics=None):
    logging.info(f"Updating alert file: {alertFile}")
    if not os.path.exists(os.path.dirname(alertFile)):
        os.makedirs(os.path.dirname(alertFile))

    with open(alertFile, 'r+') as file:
        data = json.load(file)
        time_stamp = time.time()
        
        if hardware_metrics:
            logging.info("Updating hardware metrics on alert file.")
            # Update trigger counts and states in a loop to reduce redundancy
            for metric in ['cpu_usage', 'ram_usage', 'disk_usage']:
                # Logging trigger counts
                data[f"{metric}_trigger_count"] += 1 if hardware_metrics.get(f'{metric}_exceeded') else 0
                # Logging time
                if hardware_metrics.get(f'{metric}_exceeded'):
                    data[f"{metric}_last_trigger_time"] = time_stamp
                # Setting New States
                data[f"{metric}_exceeded"] = hardware_metrics.get(f'{metric}_exceeded')
                # Setting Metrics
                data[f"{metric}"] = hardware_metrics.get(metric)
        else:
            logging.info("Updating ping metrics on alert file.")
            data['alarm_triggered'] = alert_triggered
            if alert_triggered:
                data["last_time_triggered"] = time_stamp
            data["trigger_count"] += 1 if alert_triggered else 0
            

        file.seek(0)
        json.dump(data, file, indent=4)

        file.truncate()


def send_warning_email_for_metric(site_name, 
                       cc,
                       metric,
                       metric_measure,
                       previous_alert_data,
                       source_file,
                       scoped_time_stamp
                       ):
    attachments = []
    label = " ".join([word.capitalize() for word in metric.split('_')])
    subject = f"Hardware Threshhold Breach: {label} on {site_name}"
    last_trigger_time = previous_alert_data.get(f'{metric}_last_trigger_time')
    last_trigger_time = get_datetime_string_from_timestamp(last_trigger_time) if last_trigger_time else "N/A."
    trend_graph = None
    export_folder = ''
    
    logging.info(f"Sending warning email for {label} breach on {site_name}")
    
    logging.info("Generating graphics")
    
    metric_graphic = generate_hardware_graphic(metric, site_name, metric_measure)
    
    intervals = int(get_interval_in_minutes('hardware') * 60)
    logging.info(f"Generating graphic trends for the last hour: {intervals} intervals")
    logging.info(f"Source for trends for the last hour: {source_file} intervals")
    
    last_hr_trends = generate_graphs_for_daily_report(
        site_name=site_name,
        hardware_source_file=source_file,
        last_n_items=intervals
    )
    
    # Generate and attach graph of last hour worth or records
    if last_hr_trends:
        trend_graph = last_hr_trends[0]
        logging.info(f"Adding last hr trend graph to attachements {trend_graph}")
        attachments.append(trend_graph)
        export_folder = os.path.dirname(trend_graph)
        
    # Generate graphic for n: 10 records before and after recorded spike
    time_scoped_graphic = generate_graphs_for_daily_report(
        site_name=site_name,
        hardware_source_file=source_file,
        scoped_time_stamp=scoped_time_stamp
    )
    
    if time_scoped_graphic:
        scoped_graph = time_scoped_graphic[0]
        logging.info(f"Adding time scoped graph {scoped_time_stamp} to attachments {scoped_graph}")
        attachments.append(scoped_graph)
        export_folder = os.path.dirname(trend_graph)

    logging.info(f'Attaching graphic at {metric_graphic}')
    attachments.append(metric_graphic)

    msg = (
        f"Greetings,\n\n"
        f"Kindly note that the site {site_name}'s {label} has breached it's threshold. Please check the attached graphic for your perusal.\n\n"
        f"The following parameters have been breached:\n\n"
        f"{label} currently has a value of {metric_measure} %.\n"
        f"Previous trigger time: {last_trigger_time}\n"
        f"Regards"
    )

    # send email with graphic attachment
    logging.info("Sending email")
    send_email(cc, subject, msg, attachments)
    
    if export_folder:
        logging.info("Now clearing directory")
        clear_folder(export_folder)
    


def get_interval_in_minutes(metric):
    metric_interval_map = {
        "hardware": "HARDWARE_CHECK_INTERVAL",
        "ping": "PING_INTERVAL"
    }
    conf = get_config()
    # Return interval in minutes
    return conf.get(metric_interval_map.get(metric.lower()), 60) / 60


def get_data_scoped_by_time_stamp(timestamp, data, n=10):
    logging.info(f"Timestamp Recorded - {timestamp}")
    data_sorted = sorted(data, key=lambda x: x['timestamp'])
    
    index = -1
    for i, entry in enumerate(data_sorted):
        if entry['timestamp'] <= timestamp:
            index = i
        else:
            break
        
    start_index = max(0, index - 10)
    end_index = min(len(data_sorted), index + 11)
    return data_sorted[start_index: end_index]

def clear_folder(folder):
    # clear folder before generating new graphs
    if not os.path.exists(folder):
        return

    for file in os.listdir(folder):
        os.remove(os.path.join(folder, file))
