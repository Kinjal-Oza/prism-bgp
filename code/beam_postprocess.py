"""BEAM's official alarm post-processing (post_processor/alarm_postprocess_routeviews.py + summary_routeviews.py) on the
alarms of one detection run (beam_detect.py output attached as a Kaggle kernel source). Pre-registered as part of the
BEAM pipeline (addendum 1eba976). Code unchanged; only paths are set, and two data-availability fallbacks are added and
logged: a missing RPKI ROA archive for a trust anchor is treated as having no ROAs, and an unreachable RADB archive as an
empty IRR. Whois lookups are current (BEAM's code does not use historical whois).
Env: CASE, TAG, SNAP.
"""
import os, sys, glob, json, shutil, subprocess, tarfile, io, socket
socket.setdefaulttimeout(180)   # FTP/HTTP fetches must not hang forever
from datetime import datetime
W = os.environ.get("WDIR", "/kaggle/working"); CASE = os.environ["CASE"]; TAG = os.environ["TAG"]
REPO = f"{W}/beam"; COLL = "route-views2"
def sh(c): print("+", c, flush=True); subprocess.run(c, shell=True, check=True)
import pandas as pd
if int(pd.__version__.split(".")[0]) >= 3:
    sh("pip install -q 'pandas==2.2.3'"); os.execv(sys.executable, [sys.executable] + sys.argv)
if not os.path.isdir(REPO):
    sh(f"git clone -q https://github.com/yhchen-tsinghua/routing-anomaly-detection {REPO} && cd {REPO} && git checkout -q ce75a16ba80d8b5deec1f9a675d3b0666b383771")
subprocess.run("command -v whois >/dev/null || (apt-get -qq update && apt-get -qq install -y whois >/dev/null)", shell=True)

info_f = glob.glob(os.environ.get("IN_GLOB", "/kaggle/input/**/") + f"beam_{CASE}_{TAG}_info.json", recursive=True)[0]
tgz = os.path.join(os.path.dirname(info_f), f"out_{CASE}_{TAG}.tgz")
info = json.load(open(info_f))
res = f"{REPO}/routing_monitor/detection_result/{COLL}"
with tarfile.open(tgz) as t:
    for m in t.getmembers():
        if m.name.endswith(".alarms.csv"):
            ym = os.path.basename(m.name)[:6]; d = f"{res}/reported_alarms/{ym}"; os.makedirs(d, exist_ok=True)
            with open(f"{d}/{os.path.basename(m.name)}", "wb") as f: f.write(t.extractfile(m).read())
months = {}
for x in info["infos"]:
    if not (x["kept"] and x.get("save_path")): continue
    ym = x["d1"][:6]; x = dict(x); x["save_path"] = f"{res}/reported_alarms/{ym}/{os.path.basename(x['save_path'])}"
    months.setdefault(ym, []).append(x)
for ym, xs in months.items(): json.dump(xs, open(f"{res}/reported_alarms/{ym}/info_{ym}.json", "w"), indent=1)
print("months", {k: len(v) for k, v in months.items()}, flush=True)

sys.path.insert(0, f"{REPO}/post_processor"); sys.path.insert(0, f"{REPO}/anomaly_detector"); sys.path.insert(0, REPO)
import rpki_validator as RV, irr_validator as IV
fallbacks = []
_fx = RV.fetch_and_uncompress_xz
def fx(url, out):
    p = _fx(url, out)
    if p is None:
        fallbacks.append(f"rpki missing: {url}"); out.write_text("URI,ASN,IP Prefix,Max Length,Not Before,Not After\n"); p = out
    return p
RV.fetch_and_uncompress_xz = fx
_sc = RV.sync_cache
def sc(y, m, d, source="https://ftp.ripe.net/rpki"):   # ROAs without maxLength: RFC 6482 default = prefix length
    df = _sc(y, m, d, source); miss = df["Max Length"].isna()
    if miss.any():
        df.loc[miss, "Max Length"] = df.loc[miss, "IP Prefix"].str.split("/").str[-1].astype(int)
        fallbacks.append(f"rpki {y}{m:02d}{d:02d}: {int(miss.sum())} ROAs without maxLength set to prefix length")
    return df
RV.sync_cache = sc
_fg = IV.fetch_and_uncompress_gz
def fg(y, m, d, domain="ftp.radb.net"):
    try: return _fg(y, m, d, domain)
    except Exception as e:
        out = IV.cache_dir / f"radb-{y}{m:02d}{d:02d}.db"; out.write_text(""); fallbacks.append(f"radb unavailable {y}{m:02d}{d:02d}: {e}"); return out
IV.fetch_and_uncompress_gz = fg
import whois_lookup as WL
_ok = subprocess.run("timeout 30 whois 8.8.8.0/24 | grep -qi google", shell=True).returncode == 0
print("whois reachable:", _ok, flush=True)
if not _ok: fallbacks.append("whois unreachable: whois_match treated as no match")
def wl(target, cache_date=WL.datetime.now().strftime("%Y-%m-%d")):   # same as BEAM's, plus a 30-s timeout
    cf = WL.cache_dir / f"{target.replace('/', '_')}.{cache_date}.txt"
    if cf.exists(): return cf.read_text(encoding="utf-8")
    if not _ok: return ""
    try:
        r = subprocess.run(["whois", target], text=True, capture_output=True, check=True, timeout=30)
        cf.write_text(r.stdout, encoding="utf-8"); return r.stdout
    except Exception as e:
        print(f"Failed to perform WHOIS lookup for {target}: {e}"); return ""
WL.whois_lookup = wl
import alarm_postprocess_routeviews as AP, summary_routeviews as SR
out = {}
for ym in sorted(months):
    y, m = int(ym[:4]), int(ym[4:])
    AP.postprocess.callback(COLL, y, m)
    try: SR.main.callback(COLL, y, m)
    except Exception as e: print("summary html/jsonl step failed after the alarm table was written:", repr(e), flush=True)
    f = f"{REPO}/post_processor/summary_output/alarms_after_post_process_{COLL}_{ym}.csv"
    if os.path.exists(f): shutil.copy(f, f"{W}/pp_{CASE}_{TAG}_{ym}.csv")
json.dump(dict(fallbacks=fallbacks, months=list(months)), open(f"{W}/pp_{CASE}_{TAG}_info.json", "w"), indent=1)
sh(f"rm -rf {REPO}"); print("DONE", flush=True)
