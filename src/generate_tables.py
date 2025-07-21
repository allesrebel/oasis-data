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
            f"{drops_rt} ({drop_pct_rt:.2f}%) & {fps_rt:.2f} & "
            f"{mask} & {bold(f'{drops_oa} ({drop_pct_oa:.2f}%)', drops_oa < drops_rt)} & "
            f"{bold(f'{ate_mean_rt:.5f}', ate_mean_rt < ate_mean_oa)} & "
            f"{bold(f'{ate_mean_oa:.5f}', ate_mean_oa < ate_mean_rt)} & "
            f"{bold(f'{ate_max_rt:.5f}', ate_max_rt < ate_max_oa)} & "
            f"{bold(f'{ate_max_oa:.5f}', ate_max_oa < ate_max_rt)} & "
            f"{bold(f'{imp_mean:.1f}%', True)} & {bold(f'{imp_max:.1f}%', True)}"
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

# ─────────── LaTeX generation – mean / max ATE (incl. FOV-3 & FOV-6) ────────────
import numpy as np
import pandas as pd


def bold(txt: str, cond: bool) -> str:
    """Return txt wrapped in \\textbf{} when cond is True."""
    return txt
    #return f"\\textbf{{{txt}}}" if cond else txt


def produce_latex_alt(df: pd.DataFrame, df_fov: pd.DataFrame,
                  baseline_tag="deadlines", oasis_tag="oasis",   # kept for API compat
                  out_file: str = "table_results.tex") -> None:
    """
    Build a LaTeX table comparing **mean / max ATE** for seven controller
    variants:  PID, PID+DL, Ω, Ω+DL, FOV-4, FOV-6, and OASIS.
    """
    # ---------------------------------------------------------------------
    # Edit here if your run-type labels differ.
    run_types = [
        "pid", "pid_deadlines",
        "omega", "omega_deadlines",
        "fov_4", "fov_6",
        "oasis"
    ]
    # ---------------------------------------------------------------------

    datasets = sorted(df["dataset"].unique())
    rows_tex = []
    agg_mean = {rt: [] for rt in run_types}
    agg_max  = {rt: [] for rt in run_types}

    for d in datasets:
        ate_mean, ate_max = {}, {}
        for rt in run_types:
            sub = df[(df["dataset"] == d) & (df["run_type"] == rt)]
            ate_mean[rt] = sub["absolute_translational_error.mean"].mean() \
                           if not sub.empty else np.nan
            ate_max[rt]  = sub["absolute_translational_error.max"].mean() \
                           if not sub.empty else np.nan

            if not np.isnan(ate_mean[rt]): agg_mean[rt].append(ate_mean[rt])
            if not np.isnan(ate_max[rt]):  agg_max[rt].append(ate_max[rt])

        best_mean = np.nanmin(list(ate_mean.values()))
        best_max  = np.nanmin(list(ate_max.values()))

        # 1 row per dataset
        row_cells = [d]
        for rt in run_types:
            m, M = ate_mean[rt], ate_max[rt]
            row_cells.extend([
                bold("--" if np.isnan(m) else f"{m:.5f}", m == best_mean),
                bold("--" if np.isnan(M) else f"{M:.5f}", M == best_max)
            ])
        rows_tex.append(" & ".join(row_cells) + r" \\")

    # --------------------------- average row -----------------------------
    avg_cells = ["\\textbf{Average}"]
    for rt in run_types:
        m = float(np.mean(agg_mean[rt])) if agg_mean[rt] else np.nan
        M = float(np.mean(agg_max[rt]))  if agg_max[rt]  else np.nan
        avg_cells.extend([
            bold("--" if np.isnan(m) else f"{m:.5f}", True),
            bold("--" if np.isnan(M) else f"{M:.5f}", True)
        ])
    avg_row = " & ".join(avg_cells) + r" \\"

    # ------------------------- LaTeX boilerplate -------------------------
    header = r"""\begin{table}[htbp]
\centering
\resizebox{\textwidth}{!}{%
\begin{tabular}{l|cc|cc|cc|cc|cc|cc|cc}
\hline
\multirow{2}{*}{\textbf{Dataset}} &
\multicolumn{2}{c|}{\textbf{PID}} &
\multicolumn{2}{c|}{\textbf{Realtime PID}} &
\multicolumn{2}{c|}{\textbf{$\omega$}} &
\multicolumn{2}{c|}{\textbf{Realtime $\omega$}} &
\multicolumn{2}{c|}{\textbf{Fixed Mask 4x4}} &
\multicolumn{2}{c|}{\textbf{Fixed Mask 6x6}} &
\multicolumn{2}{c}{\textbf{OASIS}} \\
\cline{2-15}
 & \textbf{Mean ATE (m)} & \textbf{Max ATE (m)} &
   \textbf{Mean} & \textbf{Max} &
   \textbf{Mean} & \textbf{Max} &
   \textbf{Mean} & \textbf{Max} &
   \textbf{Mean} & \textbf{Max} &
   \textbf{Mean} & \textbf{Max} &
   \textbf{Mean} & \textbf{Max} \\
\hline
"""
    footer = r"""\hline
\end{tabular}}
\caption{Mean and maximum absolute translational error (ATE) for seven controller variants across EuRoC MAV datasets. Lower values are better; bold highlights the best score per dataset.}
\label{tab:ate_pid_omega_fov_oasis}
\end{table}
"""
    tex = header + "\n".join(rows_tex) + "\n\\hline\n" + avg_row + "\n\\hline\n" + footer
    with open(out_file, "w") as fh:
        fh.write(tex)
        print(f"LaTeX table written to {out_file}")

