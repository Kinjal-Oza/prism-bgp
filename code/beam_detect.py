"""Run BEAM's official detection pipeline (routing monitor -> BEAM_diff_evaluator -> report_anomaly) for one incident,
as fixed in HELDOUT_PREREGISTRATION.md (addenda 1eba976 and f8a6bfd). Kaggle CPU session, internet on.

Env: CASE (e.g. GO2017), ONSET ("YYYY-mm-dd HH:MM", UTC), SNAP (CAIDA month of the model, e.g. 20170801), TAG (clean|poison).
The trained model (node.emb, link.emb, rela.emb) comes from an attached Kaggle kernel output.

What this driver does and does not change:
- It calls BEAM's own Monitor, load_updates_to_df, evaluate_monthly_for and report_alarm_monthly; their code is not changed.
- The monitor consumes every route-views2 update file from 7 days before the control window to the end of the test window
  (pre-registered fallback), starting empty as BEAM does. Each file is deleted after use.
- Route-change files are kept only for the hours the alarm step needs: hours overlapping the 12-h control window or the
  4-h test window, and the hour before each. report_anomaly compares each hourly bulk only with the previous one, so the
  alarms kept (pairs whose reference hour is exactly the previous hour) equal those of a full run.
"""
import os, sys, glob, json, shutil, subprocess, time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

W = os.environ.get("WDIR", "/kaggle/working"); TMP = "/kaggle/tmp" if os.path.isdir("/kaggle/tmp") else "/tmp"
CASE = os.environ["CASE"]; SNAP = os.environ["SNAP"]; TAG = os.environ.get("TAG", "clean")
T = datetime.strptime(os.environ["ONSET"], "%Y-%m-%d %H:%M")
C = T - timedelta(days=7)
TEST = (T - timedelta(hours=2), T + timedelta(hours=2)); CTL = (C - timedelta(hours=6), C + timedelta(hours=6))
START = CTL[0] - timedelta(days=7); END = TEST[1]
if os.environ.get("SMOKE"):   # local smoke test only
    TEST = CTL = (T - timedelta(hours=1), T); START = T - timedelta(hours=2); END = T
COLL = "route-views2"; URL = "http://archive.routeviews.org/bgpdata/"
REPO = f"{W}/beam"

def sh(c): print("+", c, flush=True); subprocess.run(c, shell=True, check=True)

# pandas >= 3 dropped an option BEAM's report step uses; keep 2.x (no algorithmic change)
import pandas as pd
if int(pd.__version__.split(".")[0]) >= 3:
    sh("pip install -q 'pandas==2.2.3'"); os.execv(sys.executable, [sys.executable] + sys.argv)

if not os.path.isdir(REPO):
    sh(f"git clone -q https://github.com/yhchen-tsinghua/routing-anomaly-detection {REPO} && cd {REPO} && git checkout -q ce75a16ba80d8b5deec1f9a675d3b0666b383771")
if not os.path.exists(f"{REPO}/data/routeviews/bgpd"):
    sh("(command -v autoreconf >/dev/null && dpkg -s libbz2-dev >/dev/null 2>&1) || (apt-get -qq update && apt-get -qq install -y autoconf automake libbz2-dev zlib1g-dev >/dev/null)")
    sh(f"cd {TMP} && rm -rf bgpdump && git clone -q --depth 1 https://github.com/RIPE-NCC/bgpdump.git && cd bgpdump && sh ./bootstrap.sh >/dev/null 2>&1 && make -j4 >/dev/null 2>&1 && ln -sf $(pwd)/bgpdump {REPO}/data/routeviews/bgpd")

# model from the attached training kernel
emb = glob.glob(os.environ.get("MODEL_GLOB", "/kaggle/input/**/node.emb"), recursive=True)
assert emb, "no trained BEAM model attached"
MODEL = f"{SNAP}.as-rel2.1000.10.128"
mdir = f"{REPO}/BEAM_engine/models/{MODEL}"; os.makedirs(mdir, exist_ok=True)
for f in ("node.emb", "link.emb", "rela.emb"): shutil.copy(os.path.join(os.path.dirname(emb[0]), f), mdir)
print("model", emb[0], "->", mdir, flush=True)

sys.path.insert(0, f"{REPO}/routing_monitor"); sys.path.insert(0, REPO)
from monitor import Monitor
from data.routeviews.fetch_updates import load_updates_to_df

res = f"{REPO}/routing_monitor/detection_result/{COLL}"; rcdir = f"{res}/route_change"; os.makedirs(rcdir, exist_ok=True)

