FROM ubuntu:26.04

ARG GROUP_ID
ARG USER_ID
ARG USER_NAME

RUN \
    apt-get update -y && \
    apt-get install -y git wget build-essential && \
    groupadd -g $GROUP_ID $USER_NAME && \
    useradd -u $USER_ID -g $USER_NAME $USER_NAME

USER $USER_NAME

RUN echo $USER, $HOME, $(pwd)
RUN wget -q https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh
RUN bash Miniforge3-$(uname)-$(uname -m).sh -b -c
RUN conda install -y cmake make cython swig doxygen numpy setuptools
