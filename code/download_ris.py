"""Download RIPE RIS rrc00 bview + UPDATE files for one case (second collector). Run from the ris/ work dir.
bview: latest one at least 24 h before the test window; updates: every 5-min file from the bview time to t1."""
import os, re, sys, subprocess
from datetime import timedelta, datetime
from concurrent.futures import ThreadPoolExecutor
from cases import all_cases as cases
BASE = "https://data.ris.ripe.net/rrc00"
_ls = {}
def listing(month):
    if month not in _ls:
        html = subprocess.run(["curl", "-s", "--retry", "3", f"{BASE}/{month}/"], capture_output=True, text=True).stdout
        _ls[month] = sorted(set(re.findall(r'(?:updates|bview)\.\d{8}\.\d{4}\.gz', html)))
    return _ls[month]
ts = lambda f: datetime.strptime(".".join(f.split(".")[1:3]), "%Y%m%d.%H%M")
def months(a, b):
    m = a.replace(day=1, hour=0, minute=0)
    while m <= b:
        yield f"{m:%Y.%m}"; m = (m + timedelta(days=32)).replace(day=1)
def jobs_for(c):
    d = f"data/{c['case']}"; os.makedirs(d, exist_ok=True)
    start = c["t0"] - timedelta(hours=24)
    bv = [(m, f) for m in months(start - timedelta(days=2), start) for f in listing(m) if f.startswith("bview") and ts(f) <= start]
    m, rib = bv[-1]
    J = [(f"{BASE}/{m}/{rib}", f"{d}/rib.gz")]; open(f"{d}/RIBTIME", "w").write(rib)
    for m in months(ts(rib), c["t1"]):
        for f in listing(m):
            if f.startswith("updates") and ts(rib) <= ts(f) < c["t1"]:
                J.append((f"{BASE}/{m}/{f}", f"{d}/upd.{ts(f):%Y%m%d.%H%M}.gz"))
    return J
def ok(dst):
    return os.path.exists(dst) and os.path.getsize(dst) > 0 and subprocess.run(["gzip", "-t", dst], capture_output=True).returncode == 0
def get(a):
    url, dst = a
    for _ in range(6):                      # retry; never keep a truncated file
        if ok(dst): return 0
        subprocess.run(["curl", "-sS", "-f", "--retry", "5", "--retry-all-errors", "-o", dst, url])
        if not ok(dst) and os.path.exists(dst): os.remove(dst)
    return 0 if ok(dst) else 1
if __name__ == "__main__":
    want = set(sys.argv[1:])
    J = [j for c in cases() if c["case"] in want for j in jobs_for(c)]
    with ThreadPoolExecutor(4) as ex: rc = list(ex.map(get, J))
    bad = [j for j, r in zip(J, rc) if r]
    print(len(J), "files, failed", len(bad)); [print(b) for b in bad[:20]]
    sys.exit(1 if bad else 0)
