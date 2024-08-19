import os
import json
import datetime
import statistics

import plotly.graph_objects as go
import psutil
import time


# Check if file exists
def check_file_exists(file_path):
    return os.path.exists(file_path)


def get_datetime_string_from_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def generate_hardware_graphic(metric):
    if metric == 'cpu_usage':
        # create pie chart showing cpu usage
        cpu_times = psutil.cpu_times_percent(interval=1, percpu=False)
        cpu_usage = {
            'User': cpu_times.user,
            'System': cpu_times.system,
            'Idle': cpu_times.idle
        }
        cpu_usage = {k: v for k, v in cpu_usage.items() if v > 0}
        fig = go.Figure(data=[go.Pie(labels=list(cpu_usage.keys()), values=list(cpu_usage.values()))])

        fig.update_layout(
            title_text='Current CPU Usage Distribution: Measured',
            annotations=[dict(text='CPU', x=0.5, y=0.5, font_size=20, showarrow=False)]
        )

    if metric == 'ram_usage':
        virtual_memory = psutil.virtual_memory()
        ram_usage = {
            'Used': virtual_memory.used,
            'Avalaible': virtual_memory.free,
            'Percent %': virtual_memory.percent
        }

        # Filter out zero values to avoid clutter
        ram_usage = {k: v for k, v in ram_usage.items() if v > 0}

        # Convert bytes to gig
        ram_usage = {k: v / (1024 ** 3) for k, v in ram_usage.items()}

        # Create the pie chart
        fig = go.Figure(data=[go.Pie(labels=list(ram_usage.keys()), values=list(ram_usage.values()), hole=.3)])

        fig.update_layout(
            title_text=f'RAM Usage Distribution: Measured',
            annotations=[dict(text='RAM', x=0.5, y=0.5, font_size=20, showarrow=False)]
        )

    if metric == 'disk_usage':
        disk_usage = psutil.disk_usage('/')
        disk_usage = {
            'Used': disk_usage.used,
            'Free': disk_usage.free
        }

        # Convert bytes to gigabytes
        disk_usage_data = {k: v / (1024 ** 3) for k, v in disk_usage_data.items()}

        # Create the pie chart
        fig = go.Figure(data=[go.Pie(labels=list(disk_usage_data.keys()), values=list(disk_usage_data.values()), hole=.3)])

        fig.update_layout(
            title_text=f'Disk Usage Distribution: Measured:',
            annotations=[dict(text='Disk', x=0.5, y=0.5, font_size=20, showarrow=False)]
        )

    return fig


