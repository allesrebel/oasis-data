#!/usr/bin/env python3
"""
postprocess_ate_results.py — collect ATE logs, build summary tables & plots.

• Works with both “old” and “new” evaluator file-name styles.
• No hard-coded platform / sensor / run-type / dataset filters:
  every unique value present in the logs is included.
"""
# ─────────────────────────────────────────────────────────────────────────────
import os, sys, re
import pandas as pd
import matplotlib.pyplot as plt

# ───────────────────────── helper extractors ────────────────────────────────
def _scan_for(prefix, path, cast):
    with open(path) as fh:
        for ln in fh:
            if ln.startswith(prefix):
                try:   return cast(ln.split()[1])
                except Exception:   return None
    return None

def extract_max(path):   return _scan_for("absolute_translational_error.max",   path, float)
def extract_mean(path):  return _scan_for("absolute_translational_error.mean",  path, float)

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
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 postprocess_ate_results.py <log_dir> [save] [show]")
        sys.exit(1)

    log_dir, save_plots = sys.argv[1], len(sys.argv) > 2 and sys.argv[2].lower()=="save"
    show_plots = len(sys.argv) > 3 and sys.argv[3].lower()=="show"
    rows, rows_fov = [], []

    for fname in os.listdir(log_dir):
        path = os.path.join(log_dir, fname)
        m = primary.match(fname) or fallback.match(fname)
        if not m:
            print(f"skip: {fname} (unmatched)"); continue
        g = m.groupdict()
        g["sensor_type"] = g.get("sensor_type") or DEFAULT_SENSOR

        max_e = extract_max(path)
        mean_e= extract_mean(path)
        if max_e is None:
            print(f"ATE max missing in {fname}"); continue

        comp = extract_complexity(path)
        time = extract_timing(path)

        rows.append({
            "platform":g["platform"], "dataset":g["dataset"], "run_type":g["run_type"],
            "sensor_type":g["sensor_type"], "trial":g["trial"],
            "mask_size":g.get("mask_size"),
            "absolute_translational_error.max":max_e,
            "absolute_translational_error.mean":mean_e,
            "KFs in map":comp["KFs in map"], "MPs in map":comp["MPs in map"],
            "Average Time":time["Average Time"], "Std Dev":time["Std Dev"]
        })

        for ts,w,h in extract_fov_mask(path):
            rows_fov.append({**{k:g[k] for k in ["platform","dataset","run_type",
                                                 "sensor_type","trial","mask_size"]},
                             "cellmanager_timestamp":ts,"fov_width":w,"fov_height":h})

    df, df_fov = pd.DataFrame(rows), pd.DataFrame(rows_fov)

    # ───────── summary tables for every platform / sensor / run_type ───────
    for (plat,sens), sub in df.groupby(["platform","sensor_type"]):
        for rtype in sub["run_type"].unique():
            run = sub[sub["run_type"]==rtype]
            print(f"\n── {plat} / {sens} / {rtype} ──")
            gmax  = run.groupby("dataset")["absolute_translational_error.max"].mean()
            gmean = run.groupby("dataset")["absolute_translational_error.mean"].mean()
            for d,v in gmax.items():  print(f"{d}: avg max = {v:.3f} m")
            for d,v in gmean.items(): print(f"{d}: avg mean = {v:.3f} m")

    # ───────── mask-size-dependent plots (all datasets present) ────────────
    df_mask = df[df["mask_size"].notnull()].copy()
    if not df_mask.empty:
        df_mask["mask_size"] = df_mask["mask_size"].astype(int)
        for dataset in df_mask["dataset"].unique():
            dset = df_mask[df_mask["dataset"]==dataset]

            # -------- mean error vs mask size --------------------------------
            plt.figure()
            plt.scatter(dset["mask_size"], dset["absolute_translational_error.mean"])
            grp = dset.groupby("mask_size")["absolute_translational_error.mean"].agg(["mean","std"]).reset_index()
            plt.errorbar(grp["mask_size"], grp["mean"], yerr=grp["std"],
                         fmt='-o', label="Mean ± STD")
            plt.title(f"ATE mean vs mask ({dataset})")
            plt.xlabel("Mask size (cells²)"); plt.ylabel("ATE mean (m)")
            plt.grid(True); plt.legend()
            if save_plots:
                fn = f"{dataset}_ate_mean_vs_mask.png"; plt.savefig(fn); plt.close()
                grp.to_csv(f"{dataset}_ate_mean_vs_mask.csv", index=False, float_format="%.6f")
                print(f"saved {fn}")
            else: plt.show() if show_plots else None

            # -------- max error vs mask size ---------------------------------
            plt.figure()
            plt.scatter(dset["mask_size"], dset["absolute_translational_error.max"])
            grp2 = dset.groupby("mask_size")["absolute_translational_error.max"].agg(["mean","std"]).reset_index()
            plt.errorbar(grp2["mask_size"], grp2["mean"], yerr=grp2["std"],
                         fmt='-o', label="Mean ± STD")
            plt.title(f"ATE max vs mask ({dataset})")
            plt.xlabel("Mask size (cells²)"); plt.ylabel("ATE max (m)")
            plt.grid(True); plt.legend()
            if save_plots:
                fn = f"{dataset}_ate_max_vs_mask.png"; plt.savefig(fn); plt.close()
                grp2.to_csv(f"{dataset}_ate_max_vs_mask.csv", index=False, float_format="%.6f")
                print(f"saved {fn}")
            else: plt.show() if show_plots else None

    # ───────── optional FOV-mask width plots (all datasets) ────────────────
    if not df_fov.empty:
        for dataset in df_fov["dataset"].unique():
            dset = df_fov[df_fov["dataset"]==dataset]
            plt.figure()
            plt.plot(dset["cellmanager_timestamp"], dset["fov_width"], 'o-')
            plt.title(f"FOV width over time ({dataset})")
            plt.xlabel("timestamp"); plt.ylabel("mask width (cells)")
            plt.grid(True)
            if save_plots:
                fn = f"{dataset}_fov_width.png"; plt.savefig(fn); plt.close()
                dset[["cellmanager_timestamp","fov_width"]].to_csv(
                    f"{dataset}_fov_width.csv", index=False, float_format="%.6f")
                print(f"saved {fn}")
            else: plt.show() if show_plots else None

if __name__ == "__main__":
    main()
