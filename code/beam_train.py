"""Train BEAM with its official code, in chunks that fit Kaggle's 12-h sessions.
The official training loop already saves a checkpoint every 100 epochs; this wrapper only resumes from it.
Algorithm, hyper-parameters (1000 epochs, Q=10, d=128, Adam lr 1e-3, batch 1024) and data are unchanged."""
import sys, os, glob, time, shutil, subprocess, torch
SNAP = os.environ["SNAP"]; STOP = int(os.environ.get("STOP_EPOCH", "1000"))
W = "/kaggle/working"
subprocess.run(f"git clone -q https://github.com/yhchen-tsinghua/routing-anomaly-detection {W}/beam", shell=True, check=True)
subprocess.run("pip install -q click joblib", shell=True)
sys.path.insert(0, f"{W}/beam/BEAM_engine"); sys.path.insert(0, f"{W}/beam")
from BEAM_model import BEAM
from data.caida_as_rel.fetch_data import get as prepare_edge_file
from pathlib import Path
edge = prepare_edge_file("2", int(SNAP)); tdir = Path(f"{W}/beam/BEAM_engine/models/{edge.stem}.1000.10.128"); tdir.mkdir(parents=True, exist_ok=True)
prev = glob.glob("/kaggle/input/**/checkpoint", recursive=True)
m = BEAM(edge_file=edge, Q=10, dimension=128, train_dir=tdir, num_workers=4)
start = 1
if prev:
    ck = torch.load(prev[0], map_location="cpu"); m.load_state_dict(ck["model_state_dict"]); start = ck["epoch"]
    print("resumed from epoch", start, prev[0], flush=True)
m.to(device=m.device)
opt = torch.optim.Adam(m.parameters(), lr=1e-3, weight_decay=0)
if prev: opt.load_state_dict(ck["optimizer_state_dict"])
gen = torch.utils.data.DataLoader(m.analyzer, batch_size=1024, shuffle=True, num_workers=4)
for epoch in range(start, STOP + 1):        # same loop body as BEAM_model.train
    if epoch % 100 == 0:
        torch.save({"epoch": epoch, "model_state_dict": m.state_dict(), "optimizer_state_dict": opt.state_dict()}, tdir / "checkpoint")
        shutil.copy(tdir / "checkpoint", f"{W}/checkpoint")
    if epoch == STOP and STOP < 1000: break
    loss = 0.0; t = time.time()
    for b in gen:
        opt.zero_grad(); b = b.to(device=m.device); bl = m(b).sum(); loss += float(bl); bl.backward(); opt.step()
    print(f"Epoch{epoch:4d}/1000 Loss: {loss:e} Time: {time.time()-t:.1f}s", flush=True)
if STOP == 1000:
    m.save_embeddings(path=str(tdir)); subprocess.run(f"cp -r {tdir} {W}/model", shell=True); print("DONE", flush=True)
