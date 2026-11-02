"""Laptop side of ONKAR-LIFE v2.
  bash run.sh tool battery          live battery %, voltage, charging trend (Ctrl+C to stop)
  bash run.sh tool pins [pull]      snapshot of all pin levels (pull: 0 none, 1 up, 2 down)
  bash run.sh tool lcdprobe         automatic screen hunt (reads panel ID, tries wake-up)
  bash run.sh tool out PIN LEVEL    hold a pin (P-number 0..38) high/low
  bash run.sh tool buzz PIN         300 ms pulse high on a pin (feel for the motor)
"""
import asyncio, sys, time, json, os
from bleak import BleakScanner, BleakClient

W = "0000b002-0000-1000-8000-00805f9b34fb"
N = "0000b003-0000-1000-8000-00805f9b34fb"
NAMES = {**{i: f"P0_{i}" for i in range(8)}, **{8+i: f"P1_{i}" for i in range(8)}, **{16+i: f"P2_{i}" for i in range(8)},
         **{24+i: f"P3_{i}" for i in range(7)}, 32: "P4_0", 33: "P4_1", 34: "P4_2", 35: "P4_3", 36: "H_0", 37: "H_1", 38: "H_2"}
LCD = {32, 33, 34, 35, 6, 7}
NEVER = {31, 20} | LCD          # 31 doesn't exist, 20 = P2_4 (sample's key IRQ)
q = asyncio.Queue()
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

async def cmd(c, b, wait=3.0):
    while not q.empty(): q.get_nowait()
    await c.write_gatt_char(W, bytes(b), response=True)
    try: return await asyncio.wait_for(q.get(), wait)
    except asyncio.TimeoutError: return None

async def connect():
    import subprocess
    subprocess.run(["bluetoothctl", "disconnect", "00:E0:12:34:56:78"], capture_output=True, timeout=10)
    await asyncio.sleep(2)   # laptop's keyboard support grabs the watch; release it so it advertises again
    found = await BleakScanner.discover(timeout=8, return_adv=True)
    dev = next((d for a, (d, adv) in found.items() if (adv.local_name or "").startswith("ONKAR")), None)
    if not dev:
        raise SystemExit("ONKAR-LIFE not advertising - run: bluetoothctl disconnect 00:E0:12:34:56:78 and retry")
    c = BleakClient(dev, timeout=25); await c.connect()
    await c.start_notify(N, lambda _h, d: q.put_nowait(bytes(d)))
    r = await cmd(c, [0x01])
    log("connected:", dev.address, "firmware v%d" % r[3] if r and r[0] == 0x81 else f"(ping reply {r})")
    return c

async def battery(c):
    hist = []
    while True:
        r = await cmd(c, [0x02])
        if r and r[0] == 0x82:
            raw = r[1] | r[2] << 8; mv = r[3] | r[4] << 8; pct = r[5]; err = r[6] - 256 if r[6] > 127 else r[6]
            hist = (hist + [mv])[-10:]
            trend = hist[-1] - hist[0] if len(hist) >= 5 else 0
            state = "CHARGING" if (trend >= 8 or mv >= 4180) else ("not charging" if len(hist) >= 5 else "measuring...")
            log(f"BATTERY {pct:3d}%  {mv} mV  {state}   (raw {raw}, err {err}, trend {trend:+d} mV)")
        else: log("no battery reply", r)
        await asyncio.sleep(3)

async def pins(c, pull):
    r = await cmd(c, [0x05, pull], 5)
    if not r or r[0] != 0x85: log("no reply", r); return
    bits = int.from_bytes(r[1:6], "little"); skipped = int.from_bytes(r[6:11], "little")
    snap = {NAMES[p]: (None if skipped >> p & 1 else bits >> p & 1) for p in NAMES}
    log("pins (pull=%d):" % pull, " ".join(f"{k}={'-' if v is None else v}" for k, v in snap.items()))
    path = os.path.expanduser("~/Projects/dafit-watch/logs/pins_last.json")
    if os.path.exists(path):
        old = json.load(open(path))
        diff = {k: (old.get(k), v) for k, v in snap.items() if old.get(k) != v}
        log("CHANGED since last snapshot:", diff if diff else "nothing")
    json.dump(snap, open(path, "w"))

