# Running the two long jobs for free

Both jobs are fixed in `HELDOUT_PREREGISTRATION.md` (addenda of 2026-10-07 and 2026-10-08). Run them as written and
report every number, including failures. Nothing here costs money.

## Job 1: multi-collector replay on GitHub Actions (free for public repositories)

1. Move the workflow file into place (my tools may not write into `.github/`), commit, and push:
   ```bash
   cd "GitHub Projects/prism-bgp"
   mkdir -p .github/workflows && git mv ci/multicollector.yml .github/workflows/multicollector.yml
   git commit -m "Enable multicollector workflow" && git push origin main
   ```
2. On github.com open the repository, click **Actions**. If asked, click **"I understand my workflows, go ahead and
   enable them"**.
3. Click **multicollector** in the left list, then **Run workflow** (leave "cases" empty), then the green **Run workflow**.
4. It runs 210 jobs, 20 at a time, each up to 6 hours. Expect roughly 1-3 days in total. You can close the browser.
5. When the run shows a green or orange check, open it, scroll to **Artifacts**, download **multicollector-results**
   (a zip) and send it to me. Jobs that failed (red) are part of the result: they are reported, not hidden.

To test first with two small cases, type `X004 PT2008` in the "cases" box before clicking Run.

## Job 3: live deployment on an Oracle Cloud "Always Free" VM

The Always Free tier includes an Arm VM with up to 4 cores and 24 GB of RAM at no cost, permanently. Sign-up asks for a
card to verify identity; Always Free resources are not charged. Use a **personal** account (not your work tenancy).

1. Sign up at cloud.oracle.com (Free Tier). Pick a home region close to you.
2. **Compute > Instances > Create instance.** Image: Canonical Ubuntu 22.04. Shape: **Ampere VM.Standard.A1.Flex**,
   2 OCPUs, 12 GB memory (marked "Always Free-eligible"). Add your SSH public key (or let it generate one and save it).
   Create.
3. Connect: `ssh ubuntu@<public IP>` (Oracle shows the IP on the instance page).
4. Install and start (copy-paste):
   ```bash
   sudo apt-get update && sudo apt-get install -y python3-pip git curl tmux
   git clone https://github.com/Kinjal-Oza/prism-bgp && cd prism-bgp/code
   pip install --break-system-packages pybgpkit pandas pyarrow websocket-client
   sudo cp ../live/prism-live.service /etc/systemd/system/ && sudo systemctl daemon-reload
   sudo systemctl enable --now prism-live
   ```
   If `pip install pybgpkit` fails on Arm, run `curl https://sh.rustup.rs -sSf | sh -s -- -y && . ~/.cargo/env` and retry.
5. Check it is alive: `tail -2 ~/prism-bgp/code/live_out/status.jsonl` (a new line every 5 minutes; `lag_s` should stay
   around 300). The service restarts automatically if it crashes or the VM reboots (each restart repeats the 24-hour
   warm-up; note any gap).
6. Leave it for at least 22 days. Then, with a free Cloudflare API token (dash.cloudflare.com > My Profile > API Tokens >
   Create Token > "Read all resources" template):
   ```bash
   cd ~/prism-bgp/code && CF_API_TOKEN=... python3 live_verify.py --out live_out
   tar czf live_results.tgz live_out/alerts.jsonl live_out/status.jsonl live_out/verify_* live_out/radar_*.json
   ```
   Copy `live_results.tgz` to your Mac (`scp ubuntu@<IP>:prism-bgp/code/live_results.tgz .`) and send it to me.
   Do not change thresholds during the run.
