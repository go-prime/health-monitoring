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
"MAXIMUM_NO_OF_ALARM_STATE_TRIGGERS": 5 # the number of triggers in the last 10 iterations that will set off an alert.
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

# Third-Party Libraries

* `plotly` - Declarative charting library.

* `kaleido` - library for generating static images.

* `requests` - HTTP client library for the Python.