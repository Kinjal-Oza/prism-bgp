"""ARTEMIS-style owner-side detection, re-implemented from Sermpezis et al. (IEEE/ACM ToN 2018) for a
head-to-head comparison with PRISM's owner mode on the same replays.

ARTEMIS is configured by the prefix owner with its prefixes, legitimate origin ASes and legitimate first-hop
neighbours. We give every prefix owner the most generous configuration available from public data: every origin and
every first-hop neighbour (the AS before the origin on the path) observed for the prefix in the RIB snapshot and in the
24-h warm-up, i.e. exactly the information PRISM had. The configuration is then frozen for the test window.

Alert types (ARTEMIS taxonomy, prefix|path):
  E|0  exact prefix, origin not configured            hijacker = origin
  E|1  exact prefix, first-hop neighbour not configured hijacker = neighbour
  S|0  sub-prefix of a configured prefix, illegal origin       hijacker = origin
  S|1  sub-prefix, legal origin, illegal first hop             hijacker = neighbour
  S|-  sub-prefix, legal origin and first hop (unconfigured more-specific) hijacker = origin
Squatting (unannounced space) and Type-N/U are out of scope here. Output: out3/<case>.artemis.parquet with the first
alert per (prefix, type, hijacker) in the test window."""
import sys, glob, ipaddress, os
from collections import defaultdict
import bgpkit, pandas as pd
import evaluate as E
from cases import all_cases
from engine import clean_path, v4key

def run(k):
    c = {x["case"]: x for x in all_cases()}[k]; t0, t1 = E.TS(c["t0"]), E.TS(c["t1"])
    org = defaultdict(set); nbr = defaultdict(set); L = defaultdict(set)
    def learn(p, path):
        if p not in org:
            n, l = v4key(p); L[l].add(n)
        org[p].add(path[-1])
        if len(path) >= 2: nbr[p].add(path[-2])
    def owner(p):
        n, l = v4key(p)
        for ln in range(l - 1, 7, -1):
            m = (n >> (32 - ln)) << (32 - ln)
            if m in L[ln]: return f"{ipaddress.IPv4Address(m)}/{ln}"
        return None
    rib = sorted(glob.glob(f"data/{k}/rib.*"))[0]
    for e in bgpkit.Parser(url=rib):
        if ":" in e.prefix: continue
        path = clean_path(e.as_path)
        if path: learn(e.prefix, path)
    seen = {}; rows = []
    for f in sorted(glob.glob(f"data/{k}/upd.*.bz2") + glob.glob(f"data/{k}/upd.*.gz")):
        for e in bgpkit.Parser(url=f):
            if e.elem_type != "A" or ":" in e.prefix: continue
            ts = e.timestamp
            if ts >= t1: continue
            path = clean_path(e.as_path)
            if not path: continue
            p = e.prefix
            if ts < t0: learn(p, path); continue          # warm-up: configuration
            o = path[-1]; nb = path[-2] if len(path) >= 2 else None
            if p in org:
                if o not in org[p]: t, h = "E|0", o
                elif nb is not None and nb not in nbr[p]: t, h = "E|1", nb
                else: continue
            else:
                P = owner(p)
                if P is None: continue
                if o not in org[P]: t, h = "S|0", o
                elif nb is not None and nb not in nbr[P]: t, h = "S|1", nb
                else: t, h = "S|-", o
            key = (p, t, h)
            if key in seen: continue
            seen[key] = 1; rows.append((ts, p, t, h, o, nb if nb is not None else -1, e.peer_asn))
    os.makedirs("out3", exist_ok=True)
    pd.DataFrame(rows, columns=["ts", "prefix", "type", "hijacker", "origin", "neighbor", "peer"]).to_parquet(f"out3/{k}.artemis.parquet")
    print(k, len(rows), "alerts; configured prefixes", len(org), flush=True)

if __name__ == "__main__":
    for k in sys.argv[1:]: run(k)
