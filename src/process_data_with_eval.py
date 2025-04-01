#!/usr/bin/env python3
import os
import sys
import re
import subprocess
from decimal import Decimal

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 script.py <dataset_platform_path> <ORBSLAM3_evaluation_path>")
        sys.exit(1)

    platform_path = sys.argv[1]
    orbslam3_evaluation_path = sys.argv[2]

    # A mapping from the directory's run type to the f_dataset file's run type.
    # Replace/extend these with your actual mapping.
    sensor_mapping = {
        "stereo_inertial": "stereo_imu",
        # Add other mappings as needed...
    }

    # Ensure that the processed output folder exists.
    processed_dir = os.path.join(os.getcwd(), "processed")
    os.makedirs(processed_dir, exist_ok=True)

    # Define a regex pattern to match directory names.
    # Expected format: <date>_result_<sensor_config>_<type_of_run>_<dataset>_<mask_size>_run_<trial_number>
    # Example: 2025-03-23_07-13-40_result_stereo_inertial_fov_deadlines_MH05_6_run_3
    pattern = re.compile(
        r'^(?P<date>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_result_'
        r'(?P<sensor_config>[^_]+_[^_]+)_'
        r'(?P<type_of_run>.+?)_'
        r'(?P<dataset>[^_]+)_'
        r'(?P<mask_size>\d+)_run_'
        r'(?P<trial_number>\d+)$'
    )

    # Iterate through all items in the platform path
    for item in os.listdir(platform_path):
        dir_path = os.path.join(platform_path, item)
        if not os.path.isdir(dir_path):
            continue

        match = pattern.match(item)
        if not match:
            print(f"Skipping directory (pattern not matched): {item}")
            continue

        date = match.group("date")
        sensor_config = match.group("sensor_config")
        run_type = match.group("type_of_run")
        dataset = match.group("dataset")
        mask_size = match.group("mask_size")
        trial = match.group("trial_number")

        # Map the run type from directory to file run type.
        if sensor_config in sensor_mapping:
            sensor_type_frame_file = sensor_mapping[sensor_config]
        else:
            # Uncomment below line if you want a warning
            print(f"Warning: No mapping found for run type '{sensor_config}' in directory '{item}'. Skipping.")
            continue

        # Construct the expected f_dataset file name
        expected_filename = f"f_dataset-{dataset}_{sensor_type_frame_file}.txt"
        file_path = os.path.join(dir_path, expected_filename)

        if not os.path.exists(file_path):
            print(f"File not found: {file_path}. Skipping directory '{item}'.")
            continue

        # Construct the ground truth file path based on the dataset.
        ground_truth_file = os.path.join(orbslam3_evaluation_path, "Ground_truth", "EuRoC_left_cam", f"{dataset}_GT.txt")
        analysis_script = os.path.join(orbslam3_evaluation_path, "evaluate_ate_scale.py")

        # Execute the analysis script using the f_dataset file.
        cmd = ["python3", analysis_script, ground_truth_file, file_path, '--verbose']
        print(f"Processing: {file_path}")
        try:
            print(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error processing {file_path}: {e}")
            continue

        # Write the output to the processed folder with the specified naming convention.
        if(mask_size != "0"):
            # we have a mask size to use
            output_filename = f"{platform_path}_{dataset}_{run_type}_{sensor_type_frame_file}_{trial}_{mask_size}.txt"
            output_filepath = os.path.join(processed_dir, output_filename)
            with open(output_filepath, "w") as f_out:
                f_out.write(output)
            print(f"Output written to: {output_filepath}")

        else:
            # no mask size
            output_filename = f"{platform_path}_{dataset}_{run_type}_{sensor_type_frame_file}_{trial}.txt"
            output_filepath = os.path.join(processed_dir, output_filename)
            with open(output_filepath, "w") as f_out:
                f_out.write(output)
            print(f"Output written to: {output_filepath}")

        # Now, search for the ExecMean.txt file in the current directory (dir_path)
        execmean_file = os.path.join(dir_path, "ExecMean.txt")
        if os.path.exists(execmean_file):
            with open(execmean_file, "r") as f_exec:
                exec_content = f_exec.read()
            # Extract KFs and MPs using regex
            kfs_match = re.search(r'KFs in map:\s*(\d+)', exec_content)
            mps_match = re.search(r'MPs in map:\s*(\d+)', exec_content)
            if kfs_match and mps_match:
                kfs_value = kfs_match.group(1)
                mps_value = mps_match.group(1)
                # Append the extracted lines to the output file
                with open(output_filepath, "a") as f_out:
                    f_out.write("\nMap complexity\n")
                    f_out.write(f"KFs in map: {kfs_value}\n")
                    f_out.write(f"MPs in map: {mps_value}\n")
                print(f"Appended ExecMean info from {execmean_file} to {output_filepath}")
            else:
                print("Could not extract KFs and/or MPs from ExecMean.txt")

            total_tracking_match = re.search(r'Total Tracking:\s*([\d.]+)\$\\pm\$([\d.]+)', exec_content)
            if total_tracking_match:
                total_tracking_avg = total_tracking_match.group(1)
                total_tracking_std = total_tracking_match.group(2)
                # Append the Total Tracking info to the output file
                with open(output_filepath, "a") as f_out:
                    f_out.write("\nTotal Tracking Analysis:\n")
                    f_out.write(f"Average Time: {total_tracking_avg}\n")
                    f_out.write(f"Std Dev: {total_tracking_std}\n")
                print(f"Appended Total Tracking info from {execmean_file} to {output_filepath}")
            else:
                print("Could not extract Total Tracking info from ExecMean.txt")
        else:
            print(f"ExecMean.txt not found in directory: {dir_path}")

         # Process cellManager.txt file for FOV Mask changes.
        cell_manager_file = os.path.join(dir_path, "cellManager.txt")
        if os.path.exists(cell_manager_file):

            def read_cell_manager_file(filename):
                """
                Parse the cellManager file to extract frame timestamps and FOV Mask dimensions.
                
                The file is expected to contain blocks like:
                
                    Frame 1.403640123456e+09 finished in 62.8161 ms stats:
                    ...
                    FOV Mask: 22x22
                
                This function reads the entire file and uses a regex to capture all such blocks.
                
                Returns:
                    tuple: Three lists containing timestamps, FOV mask widths, and FOV mask heights.
                """
                with open(filename, 'r') as f:
                    content = f.read()
                # Regex pattern captures:
                #  - The timestamp (with high precision) after "Frame"
                #  - And later the FOV Mask dimensions.
                pattern = r'Frame\s+([\d\.eE\+\-]+)\s+finished\s+in\s+[\d\.]+\s+ms\s+stats:.*?FOV Mask:\s*(\d+)\s*x\s*(\d+)'
                matches = re.findall(pattern, content, flags=re.DOTALL)
                timestamps = []
                fov_widths = []
                fov_heights = []
                for timestamp_str, width_str, height_str in matches:
                    try:
                        ts = float(Decimal(timestamp_str))
                    except Exception:
                        ts = float(timestamp_str)
                    timestamps.append(ts)
                    fov_widths.append(int(width_str))
                    fov_heights.append(int(height_str))
                return timestamps, fov_widths, fov_heights

            # Process cellManager.txt file for FOV Mask data.
            cell_manager_file = os.path.join(dir_path, "cellManager.txt")
            if os.path.exists(cell_manager_file):
                try:
                    timestamps, fov_widths, fov_heights = read_cell_manager_file(cell_manager_file)
                    with open(output_filepath, "a") as f_out:
                        f_out.write("\nFOV Mask Data from cellManager.txt:\n")
                        for ts, width, height in zip(timestamps, fov_widths, fov_heights):
                            f_out.write(f"Time: {ts}, FOV Mask: {width}x{height}\n")
                    print(f"Appended cellManager FOV Mask data from {cell_manager_file} to {output_filepath}")
                except Exception as e:
                    print(f"Error processing {cell_manager_file}: {e}")
            else:
                print(f"cellManager.txt not found in directory: {dir_path}")

if __name__ == "__main__":
    main()
