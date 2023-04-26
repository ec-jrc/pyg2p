CHANGE LOG
==========
v 3.2
-----
* New interpolation methods: bilinear interpolation on irregular grids, Delaunay triangulation, bilinear interpolation based on Delaunay triangulation (best performances on irregular and projected grids)
* Additional average computation method on Aggregator 
* NetCDF lat/lon map reading. Scale factor, offset, variable type options in NetCDF output map writing

v 3.1
-----
* **74** API is much more flexible. Check documentation on how to use pyg2p programmatically.
* **73** Intertables are saved as .gz now, to save disk space. It's possible to compress all existing intertables and use them without changes in configuration. If pyg2p doesn't find the intertable, it will try to read it with suffix .gz.


v 3.0
-----
* **72** Pruned old test suite and test runner script. Using pytest with oracle data from latest version (v 2.1).
    grib2pcraster is not used anymore
* **71** Manual is in Markdown now, available on github.com as README.md
* **70** Changed from NETCDF4_CLASSIC to NETCDF4 for netCDF outputs
* **69** Replace GRIB_API with ecCodes
* **68** Python3 version

v 2.1
-----
* **67** NETCDF4 CLASSIC format output. Enabled by command line -F netcdf
    or in execution JSON file OutMaps format attribute
* **66** INTERTABLES, GEOPOTENTIALS user folders are optional for the user.
    Need to setup in ./pyg2p/myfile.conf only for writing new intertables/geopotentials in user folders
* **65** Bug fix: Correct handling of GRIB missing values


v 2.0.1
-------
* **64** Minor fixes in API
* **63** Minor fixes in logging


v 2.0.0
-------

* **62** Added command -W to download default geopotentials and intertables from FTP.

* **61** Separated default configuration (in package) from user configuration.

* **60** pyg2p is now installed as executable script via setup.py.

* **59** Documentation in a single file, with more information on interpolation (and internals),
    grids and examples.

* **58** JSON commands configuration can contain variables in the form {var}.
    Those vars can be defined in a .conf file under ~/.pyg2p/ user folder:
    var = /path/to/my/data

* **57** Configuration is in JSON format and placed under ~/.pyg2p/ user folder.
    Added a command line option to copy source configuration to user folder.
    The command copies json files and geopotentials.
    Dismiss XML config and convert all XML config files into JSON using --convert_to_v2 command argument.

v 1.3.5
-------

* **056** Bug Fix: Fixed wrong order in output values when no aggregation was used

* **055** Ordering happens only in one place, with beneifts on performances and memory
    Removed unused code; minor formatting


v 1.3.4
-------

* **054** Added name prefix as command line argument (overwriting XML template configuration)


v 1.3.3
-------

* **053** Bug Fix: Show help when pyg2p is launched without arguments

* **052** Added AFFS configurations and tests


v 1.3.2
-------

* **051** Added a new option to select messages based on the dataDate GRIB key. It's not possible to select a range of dates.
   For certain GRIB files, this could be used in conjunction  with the already existing dataTime option.


v 1.3.1
-------

* **050** Bug Fix:  For first time step, accumulation was not handling missing values correctly.
   Solution was to init the output array as zeros.


v 1.3
-----
* **049** Added a small API to import and use pyg2p from python scripts.


* **048** Performances improvements in scipy based interpolation methods (nearest, invdist):
        - Very fast interlookup table creation (seconds or minutes, not hours or days)
            in invdist method.
        - Interlookup table created in no time in nearest method.
        - Results are close to GRIB_API based interpolation so they are validated.

* **047** Bug fix: Corrected bug in interpolation from intertables, introduced with 1.2.8

* **046** Bug fix: Corrected bug in scipy interpolation of geopotentials, affecting temperature correction.

* **045** Test Suite now includes the possibility to execute pyg2p to compare GRIB_API and scipy interpolation results.

v 1.2.9
-------
* **044** Performances improvements:
        - adoption of numexpr in  manipulation, correction, conversion
          (instead of numpy vectorized functions obtained from lambdas)
          Improvements are extremelly evident especially in large grids processing like T3999.
        - using grib api indexes instead opened files. Boost performances in startup
            for huge input grib files.

* **043** Memory footprint is reduced of 30%/70%:
        - removed two unused collections
        - using iteritems instead of items
        - set copy flag to False when masking numpy values
        - earlier release of resources when it's sure they are not needed any longer
        - attempt calls to garbage collection in key points

* **041**  Enriched information in test suite:
        - using memory_profile module to display memory usage,
        - compute time execution difference between pyg2p and grib2pcraster
        - improved output for better readability

v 1.2.8
-------
* **040** Bug fix: When ungribbing a multiresolution file, if the extended resolution intertable was not found,
        the program was errouneously producing the intertable.

* **039** Bug fix: In manipulation of extended resolution messages in a multiresolution file,
    the manipulator was instantiated with a wrong start_step and so the manipulated maps were wrong.

v 1.2.7
-------
* **038** In accumulation aggregation, the user can optionally force pyg2p to use a zero array as initial input GRIB,
        even if a message at step 0 exists in the GRIB file for that variable.
    To use this option, set the attribute forceZeroArray="y" for the Aggregation XML element.


v 1.2.6
-------
* **037** Bug Fix: Configuration errors (like wrong paths to lat, lon, dem, clone maps) weren't properly logged
        due a bug in constructing the application error message.

