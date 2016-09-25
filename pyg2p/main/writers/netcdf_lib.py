# -------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      burekpe
#
# Created:     21/02/2014
# Copyright:   (c) burekpe 2014
# Licence:     <your licence>
# -------------------------------------------------------------------------------


from pcraster import *
from pcraster.framework import DynamicModel, pcr2numpy, numpy2pcr, DynamicFramework

import numpy as np
from netCDF4 import Dataset
from netCDF4 import num2date, date2num

import time as timex
import datetime as date


class RunoffModel(DynamicModel):
    def __init__(self, cloneMap):
        DynamicModel.__init__(self)
        setclone(cloneMap)
        self.i = 0

    def initial(self):
        # coverage of locations for the whole area
        self.j = 0

    def dynamic(self):
        global value

        if write:
            # calculate and report maps at each timestep
            mapp = self.readmap(inputfile)
            mappnp = pcr2numpy(mapp, np.nan)

            t0 = startdate + date.timedelta(days=self.i)
            t = date2num(t0, time.units, calendar='proleptic_gregorian')
            t2.append(t)

            value[self.i, :, :] = mappnp

            self.i += 1
        else:
            nf1 = Dataset(netcdf_output, 'r')
            value = nf1.variables.items()[-1][0]  # get the last variable name
            mappnp = nf1.variables[value][self.i, :, :]

            mappnp[np.isnan(mappnp)] = -9999
            # reverse because the strange meteorological guys turned the world upside down
            mapp = numpy2pcr(Scalar, mappnp, -9999)

            self.i += 1
            nf1.close()
            self.report(mapp, pcrasterout)


# ++++++++++++++++++++++ USER Input  ++++++++++++++++++++++++++++++++++++++++++++
write = True

startdate = date.datetime(1995, 6, 8, 0, 0, 0)
steps = 7314

prefix = "srp"
value_unit = 'mm'
value_long_name = 'sro-precip_HTessel_REF'
value_standard_name = 'srp'
source = 'EEMWF REFORECAST'
reference = 'ECMWF'

xcoord = 'lon'
ycoord = 'lat'
digit = 2

sourceDir = "W:/hirpafe/Reforecast2016/GRIB_DATA/ungrib_ro/concatenated/"
# sourceDir="W:/hirpafe/Reforecast2016/GRIB_DATA/ungrib_ro/concatenated/"
netcdf_output = "W:/hirpafe/Calibration/GloRef_Cal/Forcing/" + prefix + ".nc"
mask = "F:/Calibration/Global_Cal/data/maps/areaOrigin.map"

# ++++++++++++++++++++++++++   END USER INPUT +++++++++++++++++++++++++++++++++++

print mask
area = readmap(mask)
areanp = pcr2numpy(area, np.nan)
print "areashape", areanp.shape
inputfile = sourceDir + prefix
myModel = RunoffModel(mask)
dynModelFw = DynamicFramework(myModel, lastTimeStep=steps, firstTimestep=1)

if write:

    nf1 = Dataset(netcdf_output, 'w', format='NETCDF4_CLASSIC')
    # general Attributes
    nf1.history = 'Created ' + timex.ctime(timex.time())
    nf1.Conventions = 'CF-1.6'
    nf1.Source_Software = 'Python netCDF4'
    nf1.source = source
    nf1.reference = reference

    # Dimension
    lon = nf1.createDimension(xcoord, areanp.shape[1])  # x 1000
    lat = nf1.createDimension(ycoord, areanp.shape[0])  # x 950
    time = nf1.createDimension('time', None)

    # Variables
    longitude = nf1.createVariable(xcoord, 'f8', (xcoord))
    latitude = nf1.createVariable(ycoord, 'f8', (ycoord))

    longitude.standard_name = 'longitude'
    longitude.long_name = 'longitude coordinate'
    longitude.units = 'degrees_east'

    latitude.standard_name = 'latitude'
    latitude.long_name = 'latitude coordinate'
    latitude.units = 'degrees_north'

    time = nf1.createVariable('time', 'f8', ('time'))
    time.standard_name = 'time'
    time.units = 'days since 1979-01-01 00:00:00.0'
    time.calendar = 'proleptic_gregorian'

    value = nf1.createVariable(prefix, 'f4', ('time', ycoord, xcoord), zlib=True, least_significant_digit=digit)

    value.standard_name = value_standard_name
    value.long_name = value_long_name
    value.units = value_unit

    value.esri_pe_string = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]]'
    lats = np.arange(89.95, -60.0,
                     -0.1)  # y  world new -> middle of pixel so 90 -0.05 -> -60 is excluded so last one is -59.95
    lons = np.arange(-179.95, 180.0, 0.1)  # x  world

    print lats.shape, lons.shape
    latitude[:] = lats
    longitude[:] = lons

    t2 = []
    print "1"
    dynModelFw.run()
    time[:] = t2

    nf1.close()
    # ---------------------------------------
    print "ready write"

else:
    print "read"
    # nf1 = Dataset(netcdf_output, 'r', format='NETCDF4')
    print "1"
    # print nf1.variables
    dynModelFw.run()
    # nf1.close()
