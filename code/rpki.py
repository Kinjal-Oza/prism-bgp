"""RPKI route-origin validation against the RIPE NCC archive of published ROAs (all five RIR trust anchors).
ROA snapshot = the day the case's test window starts (files in rpki/, fetched from ftp.ripe.net/rpki/<tal>/<date>/)."""
import lzma, csv, ipaddress
from collections import defaultdict
from engine import v4key
TALS = ["afrinic", "apnic", "arin", "lacnic", "ripencc"]
_cache = {}
def load(day):                         # day: 'YYYY-MM-DD'
    if day in _cache: return _cache[day]
    R = defaultdict(lambda: defaultdict(list))   # length -> network int -> [(asn, maxlen)]
    for t in TALS:
        for r in csv.DictReader(lzma.open(f"rpki/{day}_{t}.csv.xz", "rt")):
            p = r["IP Prefix"]
            if ":" in p: continue
            n, l = v4key(p); R[l][n].append((int(r["ASN"].replace("AS", "")), int(r["Max Length"]) if r["Max Length"] else l))
    _cache[day] = R; return R
def state(R, prefix, origin):
    """'valid', 'invalid' or 'notfound' (RFC 6811)."""
    n, l = v4key(prefix); covered = False
    for L in range(l, -1, -1):
        m = (n >> (32 - L)) << (32 - L) if L else 0
        for asn, ml in R[L].get(m, ()):
            covered = True
            if asn == origin and l <= ml and asn != 0: return "valid"
    return "invalid" if covered else "notfound"
