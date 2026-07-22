FROM ubuntu:26.04
RUN \
    apt-get update -y && \
    apt-get install -y git wget && \
    wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh && \
    bash Miniforge3-$(uname)-$(uname -m).sh -b && \
    conda install cmake make cython swig doxygen numpy setuptools
