# Use Ubuntu 22.04 (Jammy Jellyfish) as the base image
FROM ubuntu:jammy

# Set environment variable to prevent user interaction during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Run apt update as root user
RUN apt update
RUN apt install -y python3 python3-pip

WORKDIR /root

# Copy Artifacts
COPY ORB_SLAM3 /root/ORB_SLAM3
COPY oasis-data /root/oasis-data

# Perform dependency install
RUN python3 -m pip install -r /root/oasis-data/src/requirements.txt
