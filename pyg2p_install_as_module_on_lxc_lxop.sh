#!/bin/bash

# This script installs pyg2p as a module in /usr/local/apps
#
# you must be logged into the target machine (lxc, lxop)

set -ex


# What version string should the installed module have
mod=2.1.0

# Where is pyg2p source code
src_root=.

# Which static dataset should this installation
# use (geopotentials, interpolation tables).
static_data_root=/gpfs/lxc/efas/emos/data/pyg2p/2.1.0 #LXC
#static_data_root=/gpfs/lxop/efas/emos/data/pyg2p/2.1.0 #LXOP



# fetch source
#git clone git@bitbucket.org:nappodo/pyg2p.git

# Prior to installation we need to set paths to binary assets
# (geopotentials and interpolation tables) in the .json file

echo "{
    \"geopotentials\": \"$static_data_root/geopotentials\",
    \"intertables\": \"$static_data_root/intertables\"
}
" > $src_root/configuration/global/global_conf.json


# Execute installation

module unload python || :
module load python/2.7.12-01

export HTTPS_PROXY=http://proxy.ecmwf.int:3333
export PYTHONPATH=$PYTHONPATH:/usr/local/apps/pyg2p/$mod/lib/python2.7/site-packages

python setup.py clean --all
python setup.py install --prefix=/usr/local/apps/pyg2p/$mod
