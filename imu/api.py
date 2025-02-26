from datetime import datetime, time, timedelta
import pandas as pd
import numpy as np
import pathlib
import sys
import json

PATH = pathlib.Path(__name__).parent
DATA_PATH = PATH.joinpath("data").resolve()

COLNAMES = ["IMUID", "BATTERY","CHECK","NTH","1","2","3","4","TSTAMP"]
COLNAMESMIN = ["IMUID", "BATTERY","NTH","1","2","3","4","TSTAMP"]
COLHEX = ["IMUID", "BATTERY","CHECK","NTH","1","2","3","4"]
COLSIG = ["1","2","3","4"]
COLDATA = ["NTH","1","2","3","4","TSTAMP"]
MISSING = "[FF]"
IMUDATA_COL = ["BATTERY","1","2","3","4"]
IMUDATA_LEN = len(IMUDATA_COL)
#read from json in the future
#let user associate from the UI in the future 
IMUREF = "IMU3"
IMUNAMES = {"01": "thorax", "02": "abdomen", "03": "reference"}
READINGNAMES = {"1": "q1", "2": "q2", "3": "q3", "4": "q4"}
BATTERY_LAB = "BAT"
NSIG4IMU = 4
NBITS = 8
RESETCOUNTER = pow(2,NBITS)
SAMPLES4SEC = 10 #samples per second 

ELAB_FILE = DATA_PATH.joinpath("log.csv")
IMUFILES = ["imu1.csv", "imu2.csv", "imu3.csv"]
#IMUFILES = ["s03_1.csv", "s03_2.csv", "s03_3.csv"]

PLOTCOLS = ["TSTAMP", "COUNTER"]
SEP = "_"

def loaddata_convert(srcfiles):
    datasamples = {
        "IMU1": pd.read_csv(
            DATA_PATH.joinpath(srcfiles[0])),
        "IMU2": pd.read_csv(
            DATA_PATH.joinpath(srcfiles[1])),
        "IMU3": pd.read_csv(
            DATA_PATH.joinpath(srcfiles[2]))
    }
    dataready = {}
    imuids = []
    for key in datasamples:
        df = datasamples[key]
        df.columns = COLNAMES
        imuids.append(convert(df.iloc[0,0]))
        #drop empty
        df = df[df.CHECK != MISSING]
        df = df[COLNAMESMIN]
        for col in range(0,3):
            df.iloc[:, col] = df.iloc[:, col].apply(lambda x: convert(x))
        for col in COLSIG:
            df[col] = df[col].apply(lambda x: quatconvert(convert(x)))
        #df.apply(lambda x: quatconvert(convert(x)) if x.name in COLSIG else x)
        df["TSTAMP"] = pd.to_datetime(df["TSTAMP"],format="%d:%m:%H:%M:%S:%f").dt.time
        dataready[key] = df
    return dataready, imuids

def colnamesplotdata(imuids):
    lnames = []
    lnames.extend(PLOTCOLS)
    for id in imuids:
        lnames.extend(colnameimudata(id))
    return lnames

def colnameimudata(id):
    coln = []
    coln.append(str(id).zfill(2) + SEP + BATTERY_LAB)
    for i in range(0,NSIG4IMU):
        coln.append(str(id).zfill(2) + SEP + str(i+1))
    return coln

#int from [hex]
def convert(s):
    ss = str(s)
    return int(ss[1:3],16)

def quatconvert(x):
    if x > 127 and x != np.nan:
        x -= 256
    x /= 127
    return x

def get_imu_data(start, deltatime):
    """
    Query imu data starting from a certain time stamp 
    and collecting a certain amount of data corresponding 
    to some seconds
    :params start: start time
    :params deltatime: in seconds, such that deltatime * SAMPLES4SEC < RESETCOUNTER
    :returns: pandas dataframe object
    """
    datain, imus = loaddata_convert(IMUFILES)
#    print(datain)
    dfref = datain[IMUREF]
    minTS = dfref[(dfref.TSTAMP >= start)]["TSTAMP"].min()
    ## POLICY
    # + 2 for tolerance w.r.t. missing data
    dt = datetime.combine(datetime.today(), minTS) + timedelta(seconds=deltatime+2)
    maxTS = dt.time()
    # collect data of interest in the specified window
    firstimu = list(datain.keys())[0]
    dftmp = datain[firstimu]
    dftmp = dftmp[(dftmp.TSTAMP >= minTS) & (dftmp.TSTAMP <= maxTS)]
    for imu in list(datain.keys())[1:]:
        dfimu = datain[imu]
        dftmp = pd.concat([dftmp, dfimu[(dfimu.TSTAMP >= minTS) & (dfimu.TSTAMP <= maxTS)]], ignore_index=True)
    minCounter = dfref.loc[dfref.TSTAMP >= start,"NTH"].iloc[0]
    nsamples = deltatime * SAMPLES4SEC
    selnth = [x % RESETCOUNTER for x in range(minCounter, minCounter+nsamples)]
    #selorder = list(range(nsamples))
    #d = dict(zip(selnth, selorder))
    #dftmp["COUNTER"] = dftmp["NTH"].map(d)
    #dftmp = dftmp.dropna()
    #dftmp["COUNTER"].astype(int)
    #print(dftmp)
    # create resulting df
    colnames = colnamesplotdata(imus)
    df = pd.DataFrame(columns=colnames)
    emptysample = [np.nan]*len(colnames)
    prevsample = [np.nan]*IMUDATA_LEN*len(imus)
    nfill = 0
    nempty = 0
    for it in selnth:
        # get the info from the three imus
        selrows = dftmp[dftmp.NTH == it]
        row = [selrows["TSTAMP"].min(), it]
        nok = 0
        for imuid in imus:
            valueimu = selrows[selrows.IMUID == imuid]
            if len(valueimu) > 0:
                imudata = list(valueimu[IMUDATA_COL].values[0])
                prevsample[0+(imuid-1)*IMUDATA_LEN:0+imuid*IMUDATA_LEN] = imudata
                nok += 1
            else:
                ## POLICY
                # if one or more are missing, fill with previous
                imudata = prevsample[0+(imuid-1)*IMUDATA_LEN:0+imuid*IMUDATA_LEN]
                nfill += 1
            row.extend(imudata)
        ## POLICY
        # if all are missing, use NAN
        if nok == 0:
            row = emptysample
            nempty += 1
            nfill -= 3
        # store in new df
        df.loc[len(df)] = row
    return df, minCounter, minCounter+nsamples, nfill, nempty

#dt = datetime.now() - timedelta(seconds=10)
#df, fromTH, toTH, nmiss, nempty = get_imu_data(dt.time(), 5)
#print(df, "\n", fromTH, toTH, nmiss, nempty)