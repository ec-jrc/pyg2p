CHANGE LOG
==========

v 1.2.9
-------
* **044** Improvement (major)

   Performances improvements:
        - adoption of numexpr in  manipulation, correction, conversion
          (instead of numpy vectorized functions obtained from lambdas)
          Improvements are extremelly evident especially in large grids processing like T3999.
        - using grib api indexes instead opened files. Boost performances in startup
            for huge input grib files.

* **043** Improvement (major)

   Memory footprint is reduced of 30%/70%:
        - removed two unused collections
        - using iteritems instead of items
        - set copy flag to False when masking numpy values
        - earlier release of resources when it's sure they are not needed any longer
        - attempt calls to garbage collection in key points

* **041** Improvement (minor)

   Enriched information in test suite:
        - using memory_profile module to display memory usage,
        - compute time execution difference between pyg2p and grib2pcraster
        - improved output for better readability

v 1.2.8
-------
* **040** Bug fix (major)
    When ungribbing a multiresolution file, if the extended resolution intertable was not found,
        the program was errouneously producing the intertable.

* **039** Bug fix (major)
    In manipulation of extended resolution messages in a multiresolution file,
    the manipulator was instantiated with a wrong start_step and so the manipulated maps were wrong.

v 1.2.7
-------
* **038** Improvement (major)
    In accumulation aggregation, the user can optionally force pyg2p to use a zero array as initial input GRIB,
        even if a message at step 0 exists in the GRIB file for that variable.
    To use this option, set the attribute forceZeroArray="y" for the Aggregation XML element.


v 1.2.6
-------
* **037** Bug Fix (minor)
    Configuration errors (like wrong paths to lat, lon, dem, clone maps) weren't properly logged
        due a bug in constructing the application error message.

* **036** Improvement (minor)
    Added some few tests and comments to configuration/tests/commands.txt

* **035** Improvement (minor)
    Some move refactoring (moving methods in utils modules)


v 1.2.5
-------
* **034** Improvement (major):
    Test functionality, activated with -t CLI argument, performs numerical checks of diff maps
        and logs red messages if values are too big.
        New XML configuration parameter: 'atol' (absolute tolerance).

* **033** Bug fix (minor):
    Some lat/lon PCRaster maps shared the same metadata so the interpolation id resulted to be the same,
        even if they are different (because of different projection).
        Added min and max values of lats and longs to the metadata. This ensures uniqueness in the interpolation filename
        for each GRIB grid/PCRaster grid couple, also in slighty different projected areas.

* **032** Bug fix (major):
    new added CLI arguments fmap and ext prevented corresponding XML configuration to be read
    so they were set to default '1'.

* **031** Bug Fix (minor):
    Removed logs of coordinates when points are out of grid
        during creation of interpolation table.


v 1.2.4
-------
* **030** Bug Fix (minor):
    2nd Resolution Intertable wasn't logged.

* **029** Improvement (minor):
    Filenames starting with dash '-' are problematic in linux.
    Now intertables filename has the prefix 'I'.


v 1.2.3
-------
* **028** Bug fix (major):
    Grid ID, as used in intertables filenames and in geopotentials IDs (in geopotentials.xml),
        were erroneously constructed cutting away decimals.
        This could have lead to ambiguities when selecting intertables or geopotentials,
        in case some GRIB files have a grid with a difference in decimals in its bounding box longitudes.

* **027** Bug fix (minor):
    test_reqs.py was never able to check the existence of configuration directory due a bug in paths.

v. 1.2.2
--------
* **026** Bug fix (major):
    Single multiresolution gribs extraction was failing for a bug in reading second resolution values.
    Previous versions are working if using two input files (arguments -i and -I).

v. 1.2.1
--------
* **025** Improvement (minor):
    Improved output of test_reqs.py

* **024** Improvement (minor):
    Added some information to Correction chapter in User manual.

* **023** Improvement (major):
    When no messages found, the application exits gracefully (error code: 0) and an error message is displayed.
    "Error: >>>>>>>>>>>>>>> Application Error: No Messages found using {'shortName': 'tp', 'perturbationNumber': 1}"

* **022** Bug fix (major):
    Logger was closed when exception raised after the application startup so
        a criptic message "no handlers found" was shown.

v. 1.2
------
* **021** Improvement (major):
    Added a new input parameter -T (--dataTime) (or Parameter#dataTime attribute in XML templating)
        for grib selection (specific for some UKMO files).

* **020** Improvement (major):
    Improved test functionality.
    - Now multiple grib2pcraster executions are allowed in a single test case.
      Needed for spatial multiresolution grib files (e.g. global) tests.
    - Now only pyg2p tests (without comparison) are allowed.
      Needed to fire-test commands not configurable in grib2pcraster (e.g. UKMO files)

* **019** Bug fix (major):
    Bug fix in test functionality. Tests with id>9 were overwriting test 1 and lost in configuration.


v. 1.1
------
* **018** Improvement (major):
    Added a little test tool for comparing results between the grib2pcraster C application and any new pyg2p release.
    The functionality compares the number of output maps in each test case
        and produces diff PCRaster maps for manual comparison.

v. 1.06
-------
* **017** Improvement (minor):
    File logging can be disabled in logger-configuration.xml using activated="False" in the root Loggers XML element.
    You can set to false,False,no,NO,No for deactivating.
    Any other string will be evaluated to True. The element is optional. Default value is True.

* **016** Improvement (major):
    Added -s and -e CLI arguments for grib start and end timestamps, overriding xml parameters.

v. 1.05
-------
* **015** Improvement (major):
    added "pyg2p -t test.xml" for running test suites all in once
    useful for fire tests, to spot severe bugs.
    (alpha version: only pyg2p commands are executed in this version)

* **014** Bug fix (major):
    Fixed a number of bugs introduced in last release.

v. 1.04
-------
* **013** Improvement (minor):
    test_reqs.py now tests the content of the release (core packages and configuration files).

* **012** Improvement (major):
    Added a new xml configuration option: intertableDir to use alternative sets of interlookup tables.


v. 1.03
-------
* **011** Bug fix (minor):
    Fixed message's key after instananeous aggregation (was affecting only as wrong log messages).

* **010** Bug fix (major):
    Fixed bug in writing PCRaster maps. Clone's zero values were considered as missing values.

* **009** Bug fix (major):
    Fixed bug for Aggregation instantaneous (messages were not ordered)


v. 1.02
-------
* **008** Improvement (minor):
    Now cutting of negative values is done before writing maps, after manipulation and interpolation.
    This speeds disk writing operations.

* **007** Bug fix (major):
    Fixed bug when tstart and tend were not configured, for unsorted grib files


v. 1.01
-------
* **006** Bug fix (minor):
    Fixed output directory path ending with double slashes when issued with a final slash.

* **005** Bug fix (major):
    For some gribs, step zero is missing which is needed
    for aggregations starting from zero.
    During aggregation, a Zero by Division was arising while trying to create
    the zero message from two existing ones.
    Now, a zero filled message is used instead.

* **004** Bug fix (major):
    Fixed scipy invdist interpolation mode for lat/long maps
    having missing values (like COSMO ones).

* **003** Bug fix (minor):
    Wrong log message during accumulation.

* **002** Improvement (major):
    Conversion is applied at the very beginning, in one raw, instead of
    when writing maps. In this way, operations are made
    in target unit and it can be desiderable.
    This brings also a little improvement in performances.
    Note that cutting of negative values is still done before to write the map.

* **001** Improvement (minor):
    Improved logs in Manipulator.py, Interpolation.py, Controller.py.

v 1.00
------
**First Release.**

* Added the -g option to the initial requirements.
