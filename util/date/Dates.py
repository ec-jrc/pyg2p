
__author__="nappodo"
__date__ ="$Jul 9, 2009 11:35:23 AM$"

import datetime as dt
import time as tt


def datetimeFromString(dateString, fmt):
    try:
        r = dt.datetime.strptime(dateString,fmt)
        return r
    except ValueError, err:
        raise err

def datetimeToString(dateTime, fmt='%Y-%m-%d'):
    """
    Convert a datetime object to its string representation.
    Default Format is %Y-%m-%d
    """
    try:
        return dateTime.strftime(fmt)
    except ValueError, err:
        raise err

def fromDatetime2Date(datetimePar):
    """

    """
    return dt.date(datetimePar.year, datetimePar.month, datetimePar.day)

def today():
    return dt.date.today()

def yesterday():
    return dt.date.today() - dt.timedelta(1)
def beforeYesterday():
    return dt.date.today() - dt.timedelta(2)

def yesterdayAt6AM():
    yday = yesterday()
    return dt.datetime(yday.year,yday.month,yday.day,6,0)

def yesterdayAt0AM():
    yday = yesterday()
    return dt.datetime(yday.year,yday.month,yday.day,0,0)

def beforeYesterdayAt0AM():
    byday = beforeYesterday()
    return dt.datetime(byday.year,byday.month,byday.day,0,0)

def now():
    return dt.datetime.today()

def currentTimestamp():
    return tt.time()

def getNowStr(fmt='%Y-%m-%d %H:%M'):
    return dt.datetime.strftime(dt.datetime.now(),fmt)

def getTimedelta(days=0,hours=0,minutes=0,seconds=0):
    return dt.timedelta(days=days,hours=hours,minutes=minutes,seconds=seconds)
 