def qcmd(op, *params): return [0x02, 0x00, op, 0x00, *params]          # QSPI-AMOLED 1-line write frame
async def lcd_raw(c, bytes_): return await cmd(c, [0x06, len(bytes_), *bytes_])
async def lcd_read_id(c):
    out = {}
    for name, w, n in (("QSPI 04", [0x03, 0x00, 0x04, 0x00], 3), ("QSPI DA", [0x03, 0x00, 0xDA, 0x00], 1),
                       ("QSPI DB", [0x03, 0x00, 0xDB, 0x00], 1), ("QSPI DC", [0x03, 0x00, 0xDC, 0x00], 1),
                       ("SPI 04", [0x04], 3), ("QSPI 0A", [0x03, 0x00, 0x0A, 0x00], 1)):
        r = await cmd(c, [0x07, len(w), *w, n])
        if r and r[0] == 0x87:
            nr = r[1]; out[name] = (r[2:2+nr].hex(), r[2+nr:2+2*nr].hex())
    alive = any(any(x not in ("00"*len(x)//2, "ff"*(len(x)//2)) for x in pair) for pair in out.values())
    return alive, out

async def wake(c):
    await lcd_raw(c, qcmd(0x11)); await asyncio.sleep(0.15)
    await lcd_raw(c, qcmd(0x3A, 0x55)); await lcd_raw(c, qcmd(0x53, 0x20)); await lcd_raw(c, qcmd(0x51, 0xFF))
    await lcd_raw(c, qcmd(0x29)); await asyncio.sleep(0.05); await lcd_raw(c, qcmd(0x23))

async def lcdprobe(c):
    log(">>> step 1: read panel ID with nothing changed")
    alive, ids = await lcd_read_id(c); log("    ID reads (D1, D0):", ids, "-> ALIVE" if alive else "-> no answer")
    log(">>> step 2: wake-up + ALL PIXELS ON. LOOK AT THE WATCH SCREEN NOW (5 s)")
    await wake(c); await asyncio.sleep(5)
    cand = [p for p in NAMES if p not in NEVER]
    if not alive:
        log(f">>> step 3: holding {len(cand)} candidate power/reset pins HIGH, then wake again. LOOK AT THE SCREEN (5 s)")
        for p in cand: await cmd(c, [0x03, p, 1], 1)
        await asyncio.sleep(0.3)
        await wake(c)
        alive, ids = await lcd_read_id(c); log("    ID reads:", ids, "-> ALIVE" if alive else "-> no answer")
        await asyncio.sleep(5)
        if alive:
            log(">>> step 4: finding which pins matter (releasing one at a time)")
            need = []
            for p in cand:
                await cmd(c, [0x0A, p], 1); await asyncio.sleep(0.05)
                a, _ = await lcd_read_id(c)
                if not a:
                    need.append(NAMES[p]); await cmd(c, [0x03, p, 1], 1); await asyncio.sleep(0.2); await wake(c)
            log("    PINS THE SCREEN NEEDS HIGH:", need)
        else:
            for p in cand: await cmd(c, [0x0A, p], 1)
            log("    released all pins. Panel never answered -> power is likely via a PMIC/I2C, or a different bus.")
    if alive:
        log(">>> step 5: filling screen ORANGE in bands (LOOK)")
        await lcd_raw(c, qcmd(0x13)); await lcd_raw(c, qcmd(0x2A, 0, 0, 0x01, 0x6F)); await lcd_raw(c, qcmd(0x2B, 0, 0, 0x01, 0xBF))
        for _ in range(10): await cmd(c, [0x09, 0xFB, 0x47, 48, 0], 6)
    log("lcdprobe finished")

async def main():
    a = sys.argv[1:] or ["battery"]
    c = await connect()
    try:
        if a[0] == "battery": await battery(c)
        elif a[0] in ("pins", "lcdprobe"):
            log("DISABLED: 'pins' touches the 32 kHz crystal pins (H_1/H_2) and 'lcdprobe' switches the motor on. Use: bash run.sh hwmap")
        elif a[0] == "out": log(await cmd(c, [0x03, int(a[1]), int(a[2])]))
        elif a[0] == "buzz": log(await cmd(c, [0x08, int(a[1]), 1, 44, 1], 2))
    finally:
        await c.disconnect()

asyncio.run(main())
