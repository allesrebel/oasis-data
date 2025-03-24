#!/usr/bin/env python3
import os
import sys
import re
import pandas as pd

def extract_max_error_value(file_path):
    """
    Reads through the file and returns the float value associated with 
    'absolute_translational_error.max' if found.
    """
    with open(file_path, 'r') as f:
        for line in f:
            # Strip leading/trailing whitespace
            line = line.strip()
            if line.startswith("absolute_translational_error.max"):
                # Expected format:
                # absolute_translational_error.max 0.15004927260652412 m
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return float(parts[1])
                    except ValueError:
                        return None
    return None

def extract_mean_error_value(file_path):
    """
    Reads through the file and returns the float value associated with 
    'absolute_translational_error.mean' if found.
    """
    with open(file_path, 'r') as f:
        for line in f:
            # Strip leading/trailing whitespace
            line = line.strip()
            if line.startswith("absolute_translational_error.mean"):
                # Expected format:
                # absolute_translational_error.mean 0.15004927260652412 m
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return float(parts[1])
                    except ValueError:
                        return None
    return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 script.py <processed data path>")
        sys.exit(1)

    processing_dir = sys.argv[1]

    # Regex to match file names of the form:
    # {platform}_{dataset}_{run_type}_{sensor_type}_{trial}.txt
    pattern = re.compile(
        r'^(?P<platform>[^_]+)_'
        r'(?P<dataset>[^_]+)_'
        r'(?P<run_type>[^_]+)_'
        r'(?P<sensor_type>.+)_'
        r'(?P<trial>\d+)\.txt$'
    )
    
    data = []
    for file in os.listdir(processing_dir):
        match = pattern.match(file)
        if not match:
            print(f"Skipping file not matching pattern: {file}")
            continue
        
        groups = match.groupdict()
        file_path = os.path.join(processing_dir, file)
        max_error_value = extract_max_error_value(file_path)
        mean_error_value = extract_mean_error_value(file_path)
        
        if max_error_value is None:
            print(f"Error value not found or invalid in file: {file}")
            continue
        
        # Append row data (trial is not stored in the DataFrame as per the request)
        row = {
            "platform": groups["platform"],
            "dataset": groups["dataset"],
            "run_type": groups["run_type"],
            "sensor_type": groups["sensor_type"],
            "absolute_translational_error.max": max_error_value,
            "absolute_translational_error.mean": mean_error_value
        }
        data.append(row)
    
    # Create a DataFrame from the collected data
    df = pd.DataFrame(data)

    # Define the fixed values and valid datasets.
    fixed_platform = "jetson"
    fixed_sensor_type = "stereo_imu"
    fixed_run_type = "deadlines"
    valid_datasets = {"MH01", "MH02", "MH03", "MH04", "MH05"}

    # Filter for the fixed values.
    df_f = df[df["platform"] == fixed_platform]
    df_f = df_f[df_f["sensor_type"] == fixed_sensor_type]
    df_f = df_f[df_f["run_type"] == fixed_run_type]

    
    # Filter the DataFrame to include only the datasets MH01 to MH05.
    valid_datasets = {"MH01", "MH02", "MH03", "MH04", "MH05"}
    df_f = df_f[df_f["dataset"].isin(valid_datasets)]

    # Group by dataset and calculate the average max translational error.
    grouped_max = df_f.groupby("dataset")["absolute_translational_error.max"].mean().reset_index()
    grouped_mean = df_f.groupby("dataset")["absolute_translational_error.mean"].mean().reset_index()

    # Print out the average error for each dataset.
    for _, row in grouped_max.iterrows():
        print(f"Dataset: {row['dataset']}, Average absolute_translational_error.max: {row['absolute_translational_error.max']}")
    for _, row in grouped_mean.iterrows():
        print(f"Dataset: {row['dataset']}, Average absolute_translational_error.mean: {row['absolute_translational_error.mean']}")


if __name__ == "__main__":
    main()
