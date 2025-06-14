#!/usr/bin/env python3
"""
generate_tables.py  –  collect ATE logs, build summary plots *and*
emit a professional-looking LaTeX table for the paper.

Minimal changes relative to the previous version:
• parse “Effective FPS Analysis” lines (frames, dropped, fps)
• store them in the dataframe
• aggregate {normal baseline vs oasis} and write table_results.tex
"""
# ─────────────────────────────────────────────────────────────────────────────
import os, sys, re, math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

TOTAL_FRAMES = {
    "MH01": 3682, "MH02": 3040, "MH03": 2700, "MH04": 2033, "MH05": 2273,
    "V101": 2912, "V102": 1710, "V103": 2149,
    "V201": 2280, "V202": 2348, "V203": 1922,
}

# ───────────────────────── helper extractors ────────────────────────────────
def _scan_for(prefix, path, cast):
    with open(path) as fh:
        for ln in fh:
            if ln.startswith(prefix):
                try:   return cast(ln.split()[1])
                except Exception:   return None
    return None

def extract_max(path):   return _scan_for("absolute_translational_error.max",  path, float)
def extract_mean(path):  return _scan_for("absolute_translational_error.mean", path, float)

def extract_complexity(path):
    return {"KFs in map": _scan_for("KFs in map:", path, int),
            "MPs in map": _scan_for("MPs in map:", path, int)}

def extract_timing(path):
    return {"Average Time": _scan_for("Average Time:", path, float),
            "Std Dev":      _scan_for("Std Dev:",      path, float)}

def extract_fov_mask(path):
    """Return list of (timestamp, w, h) tuples."""
    with open(path) as f: text = f.read()
    m = re.search(r'FOV Mask Data from cellManager\.txt:\s*\n(.*)', text, re.DOTALL)
    if not m: return []
    out = []
    for ln in m.group(1).splitlines():
        mm = re.match(r'Time:\s*([\d.eE\+\-]+),\s*FOV Mask:\s*(\d+)x(\d+)', ln)
        if mm:
            try:    ts = float(mm.group(1))
            except: ts = None
            out.append((ts, int(mm.group(2)), int(mm.group(3))))
    return out


# ─────────── NEW: canonical frame counts ────────────────────────────────────
TOTAL_FRAMES = {
    "MH01": 3682, "MH02": 3040, "MH03": 2700, "MH04": 2033, "MH05": 2273,
    "V101": 2912, "V102": 1710, "V103": 2149,
    "V201": 2280, "V202": 2348, "V203": 1922,
}

def extract_fps_block(path):
    """Parse the optional 'Effective FPS Analysis' block."""
    frames = drops = fps = None
    with open(path) as fh:
        for ln in fh:
            ln = ln.strip()
            if ln.startswith("Frames processed:"):
                try: frames = int(ln.split(":")[1].strip())
                except Exception: pass
            elif ln.startswith("Dropped frames:"):
                try: drops = int(ln.split(":")[1].strip())
                except Exception: pass
            elif ln.startswith("Effective FPS:"):
                try: fps = float(ln.split(":")[1].strip())
                except Exception: pass
    return frames, drops, fps

# ─────────────────────────── filename regexes ───────────────────────────────
primary = re.compile(  # legacy style (has sensor_type)
    r'^(?P<platform>[^_]+)_(?P<dataset>[^_]+)_(?P<run_type>.+?)_'
    r'(?P<sensor_type>[^_]+_[^_]+)_(?P<trial>\d+)(?:_(?P<mask_size>\d+))?'
    r'\.(?:txt|log|out)$')

fallback = re.compile( # new style (no sensor_type)
    r'^(?P<platform>[^_]+)_(?P<dataset>[^_]+)_(?P<run_type>.+?)_'
    r'(?P<trial>\d+)(?:_(?P<mask_size>\d+))?'
    r'\.(?:txt|log|out)$')

DEFAULT_SENSOR = "stereo_imu"
# ─────────────────────────────────────────────────────────────────────────────
def bold(val, cond):
    """Wrap val in \\textbf{} if cond is True."""
    return f"\\textbf{{{val}}}" if cond else val

