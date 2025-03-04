import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px
import io
import base64
import time

from imu.align import convertlogs, align

IMUNAMES = {"01": ["thorax", "tho", "t"], "02": ["abdomen", "abd", "a"], "03": ["reference", "ref", "r"]}
HMCOLORS = [[0, "#fdfefe"], [1, "#1e8449"]]  # Green/White Heatmap

# Initialize Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Respiratory Analysis"

# Layout
app.layout = html.Div(style={'display': 'flex'}, children=[
    html.Div(style={'width': '200px', 'padding': '20px', 'borderLeft': '1px solid #ccc'}, children=[
        dcc.Upload(
            id='upload-data',
            children=html.Div([html.Button('Select Log File')]),
            multiple=False
        ),
        html.Div(id='file-info', style={'marginTop': '10px'})
    ]),
    html.Div(style={'flex': '1', 'padding': '20px'}, children=[
        dcc.Loading(id="loading-spinner", type="circle", children=[
            dcc.Tabs(id="tabs", value='tab1', children=[
                dcc.Tab(label='File Info', value='tab1'),
                dcc.Tab(label='Data Acquisition', value='tab2'),
                dcc.Tab(label='Data Acquisition - HM', value='tab2b'),
                dcc.Tab(label='Data Analysis', value='tab3')
            ]),
            html.Div(id='tabs-content', style={'marginTop': '20px'})
        ])
    ]),
    dcc.Store(id='aligned-df', data={})
])

def parse_content(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif filename.endswith('.txt'):
            payloads = convertlogs(decoded.decode('utf-8'), 3)
            df, _, _, _, _ = align(payloads, 3)
        else:
            return html.Div("Unsupported file format"), None
        return html.Div([html.H5(filename)]), df.to_dict('records')
    except Exception as e:
        return html.Div(f"Error processing file: {str(e)}"), None

@app.callback(
    [Output('tabs-content', 'children'), 
     Output('file-info', 'children'),
     Output('aligned-df', 'data')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')]
)
def update_output(contents, filename):
    if filename is None:
        return html.Div("Upload a file to get started."), "No file uploaded", {}
    if contents is None:
        return html.Div("Selected file, but no content loaded."), "No content uploaded", {}
    
    file_info, df = parse_content(contents, filename)
    if df is None:
        return file_info, "Error loading file", {}

    file_details = html.Div([html.P([html.B("Filename:"), f" {filename}"])])
    return html.Div(id='tab-content', children=[]), file_details, df

@app.callback(
    Output('tab-content', 'children'),
    [Input('tabs', 'value'),
     Input('aligned-df', 'data')],
    [State('upload-data', 'filename')]
)
def render_tab(tab, df, filename):
    if not df:
        return html.Div("Upload a file to see content.")
    df = pd.DataFrame.from_dict(df)
    if "TSTAMP" in df.columns:
        df["TSTAMP"] = df["TSTAMP"].str.slice(6,)
    
    if tab == 'tab1':
        return html.Div([
            html.H3("File Details"),
            html.P([html.B("Filename:"), f" {filename}"])
        ])
    
    elif tab == 'tab2':
        charts = []
        
        for i in range(3):
            imuname = str(i+1).zfill(2)
            icol = df.columns.get_loc(imuname + "_1")
            fig = px.line(df, x=df.columns[0], 
                          y=df.columns[icol:icol+4],
                          title=f"IMU {IMUNAMES[imuname][0]}")
            charts.append(dcc.Graph(figure=fig))
        
        return html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr', 'gap': '20px'}, children=charts)
    
    elif tab == 'tab2b':
        df["01"] = df.get("01_1", pd.Series()).notna().astype(int)
        df["02"] = df.get("02_1", pd.Series()).notna().astype(int)
        df["03"] = df.get("03_1", pd.Series()).notna().astype(int)
        dfhm = df[["TSTAMP", "01", "02", "03"]]


        fig = go.Figure(data=go.Heatmap(
            z=dfhm.iloc[:, 1:].T.values,
#            x=dfhm.index,
            x=dfhm.iloc[:, 0],
            y=[IMUNAMES[k][0].title() for k in ["01", "02", "03"]],
            colorscale=HMCOLORS,
            colorbar=dict(title="Collected sample", tickvals=[0, 0.5], ticktext=["Missing", "OK"]))
        )
        fig.update_traces(showscale=False) 
        fig.update_layout(title_text='Samples Acquisition Map', xaxis_nticks=36)
        return html.Div([
            dcc.Graph(figure=fig),
            html.Div([
                html.P("Collected", style={'backgroundColor': '#1e8449', 'color': 'white', 'padding': '5px', 'borderRadius': '5px', 'display': 'inline-block'}),
                html.P(" "),
                html.P("Missing", style={'backgroundColor': '#fdfefe', 'color': 'black', 'padding': '6px', 'border': '1px solid black', 'borderRadius': '5px', 'display': 'inline-block'})
            ])
        ])
    
    elif tab == 'tab3':
        return html.Div([
            html.Button("Run Analysis", id="run-analysis"),
            html.Div(id="analysis-output")
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
