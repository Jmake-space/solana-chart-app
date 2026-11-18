#!/bin/bash
# Hourly Solana dataset refresh + sync to pi5d05 NVMe.
# VM copy:  ~/workspace/solana/  (dataset, forecast.json, chart-data.json, app/)
# Pi copy:  /mnt/nas02/solana/ on pi5d05 (192.168.1.108, via d06 hop)
# Steps: fetch (Binance public, no key) -> verify (abort on any failure)
#   -> forecast v3 -> weekly 12w outlook -> chart-data -> local app rebuild
#   -> manifest update -> daily OKX IV snapshot (non-fatal)
#   -> rsync VM -> d06 staging -> d05 NVMe -> verify Pi copy (counts + md5)
# Exit non-zero on any failure, before rsync, so a bad fetch never overwrites the Pi.
# Log: ~/workspace/solana/logs/sync-YYYY-MM-DD.log (append)
set -u
SOL="$HOME/workspace/solana"
LOGDIR="$SOL/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/sync-$(date -u +%F).log"
exec >>"$LOG" 2>&1
echo "=== sync start $(date -u +%FT%TZ) ==="
cd "$SOL/scripts" || exit 1

run() { echo "--- $*"; "$@" || { echo "FAIL: $*"; exit 1; }; }

run python3 fetch_binance.py
# verify_dataset.py prints checks; gate on the zero-failure lines
VERIFY_OUT=$(python3 verify_dataset.py) || { echo "$VERIFY_OUT"; echo "FAIL: verify_dataset.py"; exit 1; }
echo "$VERIFY_OUT"
for pat in "duplicate timestamps: 0" "non-1h steps: 0" "OHLC/volume violations: 0" "daily aggregate mismatches: 0"; do
  echo "$VERIFY_OUT" | grep -qF "$pat" || { echo "FAIL: verification gate missing '$pat'"; exit 1; }
done
run python3 forecast_v3.py  # v3 drift30 + tunable vol (2026-11-17); v1/v2 kept intact for comparison
run python3 make_chart_data.py
run python3 build_local_app.py
run python3 update_manifest.py

# 3-month (12-week) analogue outlook from the 3y weekly data (added
# 2026-11-18). Writes a `weekly_12w` block into forecast.json; does NOT
# change v3's daily points (no weekly model beats naive on MAE). Fail-safe:
# the script exits 0 on any error, and the || here is belt-and-braces.
python3 weekly_outlook.py || echo "Weekly outlook step failed (non-fatal, continuing)"

# Daily OKX SOL ATM IV snapshot (public REST, no key; added 2026-11-18).
# Runs once per UTC day, no-ops when today's rows already exist, and MUST
# NEVER fail this sync: the collector exits 0 on any error, and the || here
# is belt-and-braces. IV stays OUT of the forecast until tested (see
# ../IV_SERIES.md); this only appends to iv_series.csv + iv_snapshots/.
python3 okx_iv_daily.py || echo "IV snapshot step failed (non-fatal, continuing)"

# --- sync to Pi ---
# ssh-agent with the VM key (exec runs as root; key lives in /home/hatch/.ssh)
eval $(ssh-agent -s) >/dev/null 2>&1
ssh-add /home/hatch/.ssh/id_ed25519 || { echo "FAIL: ssh-add"; exit 1; }

# Stage 1: VM -> d06 (Tailscale, via pi-ssh proxy).
# NOTE: rsync directly from the VM fails here — rsync mangles the ProxyCommand
# that pi-ssh uses (verified 2026-11-17: "SyntaxError: invalid decimal literal"
# from the SSH banner). Tar piped through the working pi-ssh wrapper works.
# Dataset is ~1.5 MB, so a full copy each hour is cheap; rm first keeps it exact.
run bash -c 'tar -czf - -C "$HOME/workspace" solana | "$HOME/workspace/bin/pi-ssh" "rm -rf /home/jaideepbir/solana && mkdir -p /home/jaideepbir/solana && tar -xzf - -C /home/jaideepbir/solana --strip-components=1"'

# Stage 2: d06 -> d05 NVMe, using the forwarded agent key.
# NOTE: the mkdir must run ON d05 (via ssh), not on d06 — an earlier version
# ran mkdir on d06 and failed with "cannot create directory /mnt/nas02".
run "$HOME/workspace/bin/pi-ssh" -A 'ssh jaideepbir@192.168.1.108 "mkdir -p /mnt/nas02/solana" && rsync -av --delete /home/jaideepbir/solana/ jaideepbir@192.168.1.108:/mnt/nas02/solana/'

# --- verify Pi copy ---
LOCAL_MD5=$(md5sum "$SOL/chart-data.json" | cut -d' ' -f1)
LOCAL_ROWS=$(find "$SOL/dataset" -name 'sol_*.csv' | wc -l)
PI_CHECK=$("$HOME/workspace/bin/pi-ssh" -A 'ssh jaideepbir@192.168.1.108 "find /mnt/nas02/solana/dataset -name '\''sol_*.csv'\'' | wc -l; md5sum /mnt/nas02/solana/chart-data.json | cut -d\" \" -f1; tail -1 /mnt/nas02/solana/dataset/daily/sol_ohlcv_daily.csv"' ) || { echo "FAIL: Pi verification ssh"; exit 1; }
echo "Pi check:"; echo "$PI_CHECK"
PI_ROWS=$(echo "$PI_CHECK" | head -1 | tr -d ' ')
PI_MD5=$(echo "$PI_CHECK" | sed -n 2p | tr -d ' ')
[ "$PI_ROWS" = "$LOCAL_ROWS" ] || { echo "FAIL: Pi file count $PI_ROWS != local $LOCAL_ROWS"; exit 1; }
[ "$PI_MD5" = "$LOCAL_MD5" ] || { echo "FAIL: Pi chart-data md5 $PI_MD5 != local $LOCAL_MD5"; exit 1; }
echo "=== sync OK $(date -u +%FT%TZ) csv_files=$LOCAL_ROWS md5=$LOCAL_MD5 ==="
