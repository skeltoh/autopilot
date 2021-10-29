#! /bin/bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    python3-dev \
    python3-pip \
    git \
    libatlas-base-dev \
    libsamplerate0-dev \
    libsndfile1-dev \
    libreadline-dev \
    libasound-dev \
    i2c-tools \
    libportmidi-dev \
    liblo-dev \
    libhdf5-dev \
    libzmq-dev \
    libffi-dev


pip3 install virtualenv
mkdir ~/.venv
python3 -m virtualenv ~/.venv/autopilot
source ~/.venv/autopilot/bin/activate
git config --global user.name "Henry"
git config --global user.email "hskelto@emory.edu"
mkdir git
cd git
git clone https://github.com/skeltoh/autopilot.git
cd autopilot
pip3 install -e .
