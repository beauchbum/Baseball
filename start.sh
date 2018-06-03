#!/bin/bash -l

set -e
set -x
CONDA_ENV=baseball

PORT="${1:-5000}"

conda env update environment.yml
source activate $CONDA_ENV

python main.py --port $port