import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
#from dash_bootstrap_templates import load_figure_template
import pandas as pd
import plotly.express as px
import io
import base64
import time
import datetime
import json

from imu.align import convertlogs, align

IMUNAMES = {"01": ["thorax", "tho", "t"], "02" : ["abdomen", "abd", "a"], "03": ["reference", "ref", "r"]}
HMCOLORS = [[0, " #fdfefe"],[1," #1e8449"]] #red #d82027

# Initialize Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Respiratory Analysis"

#load_figure_template("materia")

# Layout
app.layout = html.Div(style={'display': 'flex'}, children=[
    html.Div(style={'width': '200px', 'padding': '20px', 'borderLeft': '1px solid #ccc'}, children=[
        dcc.Upload(
            id='upload-data',
            children=html.Button('Select Log File'),
            multiple=False
        ),
        html.Div(id='file-info', style={'marginTop': '10px'})
    ]),
    html.Div(style={'flex': '1', 'padding': '20px'}, children=[
        dcc.Tabs(id="tabs", value='tab1', children=[
            dcc.Tab(label='File Info', value='tab1'),
            dcc.Tab(label='Data Acquisition', value='tab2'),
            dcc.Tab(label='Data Acquisition - HM', value='tab2b'),
            dcc.Tab(label='Data Acquisition', value='tab2c'),
            dcc.Tab(label='Data Analysis', value='tab3')
        ]),
        html.Div(id='tabs-content', style={'marginTop': '20px'})
    ]),
    # dcc.Store stores the intermediate value
    dcc.Store(id='aligned-df')
    # ,
    # dbc.Spinner(
    #     [
    #         dcc.Store(id="store"),
    #         html.Div(id="tab-content", className="p-4"),
    #     ],
    #     delay_show=100,
    # )    
])

def parse_content(contents, filename, last_modified):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif filename.endswith('.txt'):
            payloads = convertlogs(decoded.decode('utf-8'), 3)
            df, nfill, nempty, nall, time_diff = align(payloads, 3)
        else:
            return html.Div("Unsupported file format"), None
        
        # # Create an HTML table preview
        # table = html.Table([
        #     html.Thead(html.Tr([html.Th(col) for col in df.columns])),
        #     html.Tbody([
        #         html.Tr([html.Td(df.iloc[i][col]) for col in df.columns]) for i in range(min(len(df), 5))
        #     ])
        # ])
        
        return html.Div([
            html.H5(filename)#,
            #table
        ]), df
    except Exception as e:
        return html.Div(f"Error processing file: {str(e)}"), None


# @app.callback(
#     Output('aligned-df', 'data'), 
#     Input('upload-data', 'contents'),
#     State('upload-data', 'filename')
# )
# def clean_data(contents, filename):
#     df = parsedata(contents, filename)
#     # more generally, this line would be
#     # json.dumps(cleaned_df)
#     return json.dumps(df)

@app.callback(
    [Output('tabs-content', 'children'), 
     Output('file-info', 'children')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename'),
     State('upload-data', 'last_modified')]
)
def update_output(contents, filename, last_modified):
    print("update_output @" + time.strftime("%H:%M:%S", time.localtime()))
    if filename is None:
        return html.Div("Upload a file to get started."), "No file uploaded"
    file_info, df = parse_content(contents, filename, last_modified)
    if df is None:
        return file_info, "Error loading file"
    
    file_details = html.Div([
        html.P([html.B("Filename:"), f" {filename}"])
    ])
    
    return html.Div(id='tab-content', children=[]), file_details

@app.callback(
    Output('tab-content', 'children'),
    [Input('tabs', 'value')],
    [State('upload-data', 'contents'), 
    State('upload-data', 'filename'),
    State('upload-data', 'last_updated')]
)
def render_tab(tab, contents, filename, last_updated):
    print("render_tab @" + time.strftime("%H:%M:%S", time.localtime()))
    if contents is None:
        return html.Div("Upload a file to see content.")
    _, df = parse_content(contents, filename, last_updated)
    if df is None and filename is not None:
        return html.Div("Error loading data.")
    
    if tab == 'tab1':
        return html.Div([
            html.H3("File Details"),
            html.P([html.B("Filename:"), f" {filename}"]),
            #datetime.datetime.fromtimestamp(last_updated).strftime("%d %m % %Y at %H:%M:%S")
        ])
    
    elif tab == 'tab2':
        charts = []
        num_charts = 3  # Ensure we have enough columns
        for i in range(0, num_charts):
            fig = px.line(df, 
                x=df.columns[0], 
                y=df.columns[4+5*i:8+5*i], 
                title="IMU " + IMUNAMES[str(i+1).zfill(2)][0]
            )
            charts.append(dcc.Graph(figure=fig))
        
        return html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr', 'gap': '20px'}, children=charts)

    elif tab == 'tab2b':
        charts = []
        # num_charts = 3  # Ensure we have enough columns
        # for i in range(0, num_charts):
        #     fig = go.Figure()
        #     for t in range(0, 4):
        #         fig.add_trace(go.Scatter(
        #             x=df[df.columns[0]], 
        #             y=df[df.columns[4+5*i+t]], 
        #             mode='lines', 
        #             name="q" + str(t+1)))
        #     fig.update_layout(title="IMU " + IMUNAMES[str(i+1).zfill(2)])
        #     charts.append(dcc.Graph(figure=fig))
        
        df["01"] = df["01_1"].notna().astype(int)
        df["02"] = df["02_1"].notna().astype(int)
        df["03"] = df["03_1"].notna().astype(int)
        dfhm = df[["TSTAMP","01","02","03"]]
#        fig = px.imshow(dfhm, x=dfhm.columns, y=dfhm.index)

        fig = go.Figure(data=go.Heatmap(
                z=dfhm.iloc[:,1:].T.values,
                x=dfhm.index, #[x[6:] for x in dfhm.iloc[:,1].values], # dfhm.iloc[:,0].str()[6:].values,
                y=[x[0].title() for x in IMUNAMES.values()],
                colorscale=HMCOLORS,
                colorbar=dict(title="Collected sample", tickvals=[0,0.5], ticktext=["Missing", "OK"])))

        fig.update_layout(
            title=dict(text='Data Acquisition Information'),
            xaxis_nticks=36)
        charts.append(dcc.Graph(figure=fig))
        return html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr', 'gap': '20px'}, children=charts)

    elif tab == 'tab2c':
        charts = []
        num_charts = 3  # Ensure we have enough columns
        fig = go.Figure()
        for i in range(0, num_charts):
            for t in range(0, 4):
                fig.add_trace(go.Scatter(
                    x=df[df.columns[0]], 
                    y=df[df.columns[4+5*i+t]] + 3*i, 
                    mode='lines', 
                    name="q" + str(t+1) + "_" + IMUNAMES[str(i+1).zfill(2)][2]))
        fig.update_layout(title="IMU")
        charts.append(dcc.Graph(figure=fig))
        
        return html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr', 'gap': '20px'}, children=charts)
    
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