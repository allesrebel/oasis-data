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
            line = line.strip()
            if line.startswith("absolute_translational_error.max"):
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
            line = line.strip()
            if line.startswith("absolute_translational_error.mean"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return float(parts[1])
                    except ValueError:
                        return None
    return None

def extract_map_complexity(file_path):
    """
    Reads through the file and extracts the map complexity information.
    Returns a dictionary with keys 'KFs in map' and 'MPs in map'.
    """
    complexity = {"KFs in map": None, "MPs in map": None}
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("KFs in map:"):
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        complexity["KFs in map"] = int(parts[1].strip())
                    except ValueError:
                        complexity["KFs in map"] = None
            elif line.startswith("MPs in map:"):
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        complexity["MPs in map"] = int(parts[1].strip())
                    except ValueError:
                        complexity["MPs in map"] = None
    return complexity

def extract_timing_info(file_path):
    """
    Reads through the file and extracts timing information.
    Returns a dictionary with keys 'Average Time' and 'Std Dev'.
    """
    timing = {"Average Time": None, "Std Dev": None}
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("Average Time:"):
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        timing["Average Time"] = float(parts[1].strip())
                    except ValueError:
                        timing["Average Time"] = None
            elif line.startswith("Std Dev:"):
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        timing["Std Dev"] = float(parts[1].strip())
                    except ValueError:
                        timing["Std Dev"] = None
    return timing

def extract_fov_mask_data(file_path):
    """
    Reads through the processed file and extracts the cellManager FOV Mask Data.
    Expects a block in the file starting with:
      FOV Mask Data from cellManager.txt:
    followed by lines like:
      Time: <timestamp>, FOV Mask: <width>x<height>
    
    Returns:
        list of tuples: Each tuple is (timestamp, fov_width, fov_height).
    """
    fov_data = []
    with open(file_path, 'r') as f:
        content = f.read()
    # Look for the FOV Mask Data block.
    match = re.search(r'FOV Mask Data from cellManager\.txt:\s*\n(.*)', content, flags=re.DOTALL)
    if match:
        data_block = match.group(1)
        lines = data_block.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = re.match(r'Time:\s*([\d\.eE\+\-]+),\s*FOV Mask:\s*(\d+)x(\d+)', line)
            if m:
                try:
                    ts = float(m.group(1))
                except Exception:
                    ts = None
                width = int(m.group(2))
                height = int(m.group(3))
                fov_data.append((ts, width, height))
    return fov_data

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 script.py <processed data path> [save]")
        sys.exit(1)

    processing_dir = sys.argv[1]
    # Check for the optional "save" flag.
    save_plots = False
    if len(sys.argv) > 2 and sys.argv[2].lower() == "save":
        save_plots = True

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
    data_fov = []  # Will hold cellManager FOV Mask data.
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

        map_complexity = extract_map_complexity(file_path)
        timing_info = extract_timing_info(file_path)

        row = {
            "platform": groups["platform"],
            "dataset": groups["dataset"],
            "run_type": groups["run_type"],
            "sensor_type": groups["sensor_type"],
            "mask_size": groups.get("mask_size", None),
            "absolute_translational_error.max": max_error_value,
            "absolute_translational_error.mean": mean_error_value,
            "KFs in map": map_complexity["KFs in map"],
            "MPs in map": map_complexity["MPs in map"],
            "Average Time": timing_info["Average Time"],
            "Std Dev": timing_info["Std Dev"]
        }
        data.append(row)

        # Extract cellManager FOV Mask Data (if any)
        fov_list = extract_fov_mask_data(file_path)
        for fov in fov_list:
            ts, width, height = fov
            row_fov = {
                "platform": groups["platform"],
                "dataset": groups["dataset"],
                "run_type": groups["run_type"],
                "sensor_type": groups["sensor_type"],
                "trial": groups["trial"],
                "mask_size": groups.get("mask_size", None),
                "cellmanager_timestamp": ts,
                "fov_width": width,
                "fov_height": height
            }
            data_fov.append(row_fov)
    
    df = pd.DataFrame(data)
    df_fov = pd.DataFrame(data_fov)

    fixed_platform = "jetson"
    fixed_sensor_type = "stereo_imu"
    fixed_run_type = ["normal", "deadlines", "oasis"]
    valid_datasets = {"MH01", "MH02", "MH03", "MH04", "MH05"}

    df_f = df[df["platform"] == fixed_platform]
    df_f = df_f[df_f["sensor_type"] == fixed_sensor_type]
    df_f = df_f[df_f["dataset"].isin(valid_datasets)]

    for fixed_run in fixed_run_type:
        print(f"Table for {fixed_platform}, {fixed_run}, for {fixed_sensor_type}")
        df_f_run = df_f[df_f["run_type"] == fixed_run]
        grouped_max = df_f_run.groupby("dataset")["absolute_translational_error.max"].mean().reset_index()
        grouped_mean = df_f_run.groupby("dataset")["absolute_translational_error.mean"].mean().reset_index()

        for _, row in grouped_max.iterrows():
            print(f"Dataset: {row['dataset']}, Average absolute_translational_error.max: {row['absolute_translational_error.max']}")
        for _, row in grouped_mean.iterrows():
            print(f"Dataset: {row['dataset']}, Average absolute_translational_error.mean: {row['absolute_translational_error.mean']}")

    print("Unique mask_size values:", df_f["mask_size"].unique())

    df_mask = df_f[df_f["mask_size"].notnull()].copy()

    # Plot ATE Error Mean and Max vs Mask Size for each dataset.
    for dataset in valid_datasets:
        df_dataset = df_mask[df_mask["dataset"] == dataset].copy()
        if df_dataset.empty:
            print(f"No data points with mask_size available for dataset {dataset} plotting.")
            continue
        df_dataset.loc[:, "mask_size"] = df_dataset["mask_size"].astype(int)
        
        # Plot ATE Error Mean vs Mask Size.
        plt.figure()
        plt.scatter(df_dataset["mask_size"], df_dataset["absolute_translational_error.mean"], label="Raw Data")
        group_stats = df_dataset.groupby("mask_size")["absolute_translational_error.mean"].agg(["mean", "std"]).reset_index()
        plt.errorbar(group_stats["mask_size"], group_stats["mean"], yerr=group_stats["std"], fmt='-o', color='red', label="Mean ± STD")
        plt.xlabel("Mask Size (cells^2)")
        plt.ylabel("ATE Error Mean (m)")
        plt.title(f"ATE Error Mean vs Mask Size for {dataset}")
        plt.legend()
        plt.grid(True)
        if save_plots:
            filename = f"{dataset}_ate_error_mean_vs_mask_size.png"
            plt.savefig(filename)
            plt.close()
            print(f"Saved plot to {filename}")
        else:
            plt.show()

        print(f"\nLaTeX Table for ATE Error Mean vs Mask Size for {dataset}:")
        print(group_stats.to_latex(index=False, float_format="%.3f"))

        # Plot ATE Error Max vs Mask Size.
        plt.figure()
        plt.scatter(df_dataset["mask_size"], df_dataset["absolute_translational_error.max"])
        group_stats_max = df_dataset.groupby("mask_size")["absolute_translational_error.max"].agg(["mean", "std"]).reset_index()
        plt.errorbar(group_stats_max["mask_size"], group_stats_max["mean"], yerr=group_stats_max["std"], fmt='-o', color='red', label="Mean ± STD")
        plt.xlabel("Mask Size (cells^2)")
        plt.ylabel("ATE Error Max (m)")
        plt.title(f"Max ATE Error vs Mask Size for {dataset}")
        plt.legend()
        plt.grid(True)
        if save_plots:
            filename = f"{dataset}_ate_error_max_vs_mask_size.png"
            plt.savefig(filename)
            plt.close()
            print(f"Saved plot to {filename}")
        else:
            plt.show()

        print(f"\nLaTeX Table for Max ATE Error vs Mask Size for {dataset}:")
        print(group_stats_max.to_latex(index=False, float_format="%.3f"))

    # Plot Timing vs Mask Size for each dataset.
    for dataset in valid_datasets:
        df_dataset = df_mask[df_mask["dataset"] == dataset].copy()
        if df_dataset.empty:
            print(f"No timing data available for dataset {dataset} plotting.")
            continue
        df_dataset.loc[:, "mask_size"] = df_dataset["mask_size"].astype(int)
        
        plt.figure()
        plt.scatter(df_dataset["mask_size"], df_dataset["Average Time"], label="Raw Timing Data")
        group_stats_time = df_dataset.groupby("mask_size")["Average Time"].agg(["mean", "std"]).reset_index()
        plt.errorbar(group_stats_time["mask_size"], group_stats_time["mean"], yerr=group_stats_time["std"], fmt='-o', color='red', label="Mean ± STD")
        plt.xlabel("Mask Size (cells^2)")
        plt.ylabel("Average Time")
        plt.title(f"Average Timing vs Mask Size for {dataset}")
        plt.grid(True)
        plt.legend()
        if save_plots:
            filename = f"{dataset}_timing_vs_mask_size.png"
            plt.savefig(filename)
            plt.close()
            print(f"Saved plot to {filename}")
        else:
            plt.show()

        print(f"\nLaTeX Table for Average Timing vs Mask Size for {dataset}:")
        print(group_stats_time.to_latex(index=False, float_format="%.3f"))

    # Plot Map Complexity vs Mask Size for each dataset.
    for dataset in valid_datasets:
        df_dataset = df_mask[df_mask["dataset"] == dataset].copy()
        if df_dataset.empty:
            print(f"No map complexity data available for dataset {dataset} plotting.")
            continue
        df_dataset.loc[:, "mask_size"] = df_dataset["mask_size"].astype(int)
        
        # Plot KFs in map vs Mask Size.
        plt.figure()
        plt.scatter(df_dataset["mask_size"], df_dataset["KFs in map"], label="Raw KFs Data")
        group_stats_kf = df_dataset.groupby("mask_size")["KFs in map"].agg(["mean", "std"]).reset_index()
        plt.errorbar(group_stats_kf["mask_size"], group_stats_kf["mean"], yerr=group_stats_kf["std"], fmt='-o', color='red', label="Mean ± STD")
        plt.xlabel("Mask Size (cells^2)")
        plt.ylabel("KFs in Map")
        plt.title(f"KFs in Map vs Mask Size for {dataset}")
        plt.grid(True)
        plt.legend()
        if save_plots:
            filename = f"{dataset}_kfs_in_map_vs_mask_size.png"
            plt.savefig(filename)
            plt.close()
            print(f"Saved plot to {filename}")
        else:
            plt.show()

        print(f"\nLaTeX Table for KFs in Map vs Mask Size for {dataset}:")
        print(group_stats_kf.to_latex(index=False, float_format="%.3f"))
        
        # Plot MPs in map vs Mask Size.
        plt.figure()
        plt.scatter(df_dataset["mask_size"], df_dataset["MPs in map"], label="Raw MPs Data")
        group_stats_mps = df_dataset.groupby("mask_size")["MPs in map"].agg(["mean", "std"]).reset_index()
        plt.errorbar(group_stats_mps["mask_size"], group_stats_mps["mean"], yerr=group_stats_mps["std"], fmt='-o', color='red', label="Mean ± STD")
        plt.xlabel("Mask Size (cells^2)")
        plt.ylabel("MPs in Map")
        plt.title(f"MPs in Map vs Mask Size for {dataset}")
        plt.grid(True)
        plt.legend()
        if save_plots:
            filename = f"{dataset}_mps_in_map_vs_mask_size.png"
            plt.savefig(filename)
            plt.close()
            print(f"Saved plot to {filename}")
        else:
            plt.show()

        print(f"\nLaTeX Table for MPs in Map vs Mask Size for {dataset}:")
        print(group_stats_mps.to_latex(index=False, float_format="%.3f"))

    if not df_fov.empty:
        # Plot only one mask dimension (fov_width) for each dataset.
        for dataset in valid_datasets:
            df_dataset = df_fov[df_fov["dataset"] == dataset]
            if df_dataset.empty:
                print(f"No FOV Mask data available for dataset {dataset}.")
                continue
            
            # Calculate average and std for fov_width.
            avg_fov_width = df_dataset["fov_width"].mean()
            std_fov_width = df_dataset["fov_width"].std()
            
            # Create a LaTeX table with the calculated values.
            latex_table = (
                "\\begin{tabular}{ll}\n"
                f"Dataset & {dataset} \\\\\n"
                f"Average FOV Width & {avg_fov_width:.3f} \\\\\n"
                f"Std Dev & {std_fov_width:.3f} \\\\\n"
                "\\end{tabular}"
            )
            print(f"\nLaTeX Table for FOV Width for {dataset}:")
            print(latex_table)
            
            # Plot fov_width over time.
            plt.figure()
            plt.plot(df_dataset["cellmanager_timestamp"], df_dataset["fov_width"], 'o-', label="FOV Width")
            plt.xlabel("Timestamp")
            plt.ylabel("FOV Mask Width (cells)")
            plt.title(f"FOV Mask Width over Time for {dataset}")
            plt.legend()
            plt.grid(True)
            if save_plots:
                filename = f"{dataset}_fov_mask_width.png"
                plt.savefig(filename)
                plt.close()
                print(f"Saved plot to {filename}")
            else:
                plt.show()

if __name__ == "__main__":
    main()
