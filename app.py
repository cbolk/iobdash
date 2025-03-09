import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px
import io
import base64
from datetime import datetime, time, timedelta

from imu.align import convertlogs, align

IMUNAMES = {"01": ["thorax", "tho", "t"], "02": ["abdomen", "abd", "a"], "03": ["reference", "ref", "r"]}
HMCOLORS = {"collected": [1, "#1e8449"], "missing": [0, "#e0dfdf"]}  # Green/White Heatmap
TIMESTAMP = "TSTAMP"
IMUIDS = [x for x in IMUNAMES.keys()]
HMCOLS = [TIMESTAMP]
HMCOLS.extend(IMUIDS)
IMUELEM = "_1"


# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "Respiratory Analysis"

# Layout
app.layout = html.Div(style={'display': 'flex'}, children=[
    html.Div(style={'width': '200px', 'padding': '20px', 'borderLeft': '1px solid #ccc'}, children=[
        dcc.Upload(
            id='upload-data',
            children=html.Div([html.Button('Select Log File')]),
            multiple=False
        ),
        html.Br(),
        html.Div(id='file-info', style={'marginTop': '10px'}),
        html.Br(),
        html.Br(),
        html.Button("Save aligned csv", id="btn_download", n_clicks=0, style={"display": "none"}),
        dcc.Download(id="save_csv")
    ]),
    html.Div(style={'flex': '1', 'padding': '20px'}, children=[
        dcc.Loading(id="loading-spinner", type="circle", children=[
            dcc.Tabs(id="tabs", value='tab1', children=[
                dcc.Tab(label='IMU Traces', value='tab1'),
                dcc.Tab(label='Data Acquisition Analysis', value='tab2'),
                dcc.Tab(label='Data Analysis', value='tab3')
            ]),
            html.Div(id='tabs-content', style={'marginTop': '20px'})
        ])
    ]),
    dcc.Store(id='aligned-df', data={}),
    dcc.Store(id='quality-df', data={})
])

