#!/usr/bin/env python3
"""
process_data_with_eval.py  (multiprocess edition)
─────────────────────────────────────────────────
Walk   ~/oasis-data/{intel,jetson}/**   → find run folders
Run   evaluate_ate_scale.py            → write summaries to ./processed/

It now uses all available CPU cores (or --workers N) to evaluate runs in
parallel.  The work is embarrassingly parallel because each run folder is
completely independent.

Usage
-----
    python3 process_data_with_eval.py <ORBSLAM3_evaluation_root> [--workers N]

Example
-------
    python3 process_data_with_eval.py ~/code/ORB-SLAM3-evaluation --workers 8
"""
from __future__ import annotations
import argparse, os, re, subprocess, sys
from decimal import Decimal
from functools import partial
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import NamedTuple


# ─────────────────────────────────────────────────────────────────────────
ROOT_DIR     = Path("~/oasis-data").expanduser()
ALLOWED_DEVS = {"intel", "jetson"}
PROCESSED    = Path.cwd() / "processed"
PROCESSED.mkdir(exist_ok=True)


# ────────────────────────── regex helpers ───────────────────────────────
SLIM_DIR_RE = re.compile(
    r'^(?P<date>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}).*?'
    r'(?P<run_type>slimslam(?:_deadlines)?)_'
    r'(?P<dataset>[A-Za-z0-9_]+)_'
    r'(?P<difficulty>[^_/]+)_run_(?P<trial>\d+)$'
)

OLD_DIR_RE = re.compile(
    r'^(?P<date>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_result_'
    r'(?P<sensor_config>[^_]+_[^_]+)_'
    r'(?P<run_type>.+?)_'
    r'(?P<dataset>[^_]+)_'
    r'(?P<mask_size>\d+)_run_'
    r'(?P<trial>\d+)$'
)


# ───────────────────────── data container ───────────────────────────────
class Task(NamedTuple):
    device:     str
    run_dir:    Path
    run_type:   str
    dataset:    str          # MH01 / V103 …
    dataset_raw:str          # MH_01 etc.
    mask_size:  str          # '0' for none
    trial:      str
    sensor_tag: str          # stereo_imu / slimslam_easy …
    traj_file:  Path
    gt_file:    Path
    analysis_py:Path


# ───────────────────────── helper fns ───────────────────────────────────
def first_traj_file(d: Path) -> Path | None:
    for patt in ("f_dataset-*.txt", "kf_dataset-*.txt"):
        files = sorted(d.glob(patt))
        if files:
            return files[0]
    return None


def normalise_dataset(raw: str) -> str:
    return raw.replace("_", "")


def discover_tasks(eval_root: Path) -> list[Task]:
    """Walk ~/oasis-data and return a list of Task objects ready for execution."""
    tasks: list[Task] = []
    analysis_py = eval_root / "evaluate_ate_scale.py"
    gt_root     = eval_root / "Ground_truth" / "EuRoC_left_cam"

    for device in ALLOWED_DEVS:
        dev_dir = ROOT_DIR / device
        if not dev_dir.is_dir():
            print(f"⚠️  {device} folder not found under {ROOT_DIR}")
            continue

        for dirpath, subdirs, _ in os.walk(dev_dir):
            run_dir = Path(dirpath)
            if run_dir == dev_dir:
                continue

            dname = run_dir.name
            m_old  = OLD_DIR_RE.match(dname)
            m_slim = None if m_old else SLIM_DIR_RE.match(dname)
            if not (m_old or m_slim):
                continue

            if m_old:
                g            = m_old.groupdict()
                run_type     = g["run_type"]
                dataset_raw  = g["dataset"]
                dataset      = normalise_dataset(dataset_raw)
                mask_size    = g["mask_size"]
                trial        = g["trial"]
                sensor_tag   = "stereo_imu"
                traj_file    = run_dir / f"f_dataset-{dataset_raw}_{sensor_tag}.txt"
                if not traj_file.exists():
                    continue
            else:
                g            = m_slim.groupdict()
                run_type     = g["run_type"]
                dataset_raw  = g["dataset"]
                dataset      = normalise_dataset(dataset_raw)
                mask_size    = "0"
                trial        = g["trial"]
                traj_file    = first_traj_file(run_dir)
                if not traj_file:
                    continue
                sensor_tag   = traj_file.stem.split(f"{dataset_raw}_", 1)[-1]

            gt_file = gt_root / f"{dataset}_GT.txt"
            if not gt_file.exists():
                continue

            tasks.append(Task(device, run_dir, run_type, dataset,
                              dataset_raw, mask_size, trial,
                              sensor_tag, traj_file, gt_file,
                              analysis_py))
    return tasks


