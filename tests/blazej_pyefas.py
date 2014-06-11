import pyg2p
import os
def toMap(self, param, outdir, tstart, tend, dt, epsmember=None, fmap=1, ext=None):

        for gribFile in self.filenames:

            if param == 't':
                dt_grib = 24
                ext = dt_grib / dt
            else:
                dt_grib = dt

            # Grib2pcraster goes back in time when accumulating or averaging. This means for example that if you require a cumulativ
            # timestep 1 to 24 we shall pass the arguments -t 24 -s 24 where -s is the starting timestep.
            # the next 2 if conditions changes -s and -e according to -t
            tstart_grib = tstart + dt_grib - 1
            tend_grib = tend
            if (tend < tstart_grib):
                tend_grib = tstart_grib

            cmdfile = '%s_%s%02d.xml' % (self.name, param, dt_grib)
            cmdpath = PYG2PDIR + '/execution_templates/' + cmdfile
            # command = PYG2PDIR + '/pyg2p.py'
            command = pyg2p.command()
            command.with_cmdpath(cmdpath).with_inputfile(gribFile)\
                .with_outdir(os.path.normpath(outdir)+os.sep)\
                .with_tstart(tstart_grib).with_tend(tend_grib)

            #you can also init the command with a string:
            #command = pyg2p.command('-l ERROR -c /pyg2p_git/execution_templates_devel/eue_t24.xml -i /dataset/test_2013330702/EpsN320-2013063000.grb -o /dataset/testdiffmaps/eueT24 -m 10')

            if epsmember is not None:
                command.with_eps(epsmember)
            if fmap is not None:
                command.with_fmap(fmap)
            if ext is not None:
                command.with_ext(ext)
            print str(command)
            executed = pyg2p.run_command(command)
        return executed