def parse_content(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif filename.endswith('.txt'):
            payloads = convertlogs(decoded.decode('utf-8'), 3)
            df, _, _, _ = align(payloads, 3)
        else:
            return html.Div("Unsupported file format"), None, None

        ## a few more stats
        datastats = {}

        if TIMESTAMP in df.columns:            
            fromtime = datetime.strptime(df.loc[0,TIMESTAMP], '%d:%m:%H:%M:%S:%f')
            totime = datetime.strptime(df.loc[len(df)-1,TIMESTAMP], '%d:%m:%H:%M:%S:%f')
            timediff =  totime - fromtime
            hours, remainder = divmod(timediff.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            strDuration = f"{int(hours)}hr {int(minutes)}min {int(seconds)}sec"
        else:
            strDuration = " -- "
        datastats["timewindow"] = strDuration

        nstamps = len(df)
        cnames = []
        for imu in IMUIDS:
            cname = imu + IMUELEM
            cnames.append(cname)
            num_miss = df[cname].isna().sum()
            datastats[imu] = [num_miss, num_miss/nstamps]
        num_imus = len(IMUIDS)
        stats_miss = [0]*num_imus
        for i in range(0, num_imus):
            nocc = ((df[cnames].isna().sum(axis=1) == i)).sum()
            stats_miss[i] = nocc
        datastats["num_imus"] = num_imus
        datastats["total"] = nstamps
        datastats["empty"] = df[cnames].isna().all(axis=1).sum()
        datastats["full"] = df[cnames].notna().all(axis=1).sum()
        datastats["nsamples"] = num_imus * nstamps
        datastats["stats"] = stats_miss
        return html.Div([
            html.H5(filename)
        ]), df.to_dict('records'), datastats
    except Exception as e:
        return html.Div(f"Error processing file: {str(e)}"), None, None

@app.callback(
    Output("btn_download", "style"),
    Input("aligned-df", "data"),
    State('upload-data', 'filename')
)
def toggle_button_visibility(data, filename):
    if filename is not None and filename.endswith('.txt'):
        if data is not None and len(data) > 0:
            return {"display": "block"}  # Show button
    return {"display": "none"}  # Hide button


@app.callback(
    Output("save_csv", "data"),
    Input("btn_download", "n_clicks"),
    [State('aligned-df', 'data'),
    State('upload-data', 'filename')],
    prevent_initial_call=True
)
def generate_csv(n_clicks, data, filename):
    if filename is None:
        return html.Div("No data to be saved")
    ext = filename[filename.rfind(".")+1:]
    fileout = filename.replace(ext, "csv")

    df = pd.DataFrame(data)
    return dcc.send_data_frame(df.to_csv, filename=fileout, index=False)


@app.callback(
    [Output('tabs-content', 'children'), 
     Output('file-info', 'children'),
     Output('aligned-df', 'data'),
     Output('quality-df', 'data')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')]
)
def update_output(contents, filename):
    if filename is None:
        return html.Div(
            html.H3(children="Upload a file to get started",
                style={'color':'#00361c','text-align':'center'})
                    ), "", {}, {}
    #className="hello"
    if contents is None:
        return html.Div("Selected file, but no content loaded."), "No content uploaded", {}, {}
    
    file_info, df, dstats = parse_content(contents, filename)
    if df is None:
        return file_info, "Error loading file", {}, {}

    file_details = html.Div([
        html.P([html.B("Filename:"), f" {filename}"]),
        html.Br(),
        html.P([html.B("Time window:")]),
        html.P(dstats["timewindow"]),        
        html.P([html.B("Sampled events:")]),
        html.P(dstats["total"])        
    ])
    return html.Div(id='tab-content', children=[]), file_details, df, dstats

@app.callback(
    Output('tab-content', 'children'),
    [Input('tabs', 'value'),
     Input('aligned-df', 'data'),
     Input('quality-df', 'data')],
    [State('upload-data', 'filename')]
)
def render_tab(tab, df, dfstats, filename):
    if not df:
        return html.Div("Upload a file to see content.")
    df = pd.DataFrame.from_dict(df)
    if TIMESTAMP in df.columns:
        df[TIMESTAMP] = df[TIMESTAMP].str.slice(6,)
    
    if tab == 'tab1':
        charts = []
        
        for i in range(3):
            imuname = str(i+1).zfill(2)
            icol = df.columns.get_loc(imuname + "_1")
            fig = px.line(df, x=df.columns[0], 
                          y=df.columns[icol:icol+4],
                          title=f"IMU {IMUNAMES[imuname][0]}")
            charts.append(dcc.Graph(figure=fig))
        
        return html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr', 'gap': '20px'}, children=charts)
    
    elif tab == 'tab2':
        for imu in IMUNAMES:
            cname = imu + IMUELEM
            df[imu] = df.get(cname, pd.Series()).notna().astype(int)
        dfhm = df[HMCOLS]
        cscale = sorted([elem for elem in HMCOLORS.values()])
        txtscale = [elem for elem in HMCOLORS.keys()]
        figHM = go.Figure(data=go.Heatmap(
            z=dfhm.iloc[:, 1:].T.values,
            x=dfhm.iloc[:, 0],
            y=[IMUNAMES[k][0].title() for k in IMUIDS],
            colorscale=cscale, 
            colorbar=dict(title="Sample collection outcomes", tickvals=[0, 0.5], ticktext=txtscale))
        )
        figHM.update_traces(showscale=False) 
        figHM.update_layout(xaxis_nticks=36, modebar={"orientation": "v"})

        # data loss
        nsamples = dfstats["total"]
        yfill = []
        yok = []
        ylabels = []
        for imu in IMUIDS:
            yfill.append(int(dfstats[imu][0]))
            yok.append(nsamples-dfstats[imu][0])
            ylabels.append(str(round((dfstats[imu][1])*100,2)) + "%") 

        axislabels = [IMUNAMES[k][0].title() for k in IMUIDS]
        figBC = go.Figure(data=[
                go.Bar(name='Missing samples', x=yfill, y=axislabels, text=ylabels, textposition="auto", marker_color=HMCOLORS["missing"][1], orientation='h'),
                go.Bar(name='Collected samples', x=yok, y=axislabels, marker_color=HMCOLORS["collected"][1], orientation='h')
            ])
        figBC.update_layout(barmode='stack', showlegend=False, modebar={"orientation": "v"})

        return html.Div([
            html.Div([
             html.H2("Samples' Acquisition Analysis"),
            ]),
            dbc.Row([
                dbc.Col(html.Div(generate_stats(dfstats), style={"padding": "20px"}), width=9),
                dbc.Col(html.Div(generate_sample_legenda(), style={"padding": "20px"}), width=3)
            ]),
            html.Div([
             html.H4("Details"),
            ]),
            dcc.Graph(figure=figHM),
            dcc.Graph(figure=figBC)            
        ])
    
    elif tab == 'tab3':
        return html.Div([
            html.Button("Run Analysis", id="run-analysis"),
            html.Div(id="analysis-output")
        ])


def generate_stats(dstats):
    nticks = dstats["total"]
    return html.Div([
        html.P("Number of collected samples per event (" + str(nticks) + " total events)"),
        html.Div([
            html.Span("From all IMUs", className="boxlegenda"),
            html.Div(className="boxcollected"),
            html.Div(className="boxcollected"),
            html.Div(className="boxcollected"),
            html.Span(dstats["full"], className="boxnumber"),
            html.Span(str(round((dstats["full"]*100)/nticks,2)) + "%", className="boxnumber")
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div([
            html.Span("From 2 IMUs out of 3", className="boxlegenda"),
            html.Div(className="boxcollected"),
            html.Div(className="boxcollected"),
            html.Div(className="boxmissing"),
            html.Span(dstats["stats"][1], className="boxnumber"),
            html.Span(str(round((dstats["stats"][1]*100)/nticks,2)) + "%", className="boxnumber")
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div([
            html.Span("From 1 IMU out of 3", className="boxlegenda"),
            html.Div(className="boxcollected"),
            html.Div(className="boxmissing"),
            html.Div(className="boxmissing"),
            html.Span(dstats["stats"][2], className="boxnumber"),
            html.Span(str(round((dstats["stats"][2]*100)/nticks,2)) + "%", className="boxnumber")
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div([
            html.Span("From 0 IMU", className="boxlegenda"),
            html.Div(className="boxmissing"),
            html.Div(className="boxmissing"),
            html.Div(className="boxmissing"),
            html.Span(str(dstats["empty"]).rjust(4), className="boxnumber"),
            html.Span(str(round((dstats["empty"]*100)/nticks,2)) + "%", className="boxnumber")
        ], style={"display": "flex", "alignItems": "center"}),
    ])

def generate_sample_legenda():
    return html.Div([
            html.P("Colors:"),
            html.Div([
                html.Div(style={
                    "width": "15px",
                    "height": "15px",
                    "backgroundColor": HMCOLORS["collected"][1],
                    "display": "inline-block",
                    "marginRight": "5px"  # Space between the square and text
                }),
                html.Span("Collected samples")
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div([
                html.Div(style={
                    "width": "15px",
                    "height": "15px",
                    "backgroundColor": HMCOLORS["missing"][1],
                    "display": "inline-block",
                    "marginRight": "5px"  # Space between the square and text
                }),
                html.Span("Missing samples")
            ], style={"display": "flex", "alignItems": "center"}),
        ])


@app.callback(
    Output("analysis-output", "children"),
    Input("run-analysis", "n_clicks"),
    prevent_initial_call=True
)
def run_analysis(n_clicks):
    return html.Div("Analysis completed!")

if __name__ == '__main__':
    app.run_server(debug=True)
