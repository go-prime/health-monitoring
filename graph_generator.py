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


def generate_hardware_graphic(metric, sitename, metric_value):
    exports_folder = get_export_folder(site_name=sitename, metric=metric)
    
    date_time_string = datetime.date.today().strftime("%Y_%m_%d")
    file_name = f'{metric}_warning_{date_time_string}.png'
    export_path = os.path.join(exports_folder, "warnings")
    
    if not os.path.exists(export_path):
        os.makedirs(export_path)
        
    file_loc = os.path.join(export_path, file_name)
    
    # Create a pie chart
    fig = go.Figure(data=[go.Pie(
        labels=["Used", "Free"],
        values=[metric_value, 100 - metric_value],
        hole=.3
    )])
    
    label = " ".join(metric.split("_")).title()
    # Set chart title
    fig.update_layout(
        title_text=f"{label} Warning.",
        annotations=[dict(text=f"{metric_value}%", x=0.5, y=0.5, font_size=20, showarrow=False)],
        width=900
    )

    fig.write_image(file_loc)
    return file_loc


def get_export_folder(site_name, metric):
    return os.path.join('exports', 'images', site_name, metric)


def generate_graphic(site_name, metric):
    datetime_str = datetime.date.today().strftime("%Y_%m_%d")

    metric_source_map = {
        'hardware': f'hardware_metrics_{datetime_str}.json',
        'ping': f'ping_metrics_{datetime_str}.json'
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

    if not check_file_exists(f'results/{site_name}/{subfolder}/{source_file}') and metric == "ping":
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


def generate_hardware_metrics_trends_graph(site, data, time_scoped_filtered=False, last_n_filtered=False, scope_by_metric=None):
    if not data:
        return

    filter_label = ''
    trace_list = []
    metric_data = []
    
    if time_scoped_filtered:
        filter_label = f"Filtered By Time: Closer Snapshot View."
    
    if last_n_filtered:
        filter_label = "Filtered By Time: Last 60 minutes."

    hardware_breakdown = {}
    sub_folder = 'hardware_metrics'
    exports_folder = os.path.join('exports', 'images', 'reports', site, sub_folder)

    if not os.path.exists(exports_folder):
        os.makedirs(exports_folder)

    filtered_data = sorted([entry for entry in data if entry['timestamp']], key=lambda x: x['timestamp'])
    timestamps = [get_datetime_string_from_timestamp(entry['timestamp']) for entry in filtered_data]
    
    if not scope_by_metric:
        # Plotting Data
        ram_usage_percentages = [entry["ram_usage_percentage"] for entry in data]
        load_avg_last_10_mins = [item['load_avg_last_10_mins'] for item in data]
        cpu_usage = [item['cpu_usage'] for item in data]

        # Averages
        ram_usage_avg = statistics.mean([item['ram_usage_percentage'] for item in data])
        load_last_10_mins_avg = statistics.mean([item['load_avg_last_10_mins'] for item in data])
        cpu_usage_avg = statistics.mean([item['cpu_usage'] for item in data])

        hardware_breakdown = {
            'ram_usage_avg': round(ram_usage_avg, 5),
            'load_last_10_mins_avg': round(load_last_10_mins_avg, 2),
            'cpu_usage_avg': round(cpu_usage_avg, 2)
        }

        ram_trace = go.Scatter(x=timestamps, y=ram_usage_percentages, mode='lines', name='RAM Usage Percentage', yaxis="y1")
        cpu_trace = go.Scatter(x=timestamps, y=cpu_usage, mode='lines', name='CPU Usage', yaxis="y1")
        load_last_10_mins_trace = go.Scatter(x=timestamps, y=load_avg_last_10_mins, mode='lines', name='Load Avg (10 mins)', yaxis="y2")

        trace_list = [cpu_trace, ram_trace, load_last_10_mins_trace]
    else:
        if scope_by_metric == "ram_usage":
            metric_data = [item.get('ram_usage_percentage', 0.0) for item in data]
        
        if scope_by_metric == "load_avg_last_10_mins":
            metric_data = [item.get('load_avg_last_10_mins', 0.0) for item in data]
        
        if scope_by_metric == "disk_usage":
            metric_data = [
                ((entry["disk_usage_used"] / (entry["disk_usage_free"] + entry["disk_usage_used"])) * 100) for entry in data
            ]
            


        metric_trace = go.Scatter(x=timestamps, y=metric_data, mode='lines', name=scope_by_metric, yaxis="y1")
        trace_list = [metric_trace]

    file_prefix = str(datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))

    fig = go.Figure(trace_list)
    if not scope_by_metric:
        fig.update_layout(
            title=f'System Metrics Over Time {filter_label}',
            xaxis_title='Timestamp',
            yaxis_title='Usage %',
            yaxis=dict(
                title="Usage %",
                titlefont=dict(color="blue"),
                tickfont=dict(color="blue")
            ),
            yaxis2=dict(
                title="Load (AVGs)",
                titlefont=dict(color="red"),
                tickfont=dict(color="red"),
                overlaying='y',
                side='right'
            ),
            width=1000
        )
    else:
        fig.update_layout(
            title=f'System Metrics Over Time {filter_label}',
            xaxis_title='Timestamp',
            yaxis_title='Usage %',
            width=1000
        )

    filter_string = ''
    if time_scoped_filtered:
        filter_string = "time_scoped"
    elif last_n_filtered:
        filter_string = "latest_trends"
    else:
        filter_string = ''
    
    export_path = os.path.join(exports_folder, f'{file_prefix}_{filter_string}_hardware_metrics_trends.png')
    fig.write_image(export_path)
    return export_path, hardware_breakdown


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

    filtered_data = sorted([entry for entry in data if entry['timestamp']], key=lambda x: x['timestamp'])
    timestamps = [get_datetime_string_from_timestamp(entry['timestamp']) for entry in filtered_data]
    
    
    statuses = [1 if entry['status'] == "success" else 0 for entry in data]
    successful_pings = [item for item in statuses if item == 1] 
    status_avg_success = round((len(successful_pings) / len(statuses)), 3) * 100

    ping_breakdown = {
        'status_avg_success': status_avg_success
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


def generate_graphs_for_daily_report(site_name,
                                     hardware_source_file=None,
                                     ping_source_file=None,
                                     last_n_items=None,
                                     scoped_time_stamp=None,
                                     scope_by_metric=None
                                     ):
    from utils import get_data_scoped_by_time_stamp

    # hardware_data
    # last n items fetches the latest n items from data list
    # as a reflection of time the total period covered will be last_n_items x ping/hardware_check_interval
    hardware_graph_file = None
    ping_graph_file = None
    breakdown = {}

    if hardware_source_file:
        last_n_filtered = last_n_items is not None
        time_scoped_filtered = scoped_time_stamp is not None
        with open(hardware_source_file) as hardware_file:
            hardware_data = json.load(hardware_file)
            # get last n items if set
            if last_n_items:
                hardware_data = hardware_data[-last_n_items:]
            if scoped_time_stamp:
                hardware_data = get_data_scoped_by_time_stamp(
                    timestamp=scoped_time_stamp,
                    data=hardware_data
                )
        hardware_graph_file, breakdown["hardware"] = generate_hardware_metrics_trends_graph(site_name, 
                                                                                            hardware_data,
                                                                                            last_n_filtered=last_n_filtered,
                                                                                            time_scoped_filtered=time_scoped_filtered,
                                                                                            scope_by_metric=scope_by_metric
                                                                                            )

    # ping data
    if ping_source_file:
        with open(ping_source_file) as ping_file:
            ping_data = json.load(ping_file)
            if last_n_items:
                ping_data = ping_data[-last_n_items:]
        ping_graph_file, breakdown["ping"] = generate_ping_metrics_trends_graph(site_name, ping_data)

    return hardware_graph_file, ping_graph_file, breakdown