# ───────────────────────── LaTeX generation (UPDATED) ───────────────────────
def produce_latex(df: pd.DataFrame, df_fov: pd.DataFrame,
                  baseline_tag="deadlines", oasis_tag="oasis",
                  out_file="table_results.tex") -> None:

    datasets = sorted(set(df["dataset"]))
    rows_tex, agg = [], {k: [] for k in (
        "bl_drop", "bl_drop_pct", "fps", "mask_mean", "mask_std",
        "ate_rt", "ate_oa", "amax_rt", "amax_oa", "imp_mean", "imp_max")}

    for d in datasets:
        base  = df[(df["dataset"] == d) & (df["run_type"] == baseline_tag)]
        oasis = df[(df["dataset"] == d) & (df["run_type"] == oasis_tag)]
        if base.empty or oasis.empty:
            continue

        total_frames = TOTAL_FRAMES.get(d)
        if total_frames is None:
            # Fallback to what we can infer if dataset not in lookup
            print(f'Falling Back! {d} not found')
            total_frames = base["frames_processed"].sum() + base["dropped_frames"].sum()

        frames_rt = base["frames_processed"].mean()
        frames_oa = oasis["frames_processed"].mean()

        drops_rt = base["dropped_frames"].mean()
        drops_oa = oasis["dropped_frames"].mean()
        drop_pct_rt = 100 * drops_rt / total_frames
        drop_pct_oa = 100 * drops_oa / total_frames

        fps_rt = base["effective_fps"].mean()

        ate_mean_rt = base["absolute_translational_error.mean"].mean()
        ate_mean_oa = oasis["absolute_translational_error.mean"].mean()
        ate_max_rt  = base["absolute_translational_error.max"].mean()
        ate_max_oa  = oasis["absolute_translational_error.max"].mean()

        imp_mean = (1 - ate_mean_oa / ate_mean_rt) * 100
        imp_max  = (1 - ate_max_oa  / ate_max_rt) * 100

        fov = df_fov[(df_fov["dataset"] == d) & (df_fov["run_type"] == oasis_tag)]
        m_mean, m_std = fov["fov_width"].mean(), fov["fov_width"].std()
        mask = "--" if np.isnan(m_mean) else f"${m_mean:.2f} \\pm {m_std:.2f}$"

        row_tex = (
            f"{d} & {total_frames} & "
            f"{drops_rt} ({drop_pct_rt:.2f}\\%) & {fps_rt:.2f} & "
            f"{mask} & {bold(f'{drops_oa} ({drop_pct_oa:.2f}\\%)', drops_oa < drops_rt)} & "
            f"{bold(f'{ate_mean_rt:.5f}', ate_mean_rt < ate_mean_oa)} & "
            f"{bold(f'{ate_mean_oa:.5f}', ate_mean_oa < ate_mean_rt)} & "
            f"{bold(f'{ate_max_rt:.5f}', ate_max_rt < ate_max_oa)} & "
            f"{bold(f'{ate_max_oa:.5f}', ate_max_oa < ate_max_rt)} & "
            f"{bold(f'{imp_mean:.1f}\\%', True)} & {bold(f'{imp_max:.1f}\\%', True)} \\\\"
        )
        rows_tex.append(row_tex)

        agg["bl_drop"].append(drops_rt)
        agg["bl_drop_pct"].append(drop_pct_rt)
        agg["fps"].append(fps_rt)
        if not np.isnan(m_mean):
            agg["mask_mean"].append(m_mean)
            agg["mask_std"].append(m_std)
        agg["ate_rt"].append(ate_mean_rt)
        agg["ate_oa"].append(ate_mean_oa)
        agg["amax_rt"].append(ate_max_rt)
        agg["amax_oa"].append(ate_max_oa)
        agg["imp_mean"].append(imp_mean)
        agg["imp_max"].append(imp_max)

    def avg(x): return float(np.mean(x)) if x else float('nan')
    avg_row = (
        f"\\textbf{{Average}} & -- & "
        f"{avg(agg['bl_drop']):.1f} ({avg(agg['bl_drop_pct']):.1f}\\%) & "
        f"{avg(agg['fps']):.2f} & "
        f"${avg(agg['mask_mean']):.2f} \\pm {avg(agg['mask_std']):.2f}$\" & "
        f"\\textbf{{0 (0.00\\%)}} & "
        f"{avg(agg['ate_rt']):.5f} & "
        f"\\textbf{{{avg(agg['ate_oa']):.5f}}} & "
        f"{avg(agg['amax_rt']):.5f} & "
        f"\\textbf{{{avg(agg['amax_oa']):.5f}}} & "
        f"\\textbf{{{avg(agg['imp_mean']):.1f}\\%}} & "
        f"\\textbf{{{avg(agg['imp_max']):.1f}\\%}} \\\\"
    )

    header = r"""\begin{table}[htbp]
\centering
\resizebox{\textwidth}{!}{%
\begin{tabular}{l|c|cc|cc|cc|cc|cc}
\hline
\multirow{2}{*}{\textbf{Dataset}} &
\multicolumn{3}{c|}{\textbf{Realtime Baseline}} &
\multicolumn{2}{c|}{\textbf{OASIS}} &
\multicolumn{2}{c|}{\textbf{Mean ATE (m)}} &
\multicolumn{2}{c|}{\textbf{Max ATE (m)}} &
\multicolumn{2}{c}{\textbf{Improvement (\%)}} \\
\cline{2-12}
 & \textbf{Frames} & \textbf{Dropped (\%)} & \textbf{FPS} &
 \textbf{Mask (Mean ± Std)} & \textbf{Dropped (\%)} &
 \textbf{Realtime} & \textbf{OASIS} &
 \textbf{Realtime} & \textbf{OASIS} &
 \textbf{Mean ATE} & \textbf{Max ATE} \\
\hline
"""
    footer = r"""\hline
\end{tabular}}
\caption{Comparison of Realtime Baseline (deadlines) and OASIS on EuRoC MAV datasets. Canonical frame counts are used to compute dropped-frame percentages; bold values denote better performance.}
\label{tab:super_table_results}
\end{table}
"""
    tex = header + "\n".join(rows_tex) + "\n\\hline\n" + avg_row + "\n\\hline\n" + footer
    with open(out_file, "w") as fh: 
        fh.write(tex)
        print(f"LaTeX table written to {out_file}")

