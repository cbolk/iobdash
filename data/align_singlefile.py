import pandas as pd
import numpy as np
import sys
#import time
from datetime import datetime, time, timedelta

SEC_IN_MIN = 60
MIN_IN_HR = 60
SEC_IN_HR = SEC_IN_MIN * MIN_IN_HR
HR_IN_DAY = 24
TIME_FORMAT = "%H:%M:%S:%f"

COLNAMES = ["IMUID", "BATTERY","CHECK","NTH","1","2","3","4","TSTAMP"]
NFIELDS = len(COLNAMES)
DATALINE = "["
SEP = ","
SEP_LAB = "_"
DISCARD = ["[04]"]
BLANK = "FF"
BYTE_IMUID = 0
BYTE_BATTERY = 1
BYTE_CHECK = 2
BYTE_COUNTER = 3
BYTE_PAYLOAD_START = 4
BYTE_PAYLOAD_END = 7
BYTE_TIMESTAMP = 8
EMPTYDATA = ["[00]","[FF]","[00]","[00]","[00]","[00]","[00]"]
NBITS = 8
RESETCOUNTER = pow(2,NBITS)
SAMPLINGRATE = 10 #samples per imu per second

PLOTCOLS = ["TSTAMP", "COUNTER"]
IMUDATACOL = ["BATTERY","1","2","3","4"]
NUM_DATACOL = len(IMUDATACOL)
OFFSET = len(PLOTCOLS)
BATTERY_LAB = "BAT"
NSIGXIMU = 4

#int from [hex]
def convert(s):
    ss = str(s)
    return int(ss[1:3],16)

def quatconvert(x):
    if x > 127 and x != np.nan:
        x -= 256
    x /= 127
    return x

def colnamesplotdata(imuids):
    lnames = []
    lnames = PLOTCOLS
    for id in imuids:
        lnames.extend(colnameimudata(id))
    return lnames

def colnameimudata(id):
    coln = []
    coln.append(str(id).zfill(2) + SEP_LAB + BATTERY_LAB)
    for i in range(0,NSIGXIMU):
        coln.append(str(id).zfill(2) + SEP_LAB + str(i+1))
    return coln

def align(payloads, num_imus):
    imus = [x+1 for x in range(num_imus)]
    cnames = ["TSTAMP", "COUNTER"]
    for id in imus:
        cnames.extend(colnameimudata(str(id).zfill(2)))
    nFields = len(cnames)
    #print(cnames)
    #[ts, counter, battery, payload]

    readings = []
    keys = []
    for i in range(num_imus):
        keys.append(i+1)
        readings.append(payloads[i+1])
#        print(readings[i])

    firstData = []
    lenData = []
    for imuid in range(num_imus):
        imudata = readings[i]
        lenData.append(len(imudata))
        firstData.append([imudata[0][0], imudata[0][1]])
    firstData_sorted = sorted(firstData, key=lambda x: x[1])
    firstTS = firstData_sorted[0][0]
    firstTS = firstTS[6:]
    startCounter = firstData_sorted[0][1]
    counter = startCounter
    nmiss = 0
    nfill = 0
    nmisscounter = 0
#    print(firstData_sorted)
    # while you have data in one of the num_imus queues
    print("... aligning samples")
    df = pd.DataFrame(columns=cnames)
    idxs = [0]*num_imus
    ns = 0
    while idxs[0] < lenData[0] and idxs[1] < lenData[1] and idxs[2] < lenData[2]:
        row = []
        ts = []    
        counternsamp = 0
        for imui, imudata in enumerate(readings):
            rowimu = imudata[idxs[imui]]
             #[ts, counter, battery, payload]
            nth = (counter % RESETCOUNTER)
            if rowimu[1] == nth:
                ts.append(rowimu[0])
                row.extend(rowimu[2:])
                idxs[imui] += 1
                counternsamp += 1
            else:
                row.extend([np.nan]*NUM_DATACOL)
                nfill += 1
        if counternsamp >= 1:
            minTS = min(ts)
            finalrow = [minTS, nth]
            finalrow.extend(row)
        else:
            nmiss += 1
            finalrow = [np.nan]*(nFields-2)
            finalrow.insert(0, nth)
            finalrow.insert(0, 0)
        df.loc[ns] = finalrow
        counter += 1
        ns += 1
    lastTS = minTS[6:]
    start_time = datetime.strptime(firstTS, TIME_FORMAT)
    end_time = datetime.strptime(lastTS, TIME_FORMAT)
    time_diff = end_time - start_time
    return df, nfill, nmiss, ns, time_diff


