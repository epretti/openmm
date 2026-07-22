FROM ubuntu:26.04

ARG GROUP_ID
ARG USER_ID
ARG USER_NAME

RUN \
    apt-get update -y && \
    apt-get install -y git wget build-essential && \
    mkdir /home/$USER_NAME && \
    groupadd -g $GROUP_ID $USER_NAME && \
    useradd -u $USER_ID -g $USER_NAME -d /home/$USER_NAME $USER_NAME && \
    chown $USER_NAME:$USER_NAME /home/$USER_NAME

USER $USER_NAME
WORKDIR /home/$USER_NAME

RUN \
    cd $HOME && \
    wget -q https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh && \
    bash Miniforge3-$(uname)-$(uname -m).sh -b -c && \
    conda install -y cmake make cython swig doxygen numpy setuptools
