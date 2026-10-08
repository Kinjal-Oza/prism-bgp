"""PRISM live (pre-registered 2026-10-07): D2 = persistence-gated learning (D1) + 6-h offender scale, on RIPE RIS Live.

  python3 live_prism.py --out live_out [--owner my_prefixes.txt] [--warmup-h 24]

Bootstrap: latest RIS rrc00 bview + latest CAIDA serial-1 relationships. Then the RIS Live firehose (all RIS
collectors). For the first --warmup-h hours nothing is alerted (history and offender history are learned).
Writes, in --out:
  alerts.jsonl   one line per alert: 5-min unit (scale "5m") or 6-h episode (scale "6h"), with evidence
  owner.jsonl    every NO/NX flag on a prefix in --owner (owner mode), if given
  status.jsonl   one line per 5 minutes: messages, announcements, flags, lag behind real time
Run it under tmux/screen or systemd. On restart it bootstraps again (state is not checkpointed)."""
import argparse, json, os, re, sys, time, math, gzip, subprocess, heapq, ipaddress
from collections import defaultdict, Counter, deque
import bgpkit
from asrel import ASRel
from engine import clean_path
from engine2 import Shared, View
W = 300; G = 12; L = 72; LAG6 = L + G
TAU = {"NO": 50, "NX": 2000}
CAIDA = "https://publicdata.caida.org/datasets/as-relationships/serial-1/"

def latest_asrel(d="asrel"):
    os.makedirs(d, exist_ok=True)
    html = subprocess.run(["curl", "-s", CAIDA], capture_output=True, text=True).stdout
    f = sorted(set(re.findall(r"\d{8}\.as-rel\.txt\.bz2", html)))[-1]
    if not os.path.exists(f"{d}/{f}"): subprocess.run(["curl", "-sSf", "-o", f"{d}/{f}", CAIDA + f], check=True)
    return f"{d}/{f}"

