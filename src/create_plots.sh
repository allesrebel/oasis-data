#!/bin/bash
# Base directories and device-specific timestamps
BASE_DIR=~/oasis-data
TIMESTAMP_JETSON="2025-02-28_10-53-19_result_stereo_inertial"
TIMESTAMP_INTEL="2025-02-28_01-04-05_result_stereo_inertial"

# Declare an associative array with path templates (using {scene} as placeholder)
declare -A path_templates
path_templates[jetson_deadlines]="${BASE_DIR}/jetson/${TIMESTAMP_JETSON}_deadlines_{scene}_0_run_1/f_dataset-{scene}_stereo_imu.txt"
path_templates[jetson_normal]="${BASE_DIR}/jetson/${TIMESTAMP_JETSON}_normal_{scene}_0_run_1/f_dataset-{scene}_stereo_imu.txt"
path_templates[jetson_oasis]="${BASE_DIR}/jetson/${TIMESTAMP_JETSON}_oasis_{scene}_0_run_1/f_dataset-{scene}_stereo_imu.txt"
path_templates[intel_deadlines]="${BASE_DIR}/intel/${TIMESTAMP_INTEL}_deadlines_{scene}_0_run_1/f_dataset-{scene}_stereo_imu.txt"
path_templates[intel_normal]="${BASE_DIR}/intel/${TIMESTAMP_INTEL}_normal_{scene}_0_run_1/f_dataset-{scene}_stereo_imu.txt"
path_templates[intel_oasis]="${BASE_DIR}/intel/${TIMESTAMP_INTEL}_oasis_{scene}_0_run_1/f_dataset-{scene}_stereo_imu.txt"

# List of scenes and devices
scenes=("MH01" "MH02" "MH03" "MH04" "MH05")
devices=("jetson" ) #"intel")

for scene in "${scenes[@]}"; do
    gt="Ground_truth/EuRoC_left_cam/${scene}_GT.txt"
    for device in "${devices[@]}"; do
        # Replace {scene} placeholder with the current scene in each template
        deadlines="${path_templates[${device}_deadlines]//\{scene\}/$scene}"
        normal="${path_templates[${device}_normal]//\{scene\}/$scene}"
        oasis="${path_templates[${device}_oasis]//\{scene\}/$scene}"
        
        # Set a friendly device title (capitalize first letter)
        if [ "$device" == "jetson" ]; then
            devTitle="Jetson"
        else
            devTitle="Intel"
        fi

        # Error over time plots comparing deadlines and oasis against normal
        python3 evaluate_error_over_time.py --plot "${scene,,}_normal_vs_deadlines_${device}.png" "$gt" "$deadlines" "$normal" --ymax 0.25 --title "${scene} Error Over Time (${devTitle})"
        python3 evaluate_error_over_time.py --plot "${scene,,}_deadlines_vs_oasis_${device}.png" "$gt" "$oasis" "$deadlines" --ymax 0.25 --title "${scene} Error Over Time (${devTitle})"
        python3 evaluate_error_over_time.py --plot "${scene,,}_normal_vs_oasis_${device}.png" "$gt" "$oasis" "$normal" --ymax 0.25 --title "${scene} Error Over Time (${devTitle})"

        # For the "all" plot, metrics are taken from the deadlines folder
        # and cellManager is taken from the oasis folder.
        deadlines_dir=$(dirname "$deadlines")
        oasis_dir=$(dirname "$oasis")
        python3 evaluate_error_over_time.py --plot "${scene,,}_all_${device}.png" "$gt" "$oasis" "$deadlines" "$normal" --ymax 0.25 --title "${scene} Error Over Time (${devTitle})" --metrics_file "${deadlines_dir}/TrackingTimeStats.txt" --cellManager "${oasis_dir}/cellManager.txt" --cellManager_plot "${scene,,}_${device}_cellManager.png"
        
        # Evaluate absolute trajectory error (ATE) scale for each variant
        for variant in deadlines normal oasis; do
            echo "${device^^} ${scene} ${variant^^}"
            case $variant in
                deadlines)
                    file_to_use="$deadlines"
                    ;;
                normal)
                    file_to_use="$normal"
                    ;;
                oasis)
                    file_to_use="$oasis"
                    ;;
            esac
            python3 evaluate_ate_scale.py --verbose "$gt" "$file_to_use"
        done
        
    done
done
