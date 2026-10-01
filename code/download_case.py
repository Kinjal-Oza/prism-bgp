"""Download the route-views2 RIB + UPDATE files one case needs, using the archive's directory
listing (robust to file times that are not aligned to quarter hours). Usage: download_case.py CASE..."""
import os, re, sys, subprocess
from datetime import timedelta, datetime
from concurrent.futures import ThreadPoolExecutor
from cases import all_cases as cases
BASE = "http://archive.routeviews.org/bgpdata"
_ls = {}
def listing(month, kind):
    k = (month, kind)
    if k not in _ls:
        html = subprocess.run(["curl", "-s", "--retry", "3", f"{BASE}/{month}/{kind}/"],
                              capture_output=True, text=True).stdout
        _ls[k] = sorted(set(re.findall(r'(?:updates|rib)\.\d{8}\.\d{4}\.bz2', html)))
    return _ls[k]
ts = lambda f: datetime.strptime(".".join(f.split(".")[1:3]), "%Y%m%d.%H%M")
def months(a, b):
    m = a.replace(day=1, hour=0, minute=0)
    while m <= b:
        yield f"{m:%Y.%m}"
        m = (m + timedelta(days=32)).replace(day=1)
def jobs_for(c):
    d = f"data/{c['case']}"; os.makedirs(d, exist_ok=True)
    start = c["t0"] - timedelta(hours=24)
    ribs = [(m, f) for m in months(start - timedelta(days=2), start) for f in listing(m, "RIBS") if ts(f) <= start]
    m, rib = ribs[-1]
    J = [(f"{BASE}/{m}/RIBS/{rib}", f"{d}/rib.bz2")]
    open(f"{d}/RIBTIME", "w").write(rib)
    for m in months(ts(rib) - timedelta(minutes=15), c["t1"]):
        for f in listing(m, "UPDATES"):
            if ts(rib) <= ts(f) < c["t1"]:   # as in download.py: updates from the RIB time on
                J.append((f"{BASE}/{m}/UPDATES/{f}", f"{d}/upd.{ts(f):%Y%m%d.%H%M}.bz2"))
    return J
def get(a):
    url, dst = a
    if os.path.exists(dst) and os.path.getsize(dst) > 0: return 0
    return subprocess.run(["curl", "-sS", "-f", "--retry", "5", "-o", dst, url]).returncode
if __name__ == "__main__":
    want = set(sys.argv[1:])
    J = [j for c in cases() if c["case"] in want for j in jobs_for(c)]
    with ThreadPoolExecutor(12) as ex: rc = list(ex.map(get, J))
    bad = [j for j, r in zip(J, rc) if r]
    print(len(J), "files, failed", len(bad)); [print(b) for b in bad[:20]]
