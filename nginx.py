import re
import logging

# Set up logging
logging.basicConfig(filename='logs/nginx_analysis.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_nginx_log(log_file):
    # Regular expression to parse log lines
    log_pattern = re.compile(r'(\S+) - - \[(.*?)\] "\S+ \S+ \S+" (\d{3}) \S+')
    
    total_requests = 0
    failed_requests = 0
    
    try:
        with open(log_file, 'r') as file:
            for line in file:
                match = log_pattern.match(line)
                if match:
                    total_requests += 1
                    status_code = int(match.group(3))
                    if status_code >= 400:
                        failed_requests += 1
    except FileNotFoundError:
        logging.error(f"Log file {log_file} not found")
        return None

    failure_rate = (failed_requests / total_requests) * 100 if total_requests > 0 else 0
    return total_requests, failed_requests, failure_rate

if __name__ == "__main__":
    log_file_path = '/var/log/nginx/access.log'
    total, failed, failure_rate = parse_nginx_log(log_file_path)
    
    if total is not None:
        logging.info(f"Total Requests: {total}")
        logging.info(f"Failed Requests: {failed}")
        logging.info(f"Failure Rate: {failure_rate:.2f}%")
        print(f"Total Requests: {total}")
        print(f"Failed Requests: {failed}")
        print(f"Failure Rate: {failure_rate:.2f}%")
    else:
        logging.error("Failed to analyze the log file.")