def hours(a, b):
    h = a.replace(minute=0); out = []
    while h < b: out.append(h); h += timedelta(hours=1)
    return out
SCORED = sorted(set(hours(*TEST)) | set(hours(*CTL)))
NEEDED = set(SCORED) | {h - timedelta(hours=1) for h in SCORED}
print("scored hours", len(SCORED), "kept hours", len(NEEDED), "monitor", START, "->", END, flush=True)

# file list: 15-min update files whose start time is in [START, END)
files = []; t = START.replace(minute=START.minute - START.minute % 15)
while t < END: files.append(t); t += timedelta(minutes=15)

def fetch(t):
    name = f"updates.{t:%Y%m%d.%H%M}.bz2"; out = f"{TMP}/u/{name}"; os.makedirs(f"{TMP}/u", exist_ok=True)
    for k in range(5):
        r = subprocess.run(["curl", "-sf", "--retry", "3", "-o", out, f"{URL}{t:%Y.%m}/UPDATES/{name}"])
        if r.returncode == 0: break
        time.sleep(5)
    else:
        return t, None
    subprocess.run(["bzip2", "-df", out], check=True); return t, out[:-4]

def prefetched(ex, items, depth=12):   # bounded read-ahead, keeps disk use small
    q = [ex.submit(fetch, x) for x in items[:depth]]; k = depth
    while q:
        r = q.pop(0).result()
        if k < len(items): q.append(ex.submit(fetch, items[k])); k += 1
        yield r

mon = Monitor(); missing = []; t0 = time.time(); n_rc = 0
with ThreadPoolExecutor(max_workers=6) as ex:
    for i, (t, fp) in enumerate(prefetched(ex, files)):
        if fp is None: missing.append(f"{t:%Y%m%d.%H%M}"); continue
        df = load_updates_to_df(fp).sort_values(by="timestamp")   # same calls as BEAM's detect()
        mon.consume(df, detect=True)
        if t.replace(minute=0) in NEEDED:
            pd.DataFrame.from_records(mon.route_changes).to_csv(f"{rcdir}/{t:%Y%m%d.%H%M}.csv", index=False); n_rc += len(mon.route_changes)
        mon.route_changes = []
        os.remove(fp)
        if i % 96 == 0: print(f"{i}/{len(files)} {t} {time.time()-t0:.0f}s kept_rc={n_rc}", flush=True)
print("monitor done", time.time() - t0, "s; missing files", missing, flush=True)
json.dump(dict(missing=missing, files=len(files)), open(f"{W}/monitor_info.json", "w"))
del mon

sys.path.insert(0, f"{REPO}/anomaly_detector")
import BEAM_diff_evaluator_routeviews as EV, report_anomaly_routeviews as RA
months = sorted({(h.year, h.month) for h in NEEDED})
for y, m in months:
    EV.evaluate_monthly_for.callback(COLL, y, m, MODEL); print("evaluated", y, m, flush=True)
infos = []
for y, m in months:
    RA.report_alarm_monthly.callback(COLL, y, m)
    for x in json.load(open(f"{res}/reported_alarms/{y}{m:02d}/info_{y}{m:02d}.json")):
        d0, d1 = datetime.strptime(x["d0"], "%Y%m%d%H"), datetime.strptime(x["d1"], "%Y%m%d%H")
        x["kept"] = (d1 in SCORED and d0 == d1 - timedelta(hours=1)); infos.append(x)
json.dump(dict(case=CASE, tag=TAG, model=MODEL, onset=str(T), test=[str(a) for a in TEST], ctl=[str(a) for a in CTL],
               start=str(START), end=str(END), infos=infos), open(f"{W}/beam_{CASE}_{TAG}_info.json", "w"), indent=1)
# outputs: alarms of kept pairs, and route changes + BEAM metrics for scored hours (for the continuous metric)
out = f"{W}/out_{CASE}_{TAG}"; os.makedirs(out, exist_ok=True)
for x in infos:
    if x["kept"] and x.get("save_path"): shutil.copy(x["save_path"], out)
for h in SCORED:
    for f in glob.glob(f"{rcdir}/{h:%Y%m%d.%H}*.csv") + glob.glob(f"{res}/BEAM_metric/{h:%Y%m%d.%H}*.bm.csv"):
        shutil.copy(f, out)
sh(f"cd {W} && tar czf out_{CASE}_{TAG}.tgz out_{CASE}_{TAG} && rm -rf out_{CASE}_{TAG} {REPO}")
print("DONE", flush=True)
