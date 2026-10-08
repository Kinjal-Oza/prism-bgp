"""Verify live PRISM alerts against Cloudflare Radar's BGP hijack and route-leak event feeds (pre-registered 2026-10-07).

  CF_API_TOKEN=... python3 live_verify.py --out live_out

Needs a free Cloudflare API token (any token can read Radar). Writes in --out:
  radar_hijacks.json, radar_leaks.json   raw feeds for the alerting period (kept for the paper's artifact)
  verify_alerts.csv                      every PRISM alert, matched Radar event (same AS within +-2 h) or blank
  verify_missed.csv                      Radar events with confidence >= 8 (hijacks) or any leak with no PRISM alert
  verify_summary.md                      counts; unmatched alerts get a 'class' column to fill by hand
                                         (confirmed / benign / unknown) from the logged evidence and public reports"""
import argparse, json, os, sys, urllib.request, urllib.parse, datetime as dt
import pandas as pd
API = "https://api.cloudflare.com/client/v4/radar/bgp"

def fetch(kind, start, end, token):
    out = []; page = 1
    while True:
        q = urllib.parse.urlencode(dict(dateStart=start, dateEnd=end, page=page, per_page=100, format="JSON"))
        req = urllib.request.Request(f"{API}/{kind}/events?{q}", headers={"Authorization": f"Bearer {token}"})
        r = json.load(urllib.request.urlopen(req, timeout=60))
        ev = (r.get("result") or {}).get("events") or (r.get("result") or {}).get(kind) or []
        out += ev
        if len(ev) < 100 or page > 200: return out
        page += 1

def pick(e, *names):
    for n in names:
        if n in e and e[n] not in (None, ""): return e[n]
    for k, v in e.items():   # tolerate schema changes: first key containing any of the name stems
        if any(n.split("_")[0] in k for n in names) and v not in (None, ""): return v
    return None

def ts(x):
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    return dt.datetime.fromisoformat(str(x).replace("Z", "+00:00")).timestamp()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="live_out"); ap.add_argument("--window-h", type=float, default=2.0)
    a = ap.parse_args(); tok = os.environ.get("CF_API_TOKEN")
    if not tok: sys.exit("set CF_API_TOKEN (free Cloudflare API token)")
    al = pd.read_json(os.path.join(a.out, "alerts.jsonl"), lines=True)
    if al.empty: sys.exit("no alerts yet")
    start = dt.datetime.utcfromtimestamp(al.ts.min() - 86400).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = dt.datetime.utcfromtimestamp(al.ts.max() + 86400).strftime("%Y-%m-%dT%H:%M:%SZ")
    H = fetch("hijacks", start, end, tok); Lk = fetch("leaks", start, end, tok)
    json.dump(H, open(os.path.join(a.out, "radar_hijacks.json"), "w")); json.dump(Lk, open(os.path.join(a.out, "radar_leaks.json"), "w"))
    rad = []
    for e in H:
        rad.append(dict(kind="hijack", id=pick(e, "id", "event_id"), asn=pick(e, "hijacker_asn"), conf=pick(e, "confidence_score"),
                        t0=ts(pick(e, "min_hijack_ts", "min_ts", "start_ts")), t1=ts(pick(e, "max_hijack_ts", "max_ts", "end_ts"))))
    for e in Lk:
        rad.append(dict(kind="leak", id=pick(e, "id", "event_id"), asn=pick(e, "leak_asn"), conf=None,
                        t0=ts(pick(e, "min_ts", "detected_ts", "start_ts")), t1=ts(pick(e, "max_ts", "finished_ts", "end_ts"))))
    R = pd.DataFrame(rad); w = a.window_h * 3600
    def match(r):
        if R.empty: return None
        m = R[(R.asn.astype(str) == str(r.asn)) & (R.t0.fillna(0) - w <= r.ts) & (r.ts <= R.t1.fillna(R.t0) + w)]
        return None if m.empty else f"{m.iloc[0].kind}:{m.iloc[0].id}"
    al["radar_match"] = al.apply(match, axis=1); al["class"] = ""
    al.drop(columns=["evidence"], errors="ignore").to_csv(os.path.join(a.out, "verify_alerts.csv"), index=False)
    hit = set(zip(al.asn.astype(str), (al.ts // 3600)))
    def missed(r):
        return not any(str(r.asn) == x and (r.t0 - w) / 3600 <= h <= ((r.t1 or r.t0) + w) / 3600 for x, h in hit)
    M = R[((R.kind == "leak") | (R.conf.fillna(0) >= 8)) & (R.t0 >= al.ts.min()) & (R.t0 <= al.ts.max())]
    M = M[M.apply(missed, axis=1)] if not M.empty else M
    M.to_csv(os.path.join(a.out, "verify_missed.csv"), index=False)
    days = (al.ts.max() - al.ts.min()) / 86400
    s = [f"# Live PRISM verification", f"Alerting period: {days:.1f} days, {len(al)} alerts ({(al.scale=='5m').sum()} 5-min, {(al.scale=='6h').sum()} 6-h).",
         f"Matched to a Radar event: {al.radar_match.notna().sum()}; unmatched (classify by hand): {al.radar_match.isna().sum()}.",
         f"Radar events (hijacks with confidence >= 8, all leaks) in the period: {len(R[((R.kind=='leak')|(R.conf.fillna(0)>=8))])}; with no PRISM alert: {len(M)}."]
    open(os.path.join(a.out, "verify_summary.md"), "w").write("\n\n".join(s) + "\n"); print("\n".join(s))

if __name__ == "__main__":
    main()