class Online(View):
    """D1 view that also keeps per-window flag sets for online scoring."""
    def __init__(self, S, owner=None):
        super().__init__("D1", S, "D1")
        self.win = defaultdict(lambda: defaultdict(set))      # w -> (fam, off) -> prefixes
        self.ev = defaultdict(list)                           # w -> evidence samples per (fam, off)
        self.owner = owner; self.owner_hits = []
    def emit(self, ts, ty, off, p, peer, path):
        w = int(ts // W); s = self.win[w][(ty, off)]
        if len(s) < 200000: s.add(p)
        e = self.ev[(w, ty, off)]
        if len(e) < 5: e.append(dict(prefix=p, path=" ".join(map(str, path)), vp=int(peer)))
        if self.owner is not None and self.owner(p): self.owner_hits.append(dict(ts=ts, fam=ty, off=int(off), prefix=p, path=" ".join(map(str, path))))
    def purge(self):
        """drop ended presence episodes and stale carriage records (bounded memory over weeks; same semantics:
        a pair that reappears starts a new episode either way)"""
        dead = [k for k, e in self.pend.items() if e[0] is None and not e[1]]
        for k in dead: del self.pend[k]
        stale = [k for k, items in self.carry.items() if not any(i in self.pend for i in items)]
        for k in stale: del self.carry[k]
        return len(dead), len(stale)
    def flush(self, out): pass
    def close(self, out): pass

class Scorer:
    def __init__(self, view):
        self.v = view; self.H = {}; self.H6 = {}; self.heap5 = []; self.heap6 = []
        self.hist = defaultdict(deque)          # (fam, off) -> deque[(w, prefixes)] last L windows
        self.adm_w = defaultdict(lambda: defaultdict(set))   # (fam, off) -> w -> admitted prefixes (by flag window)
        self.adm_seen = 0; self.in_ep = set()
    def _ingest_admissions(self):
        A = self.v.adm
        for fam, p, a, since, t in A[self.adm_seen:]:
            w = int(since // W); self.adm_w[(fam, a)][w].add(p)
            heapq.heappush(self.heap5, (max(w + G, math.ceil(t / W)), fam, a, w))
        self.adm_seen = len(A)
    def close_window(self, w, alerting):
        """score window w (all its flags are in); returns alerts"""
        self._ingest_admissions()
        while self.heap5 and self.heap5[0][0] <= w:
            _, fam, a, ww = heapq.heappop(self.heap5)
            k = (fam, a); self.H[k] = max(self.H.get(k, 0), len(self.adm_w[k].get(ww, ())))
            heapq.heappush(self.heap6, (ww + LAG6, fam, a, ww))
        while self.heap6 and self.heap6[0][0] <= w:
            _, fam, a, ww = heapq.heappop(self.heap6); k = (fam, a)
            u = set().union(*[s for x, s in self.adm_w[k].items() if ww - L < x <= ww])
            self.H6[k] = max(self.H6.get(k, 0), len(u))
        out = []; cur = self.v.win.pop(w, {})
        for k, pf in cur.items():
            dq = self.hist[k]; dq.append((w, pf))
        for k in list(self.hist):
            dq = self.hist[k]
            while dq and dq[0][0] <= w - L: dq.popleft()
            if not dq: del self.hist[k]; self.in_ep.discard(k); continue
            fam, a = k; tau = TAU[fam]
            if k in cur:
                c = len(cur[k]); s = c / (1 + self.H.get(k, 0))
                if s >= tau and alerting:
                    out.append(dict(scale="5m", fam=fam, asn=int(a), window=w, ts=w * W, c=c, H=self.H.get(k, 0), score=s,
                                    evidence=self.v.ev.get((w, fam, a), [])))
            c6 = len(set().union(*[s for _, s in dq])); s6 = c6 / (1 + self.H6.get(k, 0))
            if s6 >= tau:
                if k not in self.in_ep and alerting:
                    out.append(dict(scale="6h", fam=fam, asn=int(a), window=w, ts=w * W, c=c6, H=self.H6.get(k, 0), score=s6,
                                    evidence=self.v.ev.get((w, fam, a), [])))
                self.in_ep.add(k)
            else: self.in_ep.discard(k)
        for key in [x for x in self.v.ev if x[0] <= w]: del self.v.ev[key]
        # bound memory for admitted-window index
        for k in list(self.adm_w):
            for x in [x for x in self.adm_w[k] if x < w - L - LAG6 - 24]: del self.adm_w[k][x]
            if not self.adm_w[k]: del self.adm_w[k]
        return out

def owner_matcher(path):
    if not path: return None
    nets = [ipaddress.ip_network(l.strip(), strict=False) for l in open(path) if l.strip() and ":" not in l]
    def m(p):
        n = ipaddress.ip_network(p, strict=False)
        return any(n.subnet_of(x) for x in nets)
    return m

def messages(client="prism-live"):
    import websocket
    while True:
        try:
            ws = websocket.create_connection(f"wss://ris-live.ripe.net/v1/ws/?client={client}", timeout=60)
            ws.send(json.dumps({"type": "ris_subscribe", "data": {"type": "UPDATE"}}))
            while True:
                m = json.loads(ws.recv())
                if m.get("type") == "ris_message": yield m["data"]
        except Exception as e:
            print("reconnect after", repr(e), file=sys.stderr, flush=True); time.sleep(5)

def flat_path(p):
    if not p or any(isinstance(x, list) for x in p): return None
    return clean_path(" ".join(map(str, p)))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="live_out"); ap.add_argument("--owner")
    ap.add_argument("--warmup-h", type=float, default=24.0); ap.add_argument("--max-hours", type=float, default=0)
    ap.add_argument("--bview", default="https://data.ris.ripe.net/rrc00/latest-bview.gz")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    rel = ASRel(latest_asrel()); S = Shared(rel); T = time.time(); n = 0
    bv = os.path.join(a.out, "bview.gz")
    subprocess.run(["curl", "-sSf", "-o", bv, a.bview], check=True)
    for e in bgpkit.Parser(url=bv):
        if ":" in e.prefix: continue
        p = clean_path(e.as_path)
        if p: S.learn_rib(e.prefix, p); n += 1
    os.remove(bv)
    print(f"bootstrap {n} RIB entries, {len(S.hist)} prefixes, {time.time()-T:.0f}s", flush=True)
    V = Online(S, owner_matcher(a.owner)); SC = Scorer(V)
    start = time.time(); cur_w = None; stats = Counter(); hosts = {}
    fa = open(os.path.join(a.out, "alerts.jsonl"), "a"); fo = open(os.path.join(a.out, "owner.jsonl"), "a")
    fs = open(os.path.join(a.out, "status.jsonl"), "a")
    for m in messages():
        ts = float(m["timestamp"]); w = int(ts // W)
        if cur_w is None: cur_w = w
        if w > cur_w:   # close all finished windows (RIS Live is near-real-time; small reordering is tolerated)
            alerting = (time.time() - start) >= a.warmup_h * 3600
            for x in range(cur_w, w):
                for al in SC.close_window(x, alerting): fa.write(json.dumps(al) + "\n")
            fa.flush()
            for h in V.owner_hits: fo.write(json.dumps(h) + "\n")
            V.owner_hits.clear(); fo.flush()
            fs.write(json.dumps(dict(window=cur_w, wall=time.time(), lag_s=time.time() - cur_w * W, alerting=alerting,
                                     pending=len(V.pend), **stats)) + "\n"); fs.flush(); stats.clear(); cur_w = w
            if cur_w % 12 == 0: V.purge()
            if a.max_hours and time.time() - start > a.max_hours * 3600: break
        host = m.get("host", "?"); hidx = hosts.setdefault(host, len(hosts)); peer = m.get("peer", "")
        sess = f"{host}|{peer}"; vp = (hidx << 33) + int(m.get("peer_asn", 0) or 0); stats["msgs"] += 1
        for wd in m.get("withdrawals", []) or []:
            if ":" not in wd: V.wd(ts, wd, sess)
        anns = m.get("announcements") or []
        if not anns: continue
        path = flat_path(m.get("path"))
        if not path: continue
        for an in anns:
            for p in an.get("prefixes", []):
                if ":" in p: continue
                stats["ann"] += 1; V.ann(ts, p, path, vp, sess)

if __name__ == "__main__":
    main()