def generate_graphic(site_name, metric, metrics_map=None):

    metric_source_map = {
        'hardware': 'hardware_metrics.json',
        'ping': 'ping_results.json'
    }

    subfolder_map = {
        'hardware': 'hardware_metrics',
        'ping': 'ping_metrics'
    }

    source_file = metric_source_map.get(metric)
    subfolder = subfolder_map.get(metric)

    if not source_file:
        raise ValueError("Invalid metric specified")

    if not subfolder:
        raise ValueError("Invalid metric specified")

    if not check_file_exists(f'results/{site_name}/{subfolder}/{source_file}'):
        raise FileNotFoundError("Ping results file not found")

    # load ping results
    with open(f'results/{site_name}/{subfolder}/{source_file}') as results_file:
        results = json.load(results_file)

    # Create folder with site name if it does not exist
    exports_folder = os.path.join('exports', 'images', site_name, subfolder)
    if not os.path.exists(exports_folder):
        os.makedirs(exports_folder)

    file_prefix = str(datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
    if metric == 'ping':    
        # Extract timestamps and statuses
        timestamps = [get_datetime_string_from_timestamp(result['timestamp']) for result in results]
        statuses = [1 if result['status'] == "success" else 0 for result in results]

        # Create the plot
        fig = go.Figure()

        # Add a scatter trace
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=statuses,
            mode='lines+markers',
            name='Ping Status'
        ))

        # Update layout
        fig.update_layout(
            title=f'Ping Success Over Time {site_name}',
            xaxis_title='Timestamp',
            yaxis_title='Status (1 = success)',
            showlegend=True
        )

        fig.write_image(os.path.join(exports_folder, f'{file_prefix}_ping_metrics.png'))

    elif metric == 'hardware':
        # # Current Metrics
        # for metric, _  in metrics_map.items():
        #     fig = generate_hardware_graphic(metric)
        #     fig.write_image(os.path.join(exports_folder, metric, f'{file_prefix}_{metric}_metrics.png'))
        timestamps = [get_datetime_string_from_timestamp(result['timestamp']) for result in results]
        cpu_usages = [entry["cpu_usage"] for entry in results]
        ram_usage_percentages = [entry["ram_usage_percentage"] for entry in results]
        load_avg_5mins = [entry["load_avg_last_5_mins"] for entry in results]
        load_avg_10mins = [entry["load_avg_last_10_mins"] for entry in results]
        load_avg_15mins = [entry["load_avg_last_15_mins"] for entry in results]

        latest_data = results[-1]

        # Pie chart for ram
        ram_usage_data = {
            'Free': latest_data.get('ram_usage_free', 0.0),
            'Used': latest_data.get('ram_usage_used', 0.0)
        }

        fig_ram = go.Figure(data=[go.Pie(labels=list(ram_usage_data.keys()), values=list(ram_usage_data.values()), hole=.3)])
        fig_ram.update_layout(
            title_text='RAM Usage Distribution',
            annotations=[dict(text='RAM', x=0.5, y=0.5, font_size=20, showarrow=False)]
        )


        # Pie chart for disk
        disk_usage_data = {
            'Free': latest_data.get('disk_usage_free', 0.0),
            'Used': latest_data.get('disk_usage_used', 0.0)
        }
        fig_disk = go.Figure(data=[go.Pie(labels=list(disk_usage_data.keys()), values=list(disk_usage_data.values()), hole=.3)])
        fig_disk.update_layout(
            title_text='Disk Usage Distribution',
            annotations=[dict(text='Disk', x=0.5, y=0.5, font_size=20, showarrow=False)]
        )

        # Pie chart for cpu
        cpu_usage_data = {
            'Used': latest_data.get('cpu_usage', 0.0),
            'Free': 100 - latest_data.get('cpu_usage', 0.0)
        }
        fig_cpu = go.Figure(data=[go.Pie(labels=list(cpu_usage_data.keys()), values=list(cpu_usage_data.values()), hole=.3)])
        fig_cpu.update_layout(
            title_text='CPU Usage Distribution',
            annotations=[dict(text='CPU', x=0.5, y=0.5, font_size=20, showarrow=False)]
        )

        fig_metrics = go.Figure()
        fig_metrics.add_trace(go.Scatter(x=timestamps, y=cpu_usages, mode='lines+markers', name='CPU Usage'))
        fig_metrics.add_trace(go.Scatter(x=timestamps, y=ram_usage_percentages, mode='lines+markers', name='RAM Usage Percentage'))
        fig_metrics.add_trace(go.Scatter(x=timestamps, y=load_avg_5mins, mode='lines+markers', name='Load Avg (5 mins)'))
        fig_metrics.add_trace(go.Scatter(x=timestamps, y=load_avg_10mins, mode='lines+markers', name='Load Avg (10 mins)'))
        fig_metrics.add_trace(go.Scatter(x=timestamps, y=load_avg_15mins, mode='lines+markers', name='Load Avg (15 mins)'))

        fig_metrics.update_layout(
            title='System Metrics Over Time',
            xaxis_title='Timestamp',
            yaxis_title='Value',
            legend_title='Metrics'
        )

        fig_metrics.update_layout(
            title='System Metrics Over Time',
            xaxis_title='Timestamp',
            yaxis_title='Value',
            legend_title='Metrics'
        )

        metric_folders = [
            os.path.join(exports_folder, 'ram_usage'),
            os.path.join(exports_folder, 'disk_usage'),
            os.path.join(exports_folder, 'system_metrics'),
            os.path.join(exports_folder, 'cpu_usage')
        ]

        for path in metric_folders:
            if not os.path.exists(path):
                os.makedirs(path)

        # Save the figures
        fig_ram.write_image(os.path.join(exports_folder, 'ram_usage', f'{file_prefix}_ram_metrics.png'))
        fig_disk.write_image(os.path.join(exports_folder, 'disk_usage', f'{file_prefix}_disk_metrics.png'))
        fig_metrics.write_image(os.path.join(exports_folder, 'system_metrics', f'{file_prefix}_system_metrics.png'))
        fig_cpu.write_image(os.path.join(exports_folder, 'cpu_usage', f'{file_prefix}_cpu_metrics.png'))

    else:
        raise ValueError("Invalid metric specified")


