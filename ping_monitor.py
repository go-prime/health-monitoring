import json, os
import time
import datetime
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils import current_time_within_business_hours, export_to_json_file, send_warning_email


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

# business working hours
BUSINESS_STARTING_HOUR = config.get("BUSINESS_START", "08:00")
BUSINESS_FINISHING_HOUR = config.get("BUSINESS_START", "17:00")

# Get max thresholds for hardware
RAM_USAGE_MAX_THRESH_HOLD = config.get('RAM_USAGE_MAX_THRESH_HOLD', 80)
CPU_USAGE_MAX_THRESH_HOLD = config.get('CPU_USAGE_MAX_THRESH_HOLD', 80)
HDD_USAGE_MAX_THRESH_HOLD = config.get('HDD_USAGE_MAX_THRESH_HOLD', 80)

# Get maximum number of alarm state triggers
MAXIMUM_NO_OF_TRIGGERS = config.get('MAXIMUM_NO_OF_ALARM_STATE_TRIGGERS', 3)


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
    logging.info(f'Logging File {output_file} found. TRUE:{os.path.exists(output_file)}')

    export_to_json_file(results, output_file)

    return connected


def process_metrics(url, interval, ping_results_folder):
    ping_alarm_stage_triggered = False

    while True:
        date_string = datetime.date.today().strftime("%Y_%m_%d")
        output_file = ping_results_folder + f'/ping_results_{date_string}.json'

        curr_time = time.strftime("%H:%M")
        curr_date = datetime.datetime.now().date().strftime("%a")
        
        # Check if current date and time with working hours
        if current_time_within_business_hours():
            logging.info(f'Current TIME:{curr_time} DAY:{curr_date} within business hours')
            url_accessed = ping_url(url, output_file)
            
            if not url_accessed:
                # Get last 10 ping results
                with open(output_file, 'r') as file:
                    ping_results = json.load(file)[-10:]

                logging.info(f'Ping Results: Last 3 {ping_results[:3]}')
                logging.info(f'Maximum number of triggers permitted: {MAXIMUM_NO_OF_TRIGGERS}')


                logging.info(f'Assessing Ping Triggers:')
                logging.info(f'{str(["x" for r in ping_results if r.get("status") == "failure"])}')

                fail_list = [result for result in ping_results if result.get('status') == 'failure']

                logging.info(f'Ping failures: {fail_list}')

                no_of_ping_failures = len(fail_list)

                logging.info(f'Number of ping failures: {no_of_ping_failures}')
                if no_of_ping_failures >= MAXIMUM_NO_OF_TRIGGERS:
                    ping_alarm_stage_triggered = True

                logging.info(f'Ping Alarm Stage Triggered: {ping_alarm_stage_triggered}')

                send_warning_email(
                    site_name=SITE_NAME,
                    cc=MAILING_LIST,
                    ping_alarm_triggered=ping_alarm_stage_triggered,
                    ping_retries=MAX_RETRY_ATTEMPTS
                )
        else:
            logging.info(f'Current TIME:{curr_time} DAY:{curr_date} is outside business hours. Skipping ping monitoring.')

        time.sleep(interval)


if __name__ == "__main__":
    url_to_ping = PING_URL
    ping_interval = PING_INTERVAL

    # create sites results folder if it doesn't exist
    ping_results_folder = os.path.join('results', SITE_NAME, 'ping_metrics')
    date_string = datetime.date.today().strftime("%Y_%m_%d")
    if not os.path.exists(ping_results_folder):
        os.makedirs(ping_results_folder)
        # Create file
        with open(os.path.join(ping_results_folder, f'ping_results_{date_string}.json'), 'w') as file:
            json.dump([], file)

    logging.info('Starting Up')
    process_metrics(url_to_ping, ping_interval, ping_results_folder)
