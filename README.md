# health-monitoring

# System no comprises of three primary functions

1. Ping (Network Availability Monitoring)- attempts to connect to specified ip PING_URL in conf/config.json
2. Hardware (Metric Monitoring CPU Usage, Disk Usage, Ram Usage)
3. Reporting

# Add config file

  

```
# add file names config.json on the config folder within the project root directory

{
"PING_URL": "https://example.com",
"PING_INTERVAL": 60, # in seconds
"MAILING_LIST": ["james@chitubu.co.zw", "smoyo@gmail.com"],
"MAILER_EMAIL": "mailer@service.mail",
"MAILER_PASSWORD": "p@55w0rd",
"SMTP_SERVER": "smtp.gmail.com", # depending on service used
"SMTP_PORT": 465, # depending on service configd
"MAX_RETRY_ATTEMPTS": 4,
"SITE_NAME": "test", # in order to uniquely id graph and metric folders
"MAX_FOLDER_SIZE": 1000,# in mb to determine max size of graph for each site
"EXCLUDE_PING_FROM_REPORTING": true,
"EXCLUDE_HARDWARE_CHECK_FROM_REPORTING": false,
"BUSINESS_DAY_START": "09:00", # used to validate working hours
"BUSINESS_DAY_END": "17:00", # used to validate working hours
"BUSINESS_WEEK_START": "MONDAY", # used to validate work week
"BUSINESS_WEEK_END": "FRIDAY"
}
```

# Setting Up

  

*Ensure you are in in project root folder*

  
```
ls
config/ exports/ graph_generator.py logs/ mailer.py main.py nginx.py README.md requirements.txt results/
```
### 1. Create virtual environment

`python3 -m venv`

### 2. Activate virtual environment

```
# Linux
source venv\bin\activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

`python -m pip install -r requirments.txt`
  
### 4. Run Scripts

```
# Ping Script
python ping_monitor.py

# Hardware Monitoring
python hardware_monitor.py

``` 

### 5. Supervisor

* Locate file health-monitoring\health_monitoring.conf
* Enter configs based on template
* You may need to add configs for the two scripts

`supervisorctl reread`

`supervisorctl reload`

`supervisorctl restart all`


***

### 6. Reporting

* Locate and modify health-monitoring\daily_report.sh for linux health-monitoring\daily_report.bat for windows
* Add script to cron jon or windows scheduler to run daily at set time

```
# Windows
schtasks /create /tn "DailyHealthMonitoringReport" /tr "<pathto>\health-monitoring\daily_report.bat" /sc daily /st 16:30

# Query task
schtasks /query /tn "DailyHealthMonitoringReport"

# Linux
crontab -e

30 16 * * * /path/to/health-monitoring/daily_report.sh

# Query cron jobs

crontab -l
```

# 6.b Recent Activity Reporting

* To generate report for recent activty
* Passing the arg: last n items will return results for the last n recorded results
* If interval is set at 60 for 60 seconds and the arg is set to 30 the report will return activity for the last 30 mins
* Period covered = last_n_items * interval
* set a shell script and provide the argument to report generate

```
# bash
path_to_venv  project_dir/report_generator.py "SITE_NAME" 30
```

# Third-Party Libraries

* `plotly` - Declarative charting library.

* `kaleido` - library for generating static images.

* `requests` - HTTP client library for the Python.

# Issues

* Need a recommened way to allow report generator to do restarts
* Need to create seperate graphs for hardware metrics
* Need to expand metrics being tracked
* Need to implement a strategy to manage logfile size
* Need to reimplement alerting logic. The tests have shown that concerning parameter peaks are not being alerted. The logic is falling short