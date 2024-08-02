import json, os
import time
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from graph_generator import generate_graphic
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


def prune_graphs(site_name):
    logging.info(f"Pruning graphs for site: {site_name}")
    # get site folder
    site_folder = os.path.join('exports/images', site_name)
    
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
    

def get_latest_graphic(site_name):
    site_folder = os.path.join('exports/images', site_name)
    if not os.path.exists(site_folder):
        os.makedirs(site_folder)
    graphic_files = [f for f in os.listdir(site_folder) if f.endswith('.png')]
    
    if not graphic_files:
        return None
    graphic_files.sort(reverse=True)
    
    return os.path.join(site_folder, graphic_files[0])


def send_warning_email():
    logging.info("Sending warning email")
    # generate new graphic
    if not SITE_NAME:
        raise ValueError("SITE_NAME not provided in config")
    
    logging.info("Generating graphic")
    
    # Prune graphs before generating new graphic
    prune_graphs(SITE_NAME)
    generate_graphic(SITE_NAME)
    
    msg = f"""
    Greetings
    
    Kindly note that the site {SITE_NAME} is down. Please check the attached graphic for more details.

    Regards
    """
    
    subject = f"Site {SITE_NAME} is down"
    
    # Get latest graphic from site folder
    logging.info("Getting latest graphic")
    img_file = get_latest_graphic(SITE_NAME)
    logging.info(f"Graphic file: {img_file}")
    
    # send email with graphic attachment
    logging.info("Sending email")
    send_email(MAILING_LIST, subject, msg, img_file)


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
        logging.info(f'Retry count: {retries}')
        try:
            response = s.get(url)
            if response.status_code == 200:
                return True
            else:
                retries += 1
        except requests.RequestException:
            retries += 1
            if retries <= MAX_RETRY_ATTEMPTS:
                time.sleep(5)
    # When max number of retries is reached, return False
    # Send warning email
    send_warning_email()
    
    

def ping_url(url, interval, output_file):
    results = []

    while True:
        logging.info(f'Pinging: {url}')
        try:
            response = requests.get(url)
            if response.status_code == 200:
                logging.info(f'Successfully reached {url}')
                results.append({"timestamp": time.time(), "status": "success"})
            else:
                logging.info(f'Failed to reach {url}')
                logging.info('Retrying to connect')
                # retry ping
                ping_retry(url)
                
                
                results.append({"timestamp": time.time(), "status": "failure", "status_code": response.status_code})
        except requests.RequestException as e:
            logging.info(f'Error - {e}')
            results.append({"timestamp": time.time(), "status": "failure", "error": str(e)})
            
            # retry ping
            ping_retry(url)

        with open(output_file, 'w') as file:
            json.dump(results, file, indent=4)

        time.sleep(interval)

if __name__ == "__main__":
    url_to_ping = PING_URL
    ping_interval = PING_INTERVAL
    
    # create sites results folder if it doesn't exist
    results_folder = os.path.join('results', SITE_NAME)
    if not os.path.exists(results_folder):
        os.makedirs(results_folder)    
        # Create file
        with open(os.path.join(results_folder, 'ping_results.json'), 'w') as file:
            json.dump([], file)
        
    output_filename = results_folder + '/ping_results.json'
    logging.info('Starting Up')
    ping_url(url_to_ping, ping_interval, output_filename)
