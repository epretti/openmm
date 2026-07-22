#!/bin/bash -ex

EXTRA_CMAKE_ARGS="-DOPENMM_BUILD_CUDA_LIB=false -DOPENMM_BUILD_OPENCL_LIB=false"
. devtools/ci/jenkins/install.sh
python devtools/run-ctest.py --job-duration=120 --timeout 300 -R 'Test(Cpu|Reference)' --parallel 6

# Build & test Python
make PythonInstall
python -m openmm.testInstallation
cd python/tests && pytest -n 6 -v