def loaddataimu_convert(fnamein, num_imus):
   print("... loading data ")
   fin = open(fnamein, "r")
   txt = fin.read().strip().split("\n")

   datain = {}
   for i in range(num_imus):
       datain[i+1] = []
       
   i = 0
   nlines = len(txt)
   while i < nlines:
      if len(txt[i]) > 0:
         if txt[i][0] == DATALINE:
             break
      i += 1
   
   #line = txt[i]
   #data line, possibly the one with ID 04
   #if line[0:4] in DISCARD:
   #   i += 1      
   firstDataRow = i
   firstReading = txt[i]
   firstTS = firstReading.strip().split(SEP)[-1]
   #normal data lines
   while i < nlines:
      line = txt[i]
      line = line.replace("[", "").replace("]", "")
      items = line.split(SEP)
      # ["IMUID", "BATTERY","CHECK","NTH","1","2","3","4","TSTAMP"]
      row = []
      if items[BYTE_CHECK] != BLANK:
          imuid = int(items[BYTE_IMUID], 16)
          battery = int(items[BYTE_BATTERY], 16)
          counter = int(items[BYTE_COUNTER], 16)
          payload = []
          for bp in range(BYTE_PAYLOAD_START, BYTE_PAYLOAD_END+1):
              payload.append(quatconvert(int(items[bp], 16)))
          ts = items[BYTE_TIMESTAMP]
          row = [ts, counter, battery]
          row.extend(payload)
          if imuid in datain:
             datain[imuid].append(row)
          else:
             datain[imuid] = [row]
      i += 1

   lastTS = ts
   print("== Loaded data (" + fnamein + ") == ")
   print("> First recorded sample: " + firstTS[6:])
   print("> Last recorded sample: " + lastTS[6:])
   print("> Number of samples: " + str(i - firstDataRow))
   return datain



#main flow
if len(sys.argv) == 4:
    fnamein = sys.argv[1] #"data/S29_corsa.txt" #
    num = int(sys.argv[2]) #num_imus
    fnameout = sys.argv[3] #"data/S29_corsa.csv" #

    payloads = loaddataimu_convert(fnamein, num)
    for p in payloads:
        df = pd.DataFrame(payloads[p])
        tmpfile = fnameout.replace(".csv", "." + str(p) +  ".csv")
        df.to_csv(tmpfile, index=False)
        print("Additional file IMU #", p, ":", tmpfile)
    dfaligned, nfill, nempty, nall, time_diff = align(payloads, num)
    dataloss = []
    offset = 2
    for i in range(num):
        dataloss.append(int(dfaligned.iloc[:, OFFSET+i*NUM_DATACOL].isna().sum()))

    #dataloss = [int(dfaligned["01_1"].isna().sum()), dfaligned["02_1"].isna().sum(), dfaligned["03_1"].isna().sum()]
    total_seconds = time_diff.total_seconds()
    hours = int(total_seconds // SEC_IN_HR)
    minutes = int((total_seconds % SEC_IN_HR) // SEC_IN_MIN)
    seconds = int(total_seconds % SEC_IN_MIN)
    print("== Aligned data == ")   
    print("> Number of consecutive data samples: ", nall, f"({hours}h {minutes}m {seconds}s)")
    print("> Number of data fills (not entire missing data for counter): ", nfill, "{:.2f}%".format((nfill * 100) / (3 * nall)))
    print("> Number of empty samples (entire missing data for counter): ", nempty, "{:.2f}%".format((nempty * 100) / (3 * nall)))
    print("Saved in: ", fnameout)
    dfaligned.to_csv(fnameout)
else:
    print("usage: ", sys.argv[0], " filein _number_of_imus_ fileout")
    #print(dfaligned)