# ─────────────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_tables.py <log_dir>  [save] [show]")
        sys.exit(1)

    log_dir, save_plots = sys.argv[1], len(sys.argv) > 2 and sys.argv[2].lower()=="save"
    show_plots = len(sys.argv) > 3 and sys.argv[3].lower()=="show"
    rows, rows_fov = [], []

    for fname in os.listdir(log_dir):
        path = os.path.join(log_dir, fname)
        m = primary.match(fname) or fallback.match(fname)
        if not m:
            continue
        g = m.groupdict()
        ## 
        # Use this to filter out and generate a table you want!
        # Filter out the data we don't want to consider for this table
        if g["platform"].lower() != "jetson":           # keep Jetson only
            continue
        if g["run_type"] not in {"deadlines", "oasis"}: # keep wanted configs
            continue
        g["sensor_type"] = g.get("sensor_type") or DEFAULT_SENSOR

        max_e = extract_max(path)
        mean_e= extract_mean(path)
        if max_e is None:
            continue

        print(f"✔ using {fname}")                       # ← NEW diagnostics line

        comp = extract_complexity(path)
        time = extract_timing(path)
        frames, drops, fps = extract_fps_block(path)

        rows.append({
            "platform":g["platform"], "dataset":g["dataset"], "run_type":g["run_type"],
            "sensor_type":g["sensor_type"], "trial":g["trial"],
            "mask_size":g.get("mask_size"),
            "absolute_translational_error.max":max_e,
            "absolute_translational_error.mean":mean_e,
            "KFs in map":comp["KFs in map"], "MPs in map":comp["MPs in map"],
            "Average Time":time["Average Time"], "Std Dev":time["Std Dev"],
            "frames_processed":frames, "dropped_frames":drops, "effective_fps":fps
        })

        for ts,w,h in extract_fov_mask(path):
            rows_fov.append({**{k:g[k] for k in ["platform","dataset","run_type",
                                                 "sensor_type","trial","mask_size"]},
                             "cellmanager_timestamp":ts,"fov_width":w,"fov_height":h})

    df, df_fov = pd.DataFrame(rows), pd.DataFrame(rows_fov)

    if not df_fov.empty:
        # --- iterate over all datasets that actually appear in the frame ---
        for dataset, df_dataset in df_fov.groupby("dataset", sort=True):
            if df_dataset.empty:        # shouldn’t occur, but keeps the old guard
                print(f"No FOV Mask data available for dataset {dataset}.")
                continue

            out_csv = f"{df_fov['platform'][0]}_{dataset}_fov_mask_width.csv"

            # 1. Order rows by timestamp so indices increase chronologically
            df_tmp = (
                df_dataset
                .sort_values("cellmanager_timestamp", kind="mergesort")  # stable sort
                .reset_index(drop=True)
            )

            # 2. Build a mapping:  timestamp  →  dense index (0,1,2,…)
            unique_ts = df_tmp["cellmanager_timestamp"].drop_duplicates()
            ts_to_idx = {ts: idx for idx, ts in enumerate(unique_ts)}

            # 3. Apply mapping to create the new column
            df_tmp.insert(0, "frame_index", df_tmp["cellmanager_timestamp"].map(ts_to_idx))

            # 4. Rename + export the three columns pgfplots needs
            (df_tmp
                .rename(columns={"cellmanager_timestamp": "timestamp"})
                .loc[:, ["frame_index", "timestamp", "fov_width"]]
                .to_csv(out_csv, index=False, float_format="%.6f")
            )

            print(f"Saved CSV to {out_csv}")

            out_csv_stats = f"{df_fov['platform'][0]}_{dataset}_fov_mask_width_stats.csv"

            # statistics for the cell manager
            df_stats = (
                df_tmp
                .groupby("frame_index")                       # collapse duplicates
                .agg(timestamp=("frame_index", "first"),        # identical within group
                    fov_mean =("fov_width", "mean"),
                    fov_std  =("fov_width", "std"))
                .reset_index(drop=True)                       # throw away frame_index
                .loc[:, ["timestamp", "fov_mean", "fov_std"]] # keep just these three
            )
            df_stats.to_csv(out_csv_stats, index=False, float_format="%3.3f")
            print(f"Saved stats CSV to {out_csv_stats}")

    # ───────── produce LaTeX table ─────────────────────────────────────────
    if not df.empty:
        produce_latex(df, df_fov)

if __name__ == "__main__":
    main()
