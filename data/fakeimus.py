from datetime import datetime, time, timedelta
import pandas as pd
import numpy as np
import random
import pathlib
import sys
import time

PATH = pathlib.Path(__name__).parent
DATA_PATH = PATH.joinpath(".").resolve()
COLNAMES = ["IMUID", "BATTERY","CHECK","NTH","1","2","3","4","TSTAMP"]
COLNAMESMIN = ["IMUID", "BATTERY","NTH","1","2","3","4","TSTAMP"]
COLHEX = ["IMUID", "BATTERY","CHECK","NTH","1","2","3","4"]
COLSIG = ["1","2","3","4"]
COLDATA = ["NTH","1","2","3","4","TSTAMP"]
MISSING = "FF"
DELTASAMESIG = 800
EMPTYDATA = ["[00]","[FF]","[00]","[00]","[00]","[00]","[00]"]
DUMPFREQ = 4
NBITS = 8
RESETCOUNTER = pow(2,NBITS)

def loaddata(srcfiles):
    datasamples = {
        "IMU1": pd.read_csv(
            DATA_PATH.joinpath(srcfiles[0])),
        "IMU2": pd.read_csv(
            DATA_PATH.joinpath(srcfiles[1])),
        "IMU3": pd.read_csv(
            DATA_PATH.joinpath(srcfiles[2]))
    }
    imuids = []
    for key in datasamples:
        df = datasamples[key]
        imuids.append(df.iloc[0,0])
        df.columns = COLNAMES
        df["TSTAMP"] = pd.to_datetime(df["TSTAMP"],format="%d:%m:%H:%M:%S:%f").dt.time
    return datasamples, imuids

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
    for key in datasamples:
        df = datasamples[key]
        df.columns = COLNAMES
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
    return dataready

#int from [hex]
def convert(s):
    ss = str(s)
    return int(ss[1:3],16)

def quatconvert(x):
    if x > 127 and x != np.nan:
        x -= 256
    x /= 127
    return x

def appendreadingstofile(fnames, nreads, dataout):
	fps = []
	for name in fnames:
		fout = open(DATA_PATH.joinpath(name), "a")
		fps.append(fout)
	for datalist in dataout:
		for index, imudata in enumerate(datalist):
			strout = ",".join(imudata)
			fps[index].write(strout+"\n")
	for fp in fps:
		fp.close()
#	except:
#		print("Error somewhere :(")


#main 

## sample data
# fnamesin = ["s03_1.csv", "s03_2.csv", "s03_3.csv"]
fnamesin = sys.argv[1:4]
# fnamesout = ["imu_1.csv", "imu_2.csv", "imu_3.csv"]
fnamesout = sys.argv[4:8]

datain, imus = loaddata(fnamesin)
#minimum internal counter from IMUS
minCounters = []
maxCounters = []
for imu in datain.values():
	minCounters.append(imu["NTH"].min())
	maxCounters.append(imu["NTH"].max())
minTick = min(minCounters)
maxTick = max(maxCounters)

fakedata = []

#counter = random.randint(minTick, maxTick)
counter = random.randint(int(minTick[1:3], 16), int(maxTick[1:3],16))
# the first reading is from IMU1 .. arbitrary
counter16 = hex(counter % RESETCOUNTER).upper()[2:]
scounter16 = "[" + counter16 + "]"
# get first value from IMU1
df = datain["IMU1"]
imuid = df.iloc[0,0]
values = df[df.NTH == scounter16][COLDATA]
timedev = values.iloc[0]["TSTAMP"]
dt = datetime.combine(datetime.today(), timedev)
dtbefore = (dt - timedelta(milliseconds=DELTASAMESIG)).time()
dtafter = (dt + timedelta(milliseconds=DELTASAMESIG)).time()
print("starting at " + scounter16 + " with " + str(df.loc[0, COLSIG].tolist()))
while True:
	counter16 = hex(counter).upper()[2:]
	counter16 = str(counter16).zfill(2)
	scounter16 = "[" + counter16 + "]"
	sigvalues = []
	# get first value from IMU1
	for imu in datain.keys():
		dfx = datain[imu]
		values = dfx[(dfx.NTH == scounter16) & (dfx.TSTAMP >= dtbefore) & (dfx.TSTAMP <= dtafter)]
		if len(values) == 1:
			realdata = values.iloc[0].tolist()
			realdatanotime = realdata[:-1]
			print(scounter16 + " IN " + imu, dtbefore, dtafter)
			#adjust time frame
			timedev = values.iloc[0]["TSTAMP"]
			dt = datetime.combine(datetime.today(), timedev)
			dtbefore = (dt - timedelta(milliseconds=DELTASAMESIG)).time()
			dtafter = (dt + timedelta(milliseconds=DELTASAMESIG)).time()
		else:
			realdatanotime = [imuid]
			realdatanotime.extend(EMPTYDATA)
			print(scounter16 + " NOT IN " + imu, dtbefore, dtafter)
		fakesignals = realdatanotime
		ctime = datetime.now().strftime("%d:%m:%H:%M:%S:%f")[:-3]
		fakesignals.append(ctime)
#		print(fakesignals)
		sigvalues.append(fakesignals)
	fakedata.append(sigvalues)
	#append to files
	if counter % DUMPFREQ == 0:
		appendreadingstofile(fnamesout, DUMPFREQ, fakedata[-DUMPFREQ:])
	counter += 1
	counter = counter % RESETCOUNTER

	time.sleep(1)