* **036** Added some few tests and comments to configuration/tests/commands.txt

* **035** Some move refactoring (moving methods in utils modules)


v 1.2.5
-------
* **034** Test functionality, activated with -t CLI argument, performs numerical checks of diff maps
        and logs red messages if values are too big.
        New XML configuration parameter: 'atol' (absolute tolerance).

* **033** Bug fix: Some lat/lon PCRaster maps shared the same metadata so the interpolation id resulted to be the same,
        even if they are different (because of different projection).
        Added min and max values of lats and longs to the metadata. This ensures uniqueness in the interpolation filename
        for each GRIB grid/PCRaster grid couple, also in slighty different projected areas.

* **032** Bug fix: new added CLI arguments fmap and ext prevented corresponding XML configuration to be read
    so they were set to default '1'.

* **031** Bug Fix: Removed logs of coordinates when points are out of grid during creation of interpolation table.


v 1.2.4
-------
* **030** Bug Fix: 2nd Resolution Intertable wasn't logged.

* **029** Filenames starting with dash '-' are problematic in linux.
    Now intertables filename has the prefix 'I'.


v 1.2.3
-------
* **028** Bug fix:  Grid ID, as used in intertables filenames and in geopotentials IDs (in geopotentials.xml),
        were erroneously constructed cutting away decimals.
        This could have lead to ambiguities when selecting intertables or geopotentials,
        in case some GRIB files have a grid with a difference in decimals in its bounding box longitudes.

* **027** Bug fix: test_reqs.py was never able to check the existence of configuration directory due a bug in paths.

v. 1.2.2
--------
* **026** Bug fix: Single multiresolution gribs extraction was failing for a bug in reading second resolution values.
    Previous versions are working if using two input files (arguments -i and -I).

v. 1.2.1
--------
* **025** Improved output of test_reqs.py

* **024** Added some information to Correction chapter in User manual.

* **023** When no messages found, the application exits gracefully (error code: 0) and an error message is displayed.
    "Error: >>>>>>>>>>>>>>> Application Error: No Messages found using {'shortName': 'tp', 'perturbationNumber': 1}"

* **022** Bug fix: Logger was closed when exception raised after the application startup so
        a criptic message "no handlers found" was shown.

v. 1.2
------
* **021**  Added a new input parameter -T (--dataTime) (or Parameter#dataTime attribute in XML templating)
        for grib selection (specific for some UKMO files).

* **020** Improved test functionality.
    - Now multiple grib2pcraster executions are allowed in a single test case.
      Needed for spatial multiresolution grib files (e.g. global) tests.
    - Now only pyg2p tests (without comparison) are allowed.
      Needed to fire-test commands not configurable in grib2pcraster (e.g. UKMO files)

* **019** Bug fixin test functionality: Tests with id>9 were overwriting test 1 and lost in configuration.


v. 1.1
------
* **018** Added a little test tool for comparing results between the grib2pcraster C application and any new pyg2p release.
    The functionality compares the number of output maps in each test case
        and produces diff PCRaster maps for manual comparison.

v. 1.06
-------
* **017** File logging can be disabled in logger-configuration.xml using activated="False" in the root Loggers XML element.
    You can set to false,False,no,NO,No for deactivating.
    Any other string will be evaluated to True. The element is optional. Default value is True.

* **016** Added -s and -e CLI arguments for grib start and end timestamps, overriding xml parameters.

v. 1.05
-------
* **015** Added "pyg2p -t test.xml" for running test suites all in once useful for fire tests, to spot severe bugs.
    (alpha version: only pyg2p commands are executed in this version)

* **014** Bug fix: Fixed a number of bugs introduced in last release.

v. 1.04
-------
* **013** test_reqs.py now tests the content of the release (core packages and configuration files).

* **012** Added a new xml configuration option: intertableDir to use alternative sets of interlookup tables.


v. 1.03
-------
* **011** Bug fix: Fixed message's key after instananeous aggregation (was affecting only as wrong log messages).

* **010** Bug fix: Fixed bug in writing PCRaster maps. Clone's zero values were considered as missing values.

* **009** Bug fix: Fixed bug for Aggregation instantaneous (messages were not ordered)


v. 1.02
-------
* **008** Now cutting of negative values is done before writing maps, after manipulation and interpolation.
    This speeds disk writing operations.

* **007** Bug fix : Fixed bug when tstart and tend were not configured, for unsorted grib files


v. 1.01
-------
* **006** Bug fix: Fixed output directory path ending with double slashes when issued with a final slash.

* **005** Bug fix: For some gribs, step zero is missing which is needed
    for aggregations starting from zero.
    During aggregation, a Zero by Division was arising while trying to create
    the zero message from two existing ones.
    Now, a zero filled message is used instead.

* **004** Bug fix: Fixed scipy invdist interpolation mode for lat/long maps
    having missing values (like COSMO ones).

* **003** Bug fix: Wrong log message during accumulation.

* **002** Conversion is applied at the very beginning, in one raw, instead of
    when writing maps. In this way, operations are made
    in target unit and it can be desiderable.
    This brings also a little improvement in performances.
    Note that cutting of negative values is still done before to write the map.

* **001** Improved logs in Manipulator.py, Interpolation.py, Controller.py.

v 1.00
------
**First Release.**

* Added the -g option to the initial requirements.
