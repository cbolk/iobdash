# import dash IO and graph objects
from dash.dependencies import Input, Output

# Plotly graph objects to render graph plots
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Import dash html, bootstrap components, and tables for datatables
import dash_html_components as html
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_table

# Import app
from app import app

# Call back to OBP Line Graph
@app.callback(
    Output("data-loss", "figure"),
    [Input("imu-reading-update", "n_intervals")], 
    [
          State("imu-reading", "figure"),
    ],
)
def update_data_loss(interval):

def gen_data_loss(interval, imu_reading_figure):
    """
    Generate data loss chart.
    :params interval: update the graph based on an interval
    """

    dfloss.tail(DATALOSS_WINDOW)

    traceFill = dict(
        type="bar",
        name="Single IMU data loss",
        y=dfloss["fill"],
        line={"color": "Orange"},
        hoverinfo="skip",
        opacity=0.4,
    )

    traceEmpty = dict(
        type="bar",
        name="IMUs data loss",
        y=dfloss["empty"],
        line={"color": "#EF3E42"},
        hoverinfo="skip",
        opacity=0.4,
    )

    layout = dict(
        height=350,
        font={"color": "#000"},
        barmode="stack",
        autosize=False,
        showlegend=False,
    )

    return dict(data=[traceFill, traceEmpty], layout=layout)