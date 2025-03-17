#!/usr/bin/env python3
import os
import sys
import re
import subprocess

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 script.py <dataset_platform_path> <ORBSLAM3_evaluation_path>")
        sys.exit(1)

    platform_path = sys.argv[1]
    orbslam3_evaluation_path = sys.argv[2]

    # A mapping from the directory's run type to the f_dataset file's run type.
    # Replace/extend these with your actual mapping.
    run_mapping = {
        "stereo_inertial_deadlines": "stereo_imu",
        # Add other mappings as needed...
    }

    # Ensure that the processed output folder exists.
    processed_dir = os.path.join(os.getcwd(), "processed")
    os.makedirs(processed_dir, exist_ok=True)

    # Define a regex pattern to match directory names.
    # Expected format: <date>_result_<type of run>_<dataset>_#_run_<trial number>
    # Example: 2025-02-28_09-03-34_result_stereo_inertial_deadlines_MH01_0_run_1
    pattern = re.compile(
        r'^(?P<date>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_result_(?P<run_type>[^_]+(?:_[^_]+)*)_(?P<dataset>[^_]+)_\d+_run_(?P<trial>\d+)$'
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
        run_type_dir = match.group("run_type")
        dataset = match.group("dataset")
        trial = match.group("trial")

        # Map the run type from directory to file run type.
        if run_type_dir in run_mapping:
            run_type_file = run_mapping[run_type_dir]
        else:
            #print(f"Warning: No mapping found for run type '{run_type_dir}' in directory '{item}'. Skipping.")
            continue

        # Construct the expected f_dataset file name
        expected_filename = f"f_dataset-{dataset}_{run_type_file}.txt"
        file_path = os.path.join(dir_path, expected_filename)

        if not os.path.exists(file_path):
            print(f"File not found: {file_path}. Skipping directory '{item}'.")
            continue

        # Construct the ground truth file path based on the dataset.
        ground_truth_file = os.path.join(orbslam3_evaluation_path, "Ground_truth", "EuRoC_left_cam", f"{dataset}_GT.txt")

        # Execute the analysis script using the f_dataset file.
        cmd = ["python3", ground_truth_file, file_path, '--verbose']
        print(f"Processing: {file_path}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error processing {file_path}: {e}")
            continue

        # Write the output to the processed folder with the specified naming convention.
        output_filename = f"{dataset}_{run_type_file}_trial_{trial}.txt"
        output_filepath = os.path.join(processed_dir, output_filename)
        # with open(output_filepath, "w") as f_out:
        #     f_out.write(output)
        print(f"Output written to: {output_filepath}")

if __name__ == "__main__":
    main()
