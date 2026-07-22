FROM condaforge/miniforge3:latest

RUN \
    apt-get update -y && \
    apt-get install -y build-essential && \
    conda install -y cmake make cython swig doxygen numpy setuptools
