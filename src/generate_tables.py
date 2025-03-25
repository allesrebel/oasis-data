#!/usr/bin/env python3
import os
import sys
import re
import pandas as pd
import matplotlib.pyplot as plt

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
    # {platform}_{dataset}_{run_type}_{sensor_type}_{trial}_{mask_size}.txt
    pattern = re.compile(
        r'^(?P<platform>[^_]+)_'
        r'(?P<dataset>[^_]+)_'
        r'(?P<run_type>.+?)(?=_[^_]+_[^_]+_\d+(?:_\d+)?\.txt)_'
        r'(?P<sensor_type>[^_]+_[^_]+)_'
        r'(?P<trial>\d+)(?:_(?P<mask_size>\d+))?\.txt$'
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
            "mask_size": groups.get("mask_size", None),
            "absolute_translational_error.max": max_error_value,
            "absolute_translational_error.mean": mean_error_value
        }
        data.append(row)
    
    # Create a DataFrame from the collected data
    df = pd.DataFrame(data)

    # Define the fixed values and valid datasets.
    fixed_platform = "jetson"
    fixed_sensor_type = "stereo_imu"
    fixed_run_type = ["normal", "deadlines", "oasis"]
    valid_datasets = {"MH01", "MH02", "MH03", "MH04", "MH05"}

    # Filter for the fixed values.
    df_f = df[df["platform"] == fixed_platform]
    df_f = df_f[df_f["sensor_type"] == fixed_sensor_type]

    
    # Filter the DataFrame to include only the datasets MH01 to MH05.
    valid_datasets = {"MH01", "MH02", "MH03", "MH04", "MH05"}
    df_f = df_f[df_f["dataset"].isin(valid_datasets)]

    for fixed_run in fixed_run_type:

        print(f"Table for {fixed_platform}, {fixed_run}, for {fixed_sensor_type}")

        # Filter the DataFrame to include only the fixed run type.
        df_f_run = df_f[df_f["run_type"] == fixed_run]

        # Group by dataset and calculate the average max translational error.
        grouped_max = df_f_run.groupby("dataset")["absolute_translational_error.max"].mean().reset_index()
        grouped_mean = df_f_run.groupby("dataset")["absolute_translational_error.mean"].mean().reset_index()

        # Print out the average error for each dataset.
        for _, row in grouped_max.iterrows():
            print(f"Dataset: {row['dataset']}, Average absolute_translational_error.max: {row['absolute_translational_error.max']}")
        for _, row in grouped_mean.iterrows():
            print(f"Dataset: {row['dataset']}, Average absolute_translational_error.mean: {row['absolute_translational_error.mean']}")

    print("Unique mask_size values:", df_f["mask_size"].unique())

    # Only consider rows with a valid mask_size
    df_mask = df_f[df_f["mask_size"].notnull()].copy()

    for dataset in valid_datasets:
        df_dataset = df_mask[df_mask["dataset"] == dataset].copy()  # Create an independent copy
        if df_dataset.empty:
            print(f"No data points with mask_size available for dataset {dataset} plotting.")
            continue
        # Convert mask_size to int using .loc to avoid the SettingWithCopyWarning.
        df_dataset.loc[:, "mask_size"] = df_dataset["mask_size"].astype(int)
        
        # Create a new figure for each dataset so each plot is independent.
        plt.figure()
        plt.scatter(df_dataset["mask_size"], df_dataset["absolute_translational_error.mean"], label="Raw Data")
        group_stats = df_dataset.groupby("mask_size")["absolute_translational_error.mean"].agg(["mean", "std"]).reset_index()
        plt.errorbar(group_stats["mask_size"], group_stats["mean"], yerr=group_stats["std"], fmt='-o', color='red', label="Mean ± STD")
        plt.xlabel("Mask Size (cells^2)")
        plt.ylabel("ATE Error Mean (m)")
        plt.title(f"ATE Error Mean vs Mask Size for {dataset}")
        plt.grid(True)
        plt.show()

        plt.figure()
        plt.scatter(df_dataset["mask_size"], df_dataset["absolute_translational_error.max"])
        group_stats_max = df_dataset.groupby("mask_size")["absolute_translational_error.max"].agg(["mean", "std"]).reset_index()
        plt.errorbar(group_stats_max["mask_size"], group_stats_max["mean"], yerr=group_stats_max["std"], fmt='-o', color='red', label="Mean ± STD")        
        plt.xlabel("Mask Size (cells^2)")
        plt.ylabel("ATE Error Max (m)")
        plt.title(f"Max ATE Error vs Mask Size for {dataset}")
        plt.grid(True)
        plt.show()


if __name__ == "__main__":
    main()
