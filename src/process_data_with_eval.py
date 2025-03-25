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

if __name__ == "__main__":
    main()
