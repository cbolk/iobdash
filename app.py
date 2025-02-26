import os
import pathlib
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import dash
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc

from dash.exceptions import PreventUpdate
from dash.dependencies import Input, Output, State
from scipy.stats import rayleigh
from imu.api import get_imu_data


GRAPH_INTERVAL = 5000 #milliseconds
#number of samples to be plotted
GRAPH_WINDOW = 10
DATALOSS_WINDOW = 10
#name of the signal to be plotted
SIGNAL_PLOT = "01_1" #fB_median_Tot"


dfloss = pd.DataFrame(columns=["fromTH","toTH","rangeTH","fill","empty"])


app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
app.title = "DASH"

server = app.server

app.layout = html.Div(
    [
        # header
        html.Div(
            [
                html.Div(
                    [
                        html.H4("IMU READINGS", className="app__header__title"),
                        html.P(
                            "This app continually queries three files and displays live charts of collected data.",
                            className="app__header__title--grey",
                        ),
                    ],
                    className="app__header__desc",
                ),
                html.Div(
                    [
                        html.A(
                            html.Button("SOURCE CODE", className="link-button"),
                            href="https://github.com/plotly/dash-sample-apps/tree/main/apps/dash-wind-streaming",
                        ),
                        html.A(
                            html.Button("ENTERPRISE DEMO", className="link-button"),
                            href="https://plotly.com/get-demo/",
                        ),
                        html.A(
                            html.Img(
                                src=app.get_asset_url("dash-logo-new-pass.png"),
                                className="app__menu__img",
                            ),
                            href="https://plotly.com/dash/",
                        ),
                    ],
                    className="app__header__logo",
                ),
            ],
            className="app__header",
        ),
        html.Div(
            [
                # wind speed
                html.Div(
                    [
                        html.Div(
                            [html.H6("VALUE", className="graph__title")]
                        ),
                        dcc.Graph(
                            id="imu-reading",
                            figure=dict(),
                        ),
                        dcc.Interval(
                            id="imu-reading-update",
                            interval=int(GRAPH_INTERVAL),
                            n_intervals=0,
                        ),
                    ],
                    className="two-thirds column imu__reading__container",
                ),
                html.Div(
                    [
                        # histogram
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.H6(
                                            "DATA LOSS",
                                            className="graph__title",
                                        )
                                    ]
                                ),
                                dcc.Graph(
                                    id="data-loss",
                                    config={"displayModeBar": False},
                                    figure=dict(),
                                ),
                            ],
                            className="graph__container first",
                        ),
                    ],
                    className="one-third column histogram__direction",
                ),
            ],
            className="app__content",
        ),
    ],
    className="app__container",
)

def get_current_time():
    """ Helper function to get the current time in seconds. """

    dt = datetime.now() - timedelta(seconds=300)
    return dt.time()


def add_dataloss_stats(df, fromTH, toTH, nfills, nempty):
    #["fromTH","toTH","rangeTH","fill","empty"]
    df.loc[len(df)] = [fromTH, toTH, str(fromTH) + "-" + str(toTH), nfills, nempty]
    print(df)
    return df


@app.callback(
    Output("imu-reading", "figure"), 
    [Input("imu-reading-update", "n_intervals")]
)
def gen_imu_reading(interval):
    """
    Generate the imu reading chart.

    :params interval: update the graph based on an interval
    """

    sel_time = get_current_time()
    df, fromTH, toTH, nmiss, nempty = get_imu_data(sel_time, GRAPH_WINDOW)
    add_dataloss_stats(dfloss, fromTH, toTH, nmiss, nempty)

    trace1 = dict(
        type="scatter",
        name="q1 thorax",
        y=df["01_1"],
        line={"color": "#332288"},
        hoverinfo="skip",
        mode="lines",
    )

    trace2 = dict(
        type="scatter",
        name="q2 thorax",
        y=df["01_2"],
        line={"color": "#44AA99"},
        hoverinfo="skip",
        mode="lines",
    )

    trace3 = dict(
        type="scatter",
        name="q3 thorax",
        y=df["01_3"],
        line={"color": "#CC6677"},
        hoverinfo="skip",
        mode="lines",
    )

    trace4 = dict(
        type="scatter",
        name="q4 thorax",
        y=df["01_4"],
        line={"color": "#DDCC77"},
        hoverinfo="skip",
        mode="lines",
    )

    layout = dict(
        font={"color": "#000"},
        height=700,
        xaxis={
            "range": [fromTH, toTH],
            "showline": True,
            "zeroline": False,
            "fixedrange": True,
#            "tickvals": [0, 50, 100, 150, 200],
#           "ticktext": ["200", "150", "100", "50", "0"],
            "title": "Counter",
        },
        yaxis={
            "range": [-1, 1],
            "showgrid": True,
            "showline": True,
            "fixedrange": True,
            "zeroline": False,
#            "nticks": max(6, round(df["Speed"].iloc[-1] / 10)),
        },
    )

    return dict(data=[trace1, trace2, trace3, trace4], layout=layout)


@app.callback(
    Output("data-loss", "figure"),
    [Input("imu-reading-update", "n_intervals")], 
    [
          State("imu-reading", "figure"),
    ],
)
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


# @app.callback(
#      Output("data-loss", "figure"),
#      [Input("imu-reading-update", "n_intervals")],
#      [
#          State("imu-reading", "figure"),
#      ],
# )
def gen_data_loss_b(interval, imu_reading_figure):
    """
    Genererate wind histogram graph.

    :params interval: update the graph based on an interval
    :params wind_speed_figure: current wind speed graph
    """


    trace = dict(
        type="bar",
        x=bin_val[1],
        y=bin_val[0],
        marker={"color": "Orange"},
        showlegend=False,
        hoverinfo="x+y",
    )

    layout = dict(
        height=350,
        font={"color": "#000"},
        xaxis={
            "title": "Wind Speed (mph)",
            "showgrid": False,
            "showline": False,
            "fixedrange": True,
        },
        yaxis={
            "showgrid": False,
            "showline": False,
            "zeroline": False,
            "title": "Number of Samples",
            "fixedrange": True,
        },
        autosize=True,
        bargap=0.01,
        bargroupgap=0,
        hovermode="closest",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "xanchor": "center",
            "y": 1,
            "x": 0.5,
        },
        shapes=[
            {
                "xref": "x",
                "yref": "y",
                "y1": int(max(bin_val_max, y_val_max)) + 0.5,
                "y0": 0,
                "x0": avg_val,
                "x1": avg_val,
                "type": "line",
                "line": {"dash": "dash", "color": "#2E5266", "width": 5},
            },
            {
                "xref": "x",
                "yref": "y",
                "y1": int(max(bin_val_max, y_val_max)) + 0.5,
                "y0": 0,
                "x0": median_val,
                "x1": median_val,
                "type": "line",
                "line": {"dash": "dot", "color": "#BD9391", "width": 5},
            },
        ],
    )
    return dict(data=[trace, scatter_data[0], scatter_data[1], trace3], layout=layout)



if __name__ == "__main__":
    app.run_server(debug=True)
