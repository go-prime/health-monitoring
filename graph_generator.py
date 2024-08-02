import os
import json
import datetime

import plotly.graph_objects as go

# Check if file exists
def check_file_exists(file_path):
    return os.path.exists(file_path)


def generate_graphic(site_name):
    if not check_file_exists(f'results/{site_name}/ping_results.json'):
        raise FileNotFoundError("Ping results file not found")
    
    # load ping results
    with open(f'results/{site_name}/ping_results.json') as results_file:
        results = json.load(results_file)
    
    # Create folder with site name if it does not exist
    exports_folder = os.path.join('exports', 'images', site_name)
    if not os.path.exists(exports_folder):
        os.makedirs(exports_folder)
        
    # Extract timestamps and statuses
    timestamps = [result['timestamp'] for result in results]
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
    file_prefix = str(datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
    # fig.write_image(f"results/site_name/{file_prefix}_ping_graph.png")
    fig.write_image(exports_folder + f"/{file_prefix}_ping_graph.png")
    
    
    