#!/bin/bash -ex

miniforge="Miniforge3-$(uname)-$(uname -m).sh"

echo $HOME
echo $USER
echo $(pwd)

wget -q "https://github.com/conda-forge/miniforge/releases/latest/download/$miniforge"
chmod +x "$miniforge"
"./$miniforge" -b -c -p "$(pwd)/miniforge"
conda install -q -y cmake make cython swig doxygen numpy setuptools