def run_task(task: Task) -> str:
    """Execute evaluate_ate_scale.py for one run folder. Return a status line."""
    out_name = (
        f"{task.device}_{task.dataset}_{task.run_type}_{task.sensor_tag}_{task.trial}"
        + (f"_{task.mask_size}" if task.mask_size != '0' else "")
        + ".txt"
    )
    out_file = PROCESSED / out_name

    # Skip if output already exists (idempotent runs)
    if out_file.exists():
        return f"SKIP {out_name}"

    cmd = ["python3", str(task.analysis_py),
           str(task.gt_file), str(task.traj_file), "--verbose"]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        summary = res.stdout
    except subprocess.CalledProcessError as e:
        return f"FAIL {out_name}: {e}"

    # Write main summary --------------------------------------------------
    out_file.write_text(summary)

    # ExecMean parsing ----------------------------------------------------
    execmean = task.run_dir / "ExecMean.txt"
    if execmean.exists():
        text = execmean.read_text()
        kfs  = re.search(r"KFs in map:\s*(\d+)", text)
        mps  = re.search(r"MPs in map:\s*(\d+)", text)
        ttrk = re.search(r"Total Tracking:\s*([\d.]+)\$\\pm\$([\d.]+)", text)
        with out_file.open("a") as f:
            if kfs and mps:
                f.write("\nMap complexity\n")
                f.write(f"KFs in map: {kfs.group(1)}\n")
                f.write(f"MPs in map: {mps.group(1)}\n")
            if ttrk:
                f.write("\nTotal Tracking Analysis:\n")
                f.write(f"Average Time: {ttrk.group(1)}\n")
                f.write(f"Std Dev: {ttrk.group(2)}\n")

    # ───────── Effective-FPS + dropped-frame analysis (nominal-FPS method) ─────────
    tracking_stats = task.run_dir / "TrackingTimeStats.txt"
    NOMINAL_FPS   = 20.0                      # <<< change if your camera rate differs

    if tracking_stats.exists() and task.traj_file.exists():

        # ---------- helper ---------------------------------------------------
        def _parse_ns(ts_str: str):
            """Return nanosecond timestamp (int) or None on failure."""
            try:
                return int(ts_str.split(".")[0])
            except ValueError:
                return None

        # ---------- 1. last timestamp in f_*.txt -----------------------------
        last_ts = None
        with task.traj_file.open() as f_traj:
            for line in f_traj:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                ts = _parse_ns(line.split()[0])
                if ts is not None:
                    last_ts = ts                       # keep latest valid value

        if last_ts is None:
            print(f"[WARN] {task.traj_file} contained no numeric timestamps – skipping FPS calc")
        else:
            # ---------- 2. collect timestamps from TrackingTimeStats.txt -----
            ts_all = []
            with tracking_stats.open() as f_track:
                for row in f_track:
                    row = row.strip()
                    if not row or row.startswith("#"):
                        continue
                    ts = _parse_ns(row.split(",")[0])
                    if ts is not None:
                        ts_all.append(ts)

            if ts_all:
                # frames inside the valid time window
                frames_processed = sum(ts <= last_ts for ts in ts_all)
                dropped_frames  = len(ts_all) - frames_processed

                if frames_processed:
                    eff_fps = NOMINAL_FPS * frames_processed / (frames_processed + dropped_frames)

                    # ---------- 3. write results -----------------------------
                    with out_file.open("a") as f:
                        f.write("\nEffective FPS Analysis:\n")
                        f.write(f"Frames processed: {frames_processed}\n")
                        f.write(f"Dropped frames:   {dropped_frames}\n")
                        f.write(f"Nominal FPS:      {NOMINAL_FPS:.2f}\n")
                        f.write(f"Effective FPS:    {eff_fps:.2f}\n")
                else:
                    print(f"[WARN] No valid TrackingTimeStats rows ≤ {last_ts} for {task.run_dir}")

    # cellManager parsing -------------------------------------------------
    cm = task.run_dir / "cellManager.txt"
    if cm.exists():
        cm_pat = r"Frame\s+([\d\.eE+\-]+).*?FOV Mask:\s*(\d+)\s*x\s*(\d+)"
        matches = re.findall(cm_pat, cm.read_text(), flags=re.DOTALL)
        if matches:
            with out_file.open("a") as f:
                f.write("\nFOV Mask Data from cellManager.txt:\n")
                for ts_s, w, h in matches:
                    try:
                        ts = float(Decimal(ts_s))
                    except Exception:
                        ts = float(ts_s)
                    f.write(f"Time: {ts}, FOV Mask: {w}x{h}\n")

    return f"OK   {out_name}"


# ───────────────────────── entrypoint ────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("evaluation_root",
                    help="Path to ORB-SLAM3 evaluation repo (contains evaluate_ate_scale.py)")
    ap.add_argument("--workers", "-j", type=int, default=cpu_count(),
                    help="Number of parallel workers (default: all logical CPUs)")
    args = ap.parse_args()

    eval_root = Path(args.evaluation_root).expanduser().resolve()
    tasks     = discover_tasks(eval_root)
    if not tasks:
        sys.exit("No runnable folders found.")

    print(f"▶  {len(tasks)} run folders queued  •  {args.workers} workers\n")

    # Pool.map is safe because each task is independent and writes its own file
    with Pool(processes=args.workers) as pool:
        for status in pool.imap_unordered(run_task, tasks):
            print(status, flush=True)


if __name__ == "__main__":
    main()
