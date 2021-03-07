#!/bin/sh

echo "Converting ID=$1.."

CONDA_BASE=$(conda info --base)
source $CONDA_BASE/etc/profile.d/conda.sh
conda activate demucs
python -m demucs.separate --dl -n demucs -d cpu --mp3 --out ../demucs-frontend/output --models ../demucs-frontend/models ../demucs-frontend/input/$1.mp3