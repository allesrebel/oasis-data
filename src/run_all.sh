#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  EuRoC evaluation wrapper – auto-discovers specific stereo-inertial + SlimSLAM runs
#  2025-06-13
# -----------------------------------------------------------------------------
set -euo pipefail
shopt -s nullglob            # empty globs expand to 0 tokens

# ───────── USER SETTINGS ─────────
BASE_DIR="${HOME}/oasis-data"
scenes=(MH01 MH02 MH03 MH04 MH05 V101 V102 V103)
devices=(intel jetson)

# ───────── helper utilities ──────
first_match () {                      # safe even when called with 0 args
  local patt="${1:-}"; [[ -z $patt ]] && return
  compgen -G "$patt" | head -n1 || true
}

to_slim () {                          # MH01→MH_01,  V101→V1_01
  [[ $1 =~ ^MH([0-9]{2})$ ]]       && { printf "MH_%s"   "${BASH_REMATCH[1]}"; return; }
  [[ $1 =~ ^V([0-9])([0-9]{2})$ ]] && { printf "V%s_%s" "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"; return; }
  printf "%s" "$1"
}

get_traj () {                        # get_traj <run-dir> → f_… | kf_… | ""
  local f
  f=$(first_match "$1"/f_dataset-*) || true
  [[ -z $f ]] && f=$(first_match "$1"/kf_dataset-*) || true
  printf "%s" "$f"
}