def generate_hardware_metrics_trends_graph(site, data):
    if not data:
        return

    hardware_breakdown = {}
    sub_folder = 'hardware_metrics'
    exports_folder = os.path.join('exports', 'images', 'reports', site, sub_folder)

    if not os.path.exists(exports_folder):
        os.makedirs(exports_folder)

    # clear folder before generating new graphs
    for file in os.listdir(exports_folder):
        os.remove(os.path.join(exports_folder, file))

    start = time.mktime((datetime.datetime.now() - datetime.timedelta(hours=8)).timetuple())
    timestamps = [get_datetime_string_from_timestamp(entry['timestamp']) for entry in data if entry['timestamp'] > start]
    cpu_usages = [entry["cpu_usage"] for entry in data]
    ram_usage_percentages = [entry["ram_usage_percentage"] for entry in data]
    disk_usage_percentages = [
       ((entry["disk_usage_used"] / (entry["disk_usage_free"] + entry["disk_usage_used"])) * 100) for entry in data
    ]

    disk_usage_avg = statistics.mean([(item['disk_usage_used'] / (item['disk_usage_used'] + item['disk_usage_free'])) * 100 for item in data])
    ram_usage_avg = statistics.mean([item['ram_usage_percentage'] for item in data])
    cpu_usage_avg = statistics.mean([item['cpu_usage'] for item in data])

    hardware_breakdown = {
        'disk_usage_avg': round(disk_usage_avg, 5),
        'ram_usage_avg': round(ram_usage_avg, 5),
        'cpu_usage_avg': round(cpu_usage_avg, 5)
    }

    cpu_trace = go.Scatter(x=timestamps, y=cpu_usages, mode='lines+markers', name='CPU Usage')
    ram_trace = go.Scatter(x=timestamps, y=ram_usage_percentages, mode='lines+markers', name='RAM Usage Percentage')

    file_prefix = str(datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))

    fig = go.Figure([cpu_trace, ram_trace])
    fig.update_layout(
        title='System Metrics Over Time',
        xaxis_title='Timestamp',
        yaxis_title='Value',
        legend_title='Metrics',
        width=900
    )

    fig.write_image(os.path.join(exports_folder, f'{file_prefix}_hardware_metrics_trends.png'))
    return os.path.join(exports_folder, f'{file_prefix}_hardware_metrics_trends.png'), hardware_breakdown


def generate_ping_metrics_trends_graph(site, data):
    if not data:
        return

    sub_folder = 'ping_metrics'
    exports_folder = os.path.join('exports', 'images', 'reports', site, sub_folder)
    ping_breakdown = {}

    if not os.path.exists(exports_folder):
        os.makedirs(exports_folder)

    # clear folder before generating new graphs
    for file in os.listdir(exports_folder):
        os.remove(os.path.join(exports_folder, file))

    timestamps = [get_datetime_string_from_timestamp(entry['timestamp']) for entry in data]
    statuses = [1 if entry['status'] == "success" else 0 for entry in data]

    status_avg_success = statistics.mean([item for item in statuses])
    ping_breakdown = {
        'status_avg_success': round(status_avg_success, 5)
    }

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=timestamps, y=statuses, mode='lines+markers', name='Ping Status'))

    fig.update_layout(
        title='Ping Success Over Time',
        xaxis_title='Timestamp',
        yaxis_title='Status (1 = success)',
        showlegend=True,
        width=900
    )

    file_prefix = str(datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
    fig.write_image(os.path.join(exports_folder, f'{file_prefix}_ping_metrics_trends.png'))
    return os.path.join(exports_folder, f'{file_prefix}_ping_metrics_trends.png'), ping_breakdown


def generate_graphs_for_daily_report(site_name, hardware_source_file=None, ping_source_file=None):
    # hardware_data
    hardware_graph_file = None
    ping_graph_file = None
    breakdown = {}

    if hardware_source_file:
        with open(hardware_source_file) as hardware_file:
            hardware_data = json.load(hardware_file)
        hardware_graph_file, breakdown["hardware"] = generate_hardware_metrics_trends_graph(site_name, hardware_data)


    # ping data
    if ping_source_file:
        with open(ping_source_file) as ping_file:
            ping_data = json.load(ping_file)
        ping_graph_file, breakdown["ping"] = generate_ping_metrics_trends_graph(site_name, ping_data)

    return hardware_graph_file, ping_graph_file, breakdown
