
  

# health-monitoring

  

  

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
"SITE_NAME": "test" # in order to uniquely id graph and metric folders
"MAX_FOLDER_SIZE": 1000 # in mb to determine max size of graph for each site
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
  
### 4. Run Script

`python main.py`

***

# Third-Party Libraries