# ─────────────── MAIN LOOP ───────────────
# The main loop is restructured to be explicit about what it's looking for.
# This avoids discovering the same run multiple times and ensures correct naming.
for scene in "${scenes[@]}"; do
  gt="Ground_truth/EuRoC_left_cam/${scene}_GT.txt"
  slim_scene=$(to_slim "$scene")

  for device in "${devices[@]}"; do
    devTitle="${device^}"                   # Intel / Jetson

    declare -A variant_map=()               # Map from final column name to trajectory file
    declare -a plot_order=()                # Preserve the desired plotting order

    # --- Define the EXACT variants to find and their directory glob patterns ---
    # This is the core of the new, reliable logic.
    # Format is "key_for_logic;glob_pattern_suffix"
    variants_to_find=(
        "normal;*_result_stereo_inertial_normal_${scene}_*_run_*"
        "deadlines;*_result_stereo_inertial_deadlines_${scene}_*_run_*"
        "oasis;*_result_stereo_inertial_oasis_${scene}_*_run_*"
        "normal_stress;*_result_stereo_inertial_normal_stress_${scene}_*_run_*"
        "oasis_stress;*_result_stereo_inertial_oasis_stress_${scene}_*_run_*"
        "fov;*_result_stereo_inertial_fov_${scene}_*_run_*"
        "fov_deadlines;*_result_stereo_inertial_fov_deadlines_${scene}_*_run_*"
        "omega;*_omega_${scene}_*_run_*"
        "omega_deadlines;*_omega_deadlines_${scene}_*_run_*"
        "pid;*_pid_${scene}_*_run_*"
        "pid_deadlines;*_pid_deadlines_${scene}_*_run_*"
        "fov_deadlines;*_result_stereo_inertial_fov_deadlines_${scene}_*_run_*"
        "slimslam;*_slimslam_${slim_scene}_*_run_*"
        "slimslam_deadlines;*_slimslam_deadlines_${slim_scene}_*_run_*"
    )

    echo "--- Processing ${device^^} for scene ${scene} ---"

    # --- Discover all unique FOV numbers from the directory names ---
    declare -A unique_fovs # Use an associative array to automatically handle uniqueness

    # Define a broad search pattern for directories that could contain an FOV number
    # The pattern looks for directories ending in _${scene}_[number]_run_
    fov_pattern="${BASE_DIR}/${device}/*_${scene}_*_run_*"

    echo "Searching for unique FOV variants in: ${fov_pattern}"

    # Loop over all directories that match the pattern
    for dir in $fov_pattern; do
        # Ensure it is a directory and extract the FOV number using the existing regex
        if [[ -d "$dir" && $(basename "$dir") =~ _${scene}_([0-9]+)_run_ ]]; then
            # The 'local' keyword was removed from the following line to fix the error
            fov_number="${BASH_REMATCH[1]}"
            # Add the number to our associative array; duplicates will be ignored
            unique_fovs["$fov_number"]=1
        fi
    done

    # --- Dynamically add the discovered FOV variants to the list ---
    # Now, iterate over the unique FOV numbers we found
    for fov in "${!unique_fovs[@]}"; do
        # For each number (e.g., 8), create the corresponding entries
        # that the main loop will process.
        variants_to_find+=("fov;*_${scene}_${fov}_run_*")
        variants_to_find+=("fov_deadlines;*_${scene}_${fov}_run_*")
    done

    # --- Discover runs for each specific variant ---
    # This is your original loop. It will now run on the expanded list
    # that includes all unique FOV variants found above.
    for item in "${variants_to_find[@]}"; do
        IFS=';' read -r variant_key glob_suffix <<< "$item"

        # Loop over all matching directories for the variant
        for dir in ${BASE_DIR}/${device}/${glob_suffix}; do
            # Check if the directory actually exists to handle cases where the glob finds no matches
            if [[ ! -d "$dir" ]]; then continue; fi

            # Try to get the trajectory file from the current directory
            traj=$(get_traj "$dir")

            # If a trajectory file is found, process it and break the inner loop
            if [[ -n "$traj" ]]; then
                # --- Determine the final column name ---
                final_column_name="$variant_key"
                # For 'fov' variants, extract the number (e.g., 8) and append it.
                # This part of your script already handles this perfectly.
                if [[ "$variant_key" == "fov" || "$variant_key" == "fov_deadlines" ]]; then
                    if [[ $(basename "$dir") =~ _${scene}_([0-9]+)_run_ ]]; then
                        final_column_name="${variant_key}_${BASH_REMATCH[1]}"
                    fi
                fi

                # Store the file path and the order, ensuring no duplicates.
                if [[ -z "${variant_map[$final_column_name]:-}" ]]; then
                    variant_map["$final_column_name"]=$traj
                    plot_order+=("$final_column_name")
                fi

                # A valid trajectory has been found for this variant, so we can stop searching.
                break
            fi
            # If no trajectory was found, the loop will automatically continue to the next matching directory.
        done
    done

    # --- Need at least the core runs to proceed ---
    if [[ -z "${variant_map[oasis]:-}" || -z "${variant_map[deadlines]:-}" || -z "${variant_map[normal]:-}" ]]; then
    echo "⚠️  Skipped: Missing one or more of [oasis, deadlines, normal]."
    
    # Find and print the missing keys
    missing_keys=()
    for key in oasis deadlines normal; do
        if [[ -z "${variant_map[${key}]:-}" ]]; then
        missing_keys+=("${key}")
        fi
    done
    echo "Missing: ${missing_keys[*]}"
    
    echo
    continue
    fi

    # --- Check if final output file already exists before running evaluation ---
    # This avoids re-running the expensive Python script.
    final_csv_check="${device}_${scene}_trajectory_errors_wide.csv"
    if [[ -f "$final_csv_check" ]]; then
        echo "✅ Skipped: Output file already exists ($final_csv_check)"
        echo
        continue
    fi

    # --- Build the final list of files in the correct order ---
    declare -a all_files=()
    for v in "${plot_order[@]}"; do
        all_files+=("${variant_map[$v]}")
    done

    # --- Generate a comma-separated list of final column names ---
    # This is the most important change: we explicitly tell the Python script what to name the columns.
    column_names=$(IFS=,; echo "${plot_order[*]}")

    # --- Evaluate error over time, passing explicit names ---
    eet_args=( "$gt" "${all_files[@]}" --trajectory_names "$column_names" --csv )

    echo "Running evaluation with explicit names: ${column_names}"
    python3 evaluate_error_over_time.py "${eet_args[@]}"
    
    # ---- rename ALL CSVs generated by evaluate_error_over_time -------
    for csv in trajectory_errors_wide.csv fov_mask_*.csv dropped_frames*.csv; do
        [ -f "$csv" ] && mv "$csv" "${device}_${scene}_${csv}"
    done

  done
done