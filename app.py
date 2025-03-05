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
HMCOLORS = {"collected": [1, "#1e8449"], "missing": [0, "#f5f5f5"]}  # Green/White Heatmap
TIMESTAMP = "TSTAMP"
IMUIDS = [x for x in IMUNAMES.keys()]
HMCOLS = [TIMESTAMP]
HMCOLS.extend(IMUIDS)
IMUELEM = "_1"


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
            df, _, _, _, _ = align(payloads, 3)
        else:
            return html.Div("Unsupported file format"), None, None
        ## a few more stats
        nsamples = len(df)
        dataloss = {}
        cnames = []
        for imu in IMUIDS:
            cname = imu + IMUELEM
            cnames.append(cname)
            num_miss = df[cname].isna().sum()
            num_tot = df[cname].notna().sum() + num_miss
            dataloss[imu] = [num_miss, num_miss/num_tot]
        nmiss = df[cnames].isna().all(axis=1).sum()
        dataloss["total"] = num_tot
        dataloss["empty"] = nmiss
        return html.Div([html.H5(filename)]), df.to_dict('records'), dataloss
    except Exception as e:
        return html.Div(f"Error processing file: {str(e)}"), None, None

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
        return html.Div("Upload a file to get started."), "No file uploaded", {}, {}
    if contents is None:
        return html.Div("Selected file, but no content loaded."), "No content uploaded", {}, {}
    
    file_info, df, dloss = parse_content(contents, filename)
    if df is None:
        return file_info, "Error loading file", {}, {}

    file_details = html.Div([html.P([html.B("Filename:"), f" {filename}"])])
    return html.Div(id='tab-content', children=[]), file_details, df, dloss

@app.callback(
    Output('tab-content', 'children'),
    [Input('tabs', 'value'),
     Input('aligned-df', 'data'),
     Input('quality-df', 'data')],
    [State('upload-data', 'filename')]
)
def render_tab(tab, df, dfloss, filename):
    if not df:
        return html.Div("Upload a file to see content.")
    df = pd.DataFrame.from_dict(df)
    if "TSTAMP" in df.columns:
        df["TSTAMP"] = df["TSTAMP"].str.slice(6,)
    
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
        figHM.update_layout(xaxis_nticks=36)

        # data loss
        nsamples = dfloss["total"]
        yfill = []
        yok = []
        ylabels = []
        for imu in IMUIDS:
            yfill.append(int(dfloss[imu][0]))
            yok.append(nsamples-dfloss[imu][0])
            ylabels.append(str(round((dfloss[imu][1])*100,2)) + "%") 

        axislabels = [IMUNAMES[k][0].title() for k in IMUIDS]
        figBC = go.Figure(data=[
                go.Bar(name='Missing samples', x=yfill, y=axislabels, text=ylabels, textposition="auto", marker_color=HMCOLORS["missing"][1], orientation='h'),
                go.Bar(name='Collected samples', x=yok, y=axislabels, marker_color=HMCOLORS["collected"][1], orientation='h')
            ])
        figBC.update_layout(barmode='stack')

        return html.Div([
            html.Div([
             html.H2("Sample Acquisition Analysis"),
            ]),
            dcc.Graph(figure=figHM),
            # html.Div([
            #     html.P("Collected", style={'backgroundColor': HMCOLORS["collected"][1], 'color': 'white', 'padding': '5px', 'borderRadius': '5px', 'display': 'inline-block'}),
            #     html.P(" "),
            #     html.P("Missing", style={'backgroundColor': HMCOLORS["missing"][1], 'color': 'black', 'padding': '6px', 'border': '1px solid black', 'borderRadius': '5px', 'display': 'inline-block'})
            # ]),
            dcc.Graph(figure=figBC)            
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
