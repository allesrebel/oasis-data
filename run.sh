#!/bin/bash

# Collect Figures across all Variants
cd ORB_SLAM3/evaluation
~/oasis-data/src/run_all.sh
~/oasis-data/src/create_plots.sh

# Generate Post Processed Data for masks and extract table
python3 ~/oasis-data/src/process_data_with_eval.py ~/ORB_SLAM3/evaluation
python3 ~/oasis-data/src/generate_tables.py processed/

# move everything to home dir
cp -r ~/ORB_SLAM3/evaluation/. ~/.