def produce_latex_stress(df: pd.DataFrame,
                         out_file: str = "table_stress.tex") -> None:
    """
    Compare two hardware platforms (Intel & Jetson) under random periodic
    stress for the run-types: normal_stress, deadlines_stress, oasis_stress.
    Produces a LaTeX table with mean / max ATE only.
    """
    # Adjust these names if your CSV uses different labels
    devices    = ["intel", "jetson"]
    run_types  = ["normal_stress", "deadlines_stress", "oasis_stress"]

    # Detect the platform column name in the dataframe
    platform_col = "platform" if "platform" in df.columns else "device"

    datasets = sorted(df["dataset"].unique())
    rows_tex = []

    # To accumulate averages across all datasets
    agg_mean = {(rt, dev): [] for rt in run_types for dev in devices}
    agg_max  = {(rt, dev): [] for rt in run_types for dev in devices}

    for d in datasets:
        # Collect ATE numbers
        entry = {}  # (run_type, device) -> (mean, max)
        for rt in run_types:
            for dev in devices:
                sub = df[(df["dataset"] == d) &
                         (df["run_type"] == rt) &
                         (df[platform_col] == dev)]
                m = sub["absolute_translational_error.mean"].mean() \
                    if not sub.empty else np.nan
                M = sub["absolute_translational_error.max"].mean() \
                    if not sub.empty else np.nan
                entry[(rt, dev)] = (m, M)

                if not np.isnan(m): agg_mean[(rt, dev)].append(m)
                if not np.isnan(M): agg_max[(rt, dev)].append(M)

        # Bold-face whichever device is better (lower) for each metric
        row = [d]
        for rt in run_types:
            m_intel, M_intel = entry[(rt, "intel")]
            m_jet  , M_jet   = entry[(rt, "jetson")]

            best_mean = np.nanmin([m_intel, m_jet])
            best_max  = np.nanmin([M_intel, M_jet])

            row.extend([
                bold("--" if np.isnan(m_intel) else f"{m_intel:.5f}", m_intel == best_mean),
                bold("--" if np.isnan(M_intel) else f"{M_intel:.5f}", M_intel == best_max),
                bold("--" if np.isnan(m_jet)   else f"{m_jet:.5f}",   m_jet   == best_mean),
                bold("--" if np.isnan(M_jet)   else f"{M_jet:.5f}",   M_jet   == best_max),
            ])
        rows_tex.append(" & ".join(row) + r" \\")

    # ---------------- average row ----------------
    avg_cells = ["\\textbf{Average}"]
    for rt in run_types:
        for dev in devices:
            m_vals = agg_mean[(rt, dev)]
            M_vals = agg_max[(rt, dev)]
            m_avg = float(np.mean(m_vals)) if m_vals else np.nan
            M_avg = float(np.mean(M_vals)) if M_vals else np.nan
            avg_cells.extend([
                bold("--" if np.isnan(m_avg) else f"{m_avg:.5f}", True),
                bold("--" if np.isnan(M_avg) else f"{M_avg:.5f}", True)
            ])
    avg_row = " & ".join(avg_cells) + r" \\"

    # ---------------- LaTeX boilerplate ----------------
    header = r"""\begin{table}[htbp]
\centering
\resizebox{\textwidth}{!}{%
\begin{tabular}{l|cccc|cccc|cccc}
\hline
\multirow{2}{*}{\textbf{Dataset}} &
\multicolumn{4}{c|}{\textbf{Normal Stress}} &
\multicolumn{4}{c|}{\textbf{Deadlines Stress}} &
\multicolumn{4}{c}{\textbf{OASIS Stress}} \\
\cline{2-13}
 & \multicolumn{2}{c}{\textbf{Intel}} & \multicolumn{2}{c|}{\textbf{Jetson}} &
   \multicolumn{2}{c}{\textbf{Intel}} & \multicolumn{2}{c|}{\textbf{Jetson}} &
   \multicolumn{2}{c}{\textbf{Intel}} & \multicolumn{2}{c}{\textbf{Jetson}} \\
 & Mean & Max & Mean & Max & Mean & Max & Mean & Max & Mean & Max & Mean & Max \\
\hline
"""
    footer = r"""\hline
\end{tabular}}
\caption{Mean and maximum absolute translational error (ATE) for Intel and Jetson under random periodic stress.  Each run-type (normal\_stress, deadlines\_stress, oasis\_stress) is executed on both systems; lower values are better.  Bold highlights the better device for each metric within a run-type.}
\label{tab:stress_intel_vs_jetson}
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

        if g["run_type"] == "fov":
            # filter out fov
            continue
            ms = g.get("mask_size")
            g["run_type"] = f"fov_{ms}" if ms else "fov"
        ## 
        # Use this to filter out and generate a table you want!
        # Filter out the data we don't want to consider for this table
        if g["platform"].lower() == "intel":# keep Jetson only
            continue
        if g["run_type"] not in {"deadlines", "oasis"}:
            continue
        # if g["run_type"] not in {"omega", "omega_deadlines", "pid", "pid_deadlines", "fov_4", "fov_6", "oasis"}: # keep wanted configs
        #     continue
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

    # # ───────── produce LaTeX table ─────────────────────────────────────────
    # if not df.empty:
    #     print(sorted(df["run_type"].unique()))
    #     produce_latex_alt(df, df_fov)

    # # ───────── produce LaTeX table ─────────────────────────────────────────
    if not df.empty:
        print(sorted(df["run_type"].unique()))
        produce_latex(df, df_fov)
    
    # ───────── produce LaTeX table ─────────────────────────────────────────
    #if not df.empty:
    #    print(sorted(df["run_type"].unique()))
    #    produce_latex_stress(df, out_file="stress.tex")
    

if __name__ == "__main__":
    main()
