"""Laptop side of ONKAR-LIFE v3.  Every run is logged by run.sh into logs/.

  bash run.sh tool3 status        firmware version, uptime, watchdog, reset reason
  bash run.sh tool3 motor         buzzes the 3 motor suspects one by one, you say which one buzzed
  bash run.sh tool3 findbattery   charger unplugged vs plugged: finds the battery ADC pin + charger pin
  bash run.sh tool3 battery       live battery %, voltage, charging (Ctrl+C to stop)
  bash run.sh tool3 i2c           finds I2C buses + chips (touch, motion sensor, heart-rate...)
  bash run.sh tool3 lcdhunt       finds the display wires by asking every pin combination for a panel ID
  bash run.sh tool3 lcdtest CS CLK MOSI   tries to wake the panel and paint it red/green/blue
  bash run.sh tool3 auto          status -> motor -> (findbattery if battery is in) -> i2c -> lcdhunt
  bash run.sh tool3 release       let go of every pin the watch is driving

Findings are saved in logs/hw.json and reused by the next command.
"""
import asyncio, sys, time, json, os, subprocess
from bleak import BleakScanner, BleakClient

ADDR = "00:E0:12:34:56:78"
W = "0000b002-0000-1000-8000-00805f9b34fb"
N = "0000b003-0000-1000-8000-00805f9b34fb"
NAMES = {**{i: f"P0_{i}" for i in range(8)}, **{8 + i: f"P1_{i}" for i in range(8)},
         **{16 + i: f"P2_{i}" for i in range(8)}, **{24 + i: f"P3_{i}" for i in range(7)},
         32: "P4_0", 33: "P4_1", 34: "P4_2", 35: "P4_3"}
VALID = sorted(NAMES)                      # firmware refuses 31 and H_0/H_1/H_2 anyway
MOTOR_SUSPECTS = [6, 7, 35, 32, 33, 34]   # every pin the v2 screen probe touched when it started buzzing
HERE = os.path.dirname(os.path.abspath(__file__))
HWJ = os.path.join(HERE, "logs", "hw.json")
I2C_KNOWN = {0x15: "touch (CST816/CST716 family)", 0x38: "touch (FT6x06/FT3x68)", 0x5D: "touch (GT911)",
             0x2E: "touch (Hynitron/HYN)", 0x18: "motion sensor (SC7A20/LIS3DH/BMA4xx)",
             0x19: "motion sensor (SC7A20/LIS3DH)", 0x0F: "motion sensor (STK8321/KX)", 0x68: "motion sensor (BMI/MPU)",
             0x6A: "motion sensor (LSM6/QMI8658)", 0x6B: "motion sensor (LSM6/QMI8658)", 0x12: "motion (QMA7981)",
             0x44: "heart-rate (HRS3300)", 0x33: "heart-rate (VC31/VC32)", 0x57: "heart-rate/SpO2 (MAX3010x)",
             0x51: "RTC (PCF8563)", 0x55: "fuel gauge (BQ27xxx)", 0x36: "fuel gauge (MAX1704x)"}
q = asyncio.Queue()


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_hw():
    try:
        return json.load(open(HWJ))
    except Exception:
        return {}


def save_hw(**kv):
    hw = load_hw()
    hw.update(kv)
    json.dump(hw, open(HWJ, "w"), indent=1)
    log("saved to logs/hw.json:", kv)


def pn(p):
    return NAMES.get(p, str(p))


class WatchGone(Exception):
    pass


async def cmd(c, b, wait=4.0):
    while not q.empty():
        q.get_nowait()
    if not c.is_connected:
        raise WatchGone()
    if wait > 10:
        # long jobs (display hunt): don't let a slow write-acknowledge abort us; the answer comes as a notification
        async def _w():
            try:
                await c.write_gatt_char(W, bytes(b), response=True)
            except Exception as e:
                log("(write ack slow:", type(e).__name__, "- still waiting for the answer)")
        asyncio.ensure_future(_w())
    else:
        try:
            await c.write_gatt_char(W, bytes(b), response=True)
        except Exception as e:
            if not c.is_connected:
                raise WatchGone()
            log("command 0x%02X failed: %s" % (b[0], e))
            return None
    try:
        return await asyncio.wait_for(q.get(), wait)
    except asyncio.TimeoutError:
        return None


async def connect():
    subprocess.run(["bluetoothctl", "disconnect", ADDR], capture_output=True, timeout=10)
    await asyncio.sleep(2)
    dev = None
    for attempt in range(2):
        found = await BleakScanner.discover(timeout=8, return_adv=True)
        dev = next((d for a, (d, adv) in found.items()
                    if (adv.local_name or "").startswith("ONKAR") or a.upper() == ADDR), None)
        if dev:
            break
        log("not seen yet - clearing the laptop's old 'keyboard' record and scanning again")
        subprocess.run(["bluetoothctl", "remove", ADDR], capture_output=True, timeout=10)
        await asyncio.sleep(2)
    if not dev:
        raise SystemExit("ONKAR-LIFE not advertising. Run: bash waitfor.sh   (it beeps when the watch is back)")
    c = BleakClient(dev, timeout=25)
    await c.connect()
    await c.start_notify(N, lambda _h, d: q.put_nowait(bytes(d)))
    r = await cmd(c, [0x01])
    ver = r[3] if r and r[0] == 0x81 else None
    log("connected:", dev.address, f"firmware v{ver}" if ver else f"(ping reply {r})")
    if ver is not None and ver < 3:
        raise SystemExit("watch runs v%d - flash v3 first: bash run.sh ota_flash --go firmware/v3/app_MP.bin" % ver)
    return c


# ---------------------------------------------------------------- status

RESET = {0x00: "power-on / hardware reset", 0x01: "WATCHDOG fired (it froze and rebooted itself)",
         0xD4: "firmware update finished", 0xD5: "firmware update failed", 0xD3: "switched to OTA mode"}


async def status(c):
    r = await cmd(c, [0x10])
    if not r or r[0] != 0x90:
        log("no status reply", r)
        return
    up = int.from_bytes(r[2:6], "little")
    driven = int.from_bytes(r[8:13], "little")
    log(f"firmware v{r[1]}  uptime {up // 60}m{up % 60:02d}s  last reset: {RESET.get(r[6], hex(r[6]))} (best guess, chip says it may be unreliable)")
    log("watchdog:", "ARMED (8 s)" if r[7] & 1 else "not armed yet", "| paused for update" if r[7] & 2 else "",
        "| heartbeats", int.from_bytes(r[13:17], "little"))
    log("pins being driven:", [pn(p) for p in VALID if driven >> p & 1] or "none")


async def release(c):
    r = await cmd(c, [0x0B])
    log("released", r[1] if r else "?", "pins")


# ---------------------------------------------------------------- pins + adc

async def read_all(c, pull):
    r = await cmd(c, [0x05, pull], 6)
    if not r or r[0] != 0x85:
        return None
    bits = int.from_bytes(r[1:6], "little")
    skipped = int.from_bytes(r[6:11], "little")
    return {p: (bits >> p & 1) for p in VALID if not skipped >> p & 1}


async def adc_sweep(c):
    r = await cmd(c, [0x11], 6)
    if not r or r[0] != 0x91:
        return None
    out = {}
    for i in range(9):
        raw = int.from_bytes(r[1 + 4 * i:3 + 4 * i], "little")
        mv = int.from_bytes(r[3 + 4 * i:5 + 4 * i], "little")
        out["VBAT" if i == 8 else f"P2_{i}"] = None if raw == 0xFFFF else mv
    return out


async def sample(c, n=4):
    adcs, pins_none, pins_down = [], [], []
    for _ in range(n):
        adcs.append(await adc_sweep(c))
        pins_none.append(await read_all(c, 0))
        pins_down.append(await read_all(c, 2))
        await asyncio.sleep(1)
    avg = {}
    for k in adcs[0]:
        vals = [a[k] for a in adcs if a and a[k] is not None]
        avg[k] = round(sum(vals) / len(vals)) if vals else None
    def stable(snaps):
        out = {}
        for p in VALID:
            v = {s[p] for s in snaps if s and p in s}
            out[p] = v.pop() if len(v) == 1 else "flicker"
        return out
    return avg, stable(pins_none), stable(pins_down)


def ask(prompt):
    try:
        return input(time.strftime("%H:%M:%S") + " >>> " + prompt + " ").strip().lower()
    except EOFError:
        return ""


async def findbattery(c):
    ask("UNPLUG the charger, then press Enter")
    log("measuring (unplugged)...")
    a0, n0, d0 = await sample(c)
    log("ADC unplugged (mV):", a0)
    ask("Now PLUG the charger in, wait 3 seconds, press Enter")
    log("measuring (charging)...")
    a1, n1, d1 = await sample(c)
    log("ADC charging  (mV):", a1)
    rows = []
    for k in a0:
        if a0[k] is None or a1[k] is None:
            continue
        rows.append((a1[k] - a0[k], k, a0[k], a1[k]))
    rows.sort(reverse=True)
    for dlt, k, x, y in rows:
        log(f"  {k:5s} {x:5d} -> {y:5d} mV  ({dlt:+d})")
    # battery through a divider sits at ~1.6-2.2 V and rises a little on charge; a charger-sense pin jumps a lot
    batt = [k for dlt, k, x, y in rows if k != "VBAT" and 1300 <= x <= 2300 and dlt >= 5]
    chg_adc = [k for dlt, k, x, y in rows if k != "VBAT" and dlt >= 800]
    chg_pins = sorted({p for p in VALID if n0.get(p) in (0, 1) and n1.get(p) in (0, 1) and n0[p] != n1[p]} |
                      {p for p in VALID if d0.get(p) in (0, 1) and d1.get(p) in (0, 1) and d0[p] != d1[p]})
    log("pins that changed when the charger went in:", [f"{pn(p)} {n0.get(p)}->{n1.get(p)} (pull-down {d0.get(p)}->{d1.get(p)})" for p in chg_pins] or "none")
    log("battery ADC candidates (1.3-2.3 V and rising):", batt or "none")
    log("charger-sense ADC candidates:", chg_adc or "none")
    if not batt and a0.get("VBAT") and a1.get("VBAT") and a1["VBAT"] - a0["VBAT"] >= 30:
        log("VBAT itself rose on charge -> the chip's own VBAT pin is the battery after all")
        batt = ["VBAT"]
    if not batt:
        flat = [k for dlt, k, x, y in rows if k != "VBAT" and 1300 <= x <= 2300]
        if flat:
            log(f"no channel ROSE on charge, but {flat} sits in battery range - using {flat[0]} (UNCERTAIN: check the battery wires are making contact)")
            batt = flat[:1]
    if not batt:
        log("NO battery channel found. Paste this log to Claude - the battery may sit on a pin outside P2_0..P2_7.")
    save_hw(battery_adc=batt[0] if batt else None, battery_unplugged_mv=a0.get(batt[0]) if batt else None,
            charger_pins=chg_pins, charger_pin_unplugged={str(p): n0.get(p) for p in chg_pins},
            charger_adc=chg_adc, adc_unplugged=a0, adc_charging=a1)


PCT = [(3400, 0), (3500, 6), (3600, 14), (3650, 22), (3700, 32), (3750, 42), (3800, 52), (3900, 65), (4000, 78), (4100, 90), (4200, 100)]


def pct(mv):
    if mv <= PCT[0][0]:
        return 0
    for (m0, p0), (m1, p1) in zip(PCT, PCT[1:]):
        if mv <= m1:
            return round(p0 + (mv - m0) * (p1 - p0) / (m1 - m0))
    return 100


async def battery(c):
    hw = load_hw()
    ch = hw.get("battery_adc")
    ratio = hw.get("battery_ratio", 2.0 if ch and ch != "VBAT" else 1.0)
    chg_pins = hw.get("charger_pins", [])
    if not ch:
        log("battery pin not known yet -> run: bash run.sh tool3 findbattery   (showing raw values meanwhile)")
    else:
        log(f"battery on {ch}, divider ratio {ratio} (ASSUMED 1:2 unless you calibrated it - compare with a multimeter once)")
    hist = []
    while True:
        a = await adc_sweep(c)
        if not a:
            log("no reply")
            await asyncio.sleep(3)
            continue
        line = " ".join(f"{k}={v}" for k, v in a.items())
        if ch and a.get(ch):
            mv = round(a[ch] * ratio)
            hist = (hist + [mv])[-10:]
            trend = hist[-1] - hist[0] if len(hist) >= 5 else 0
            state = ""
            unpl = hw.get("charger_pin_unplugged") or {}
            if chg_pins and unpl:
                snap = await read_all(c, 0)
                if snap:
                    plugged = any(snap.get(p) is not None and snap[p] != unpl.get(str(p)) for p in chg_pins)
                    state = "CHARGING (charger pin)" if plugged else "not charging (charger pin)"
            if not state:
                state = "CHARGING (by trend)" if trend >= 10 else ("not charging" if len(hist) >= 5 else "measuring...")
            log(f"BATTERY {pct(mv):3d}%  {mv} mV  {state}    [{line}]")
        else:
            log("raw mV:", line)
        await asyncio.sleep(3)


# ---------------------------------------------------------------- motor

async def motor(c):
    found = None
    k = len(MOTOR_SUSPECTS)
    for i, p in enumerate(MOTOR_SUSPECTS, 1):
        ask(f"[{i}/{k}] Hold the watch. Press Enter: {pn(p)} goes HIGH for 0.5 s, then LOW for 0.5 s")
        await cmd(c, [0x08, p, 1, 0xF4, 0x01], 4)
        await asyncio.sleep(0.3)
        await cmd(c, [0x08, p, 0, 0xF4, 0x01], 4)
        a = ask("Did it vibrate at all? (y/n)")
        if a.startswith("y"):
            found = p
            break
    await release(c)
    if found is None:
        log("none of them buzzed (on charger-only power the motor may also just lack current) - moving on")
    else:
        log("MOTOR =", pn(found))
    save_hw(motor=found)


# ---------------------------------------------------------------- i2c

async def i2c(c):
    hw = load_hw()
    skip = {hw.get("motor")} | set(MOTOR_SUSPECTS)
    down = await read_all(c, 2)
    up = await read_all(c, 1)
    if not down:
        log("pin read failed")
        return
    # an I2C line has a pull-up resistor on the board: it stays HIGH even when we pull it down
    cands = [p for p in VALID if down.get(p) == 1 and p not in skip]
    log("pins held high by the board (I2C suspects):", [pn(p) for p in cands])
    buses = []
    for scl in cands:
        for sda in cands:
            if scl == sda:
                continue
            r = await cmd(c, [0x12, scl, sda], 6)
            if not r or r[0] != 0x92:
                continue
            if r[1] == 0 and r[2] > 0:
                addrs = [a for a in range(0x08, 0x78) if r[3 + (a >> 3)] >> (a & 7) & 1]
                if len(addrs) > 20:
                    continue                      # every address 'answering' = not a real bus
                log(f"I2C BUS  SCL={pn(scl)} SDA={pn(sda)}:", ", ".join(f"0x{a:02X} {I2C_KNOWN.get(a, '?')}" for a in addrs))
                buses.append({"scl": scl, "sda": sda, "addrs": addrs})
    await release(c)
    if not buses:
        log("no I2C chips found (touch/sensors may be powered off or need a reset pin first)")
    for b in buses:
        for a in b["addrs"]:
            for reg in (0x0F, 0x00, 0xA7, 0xA8, 0x75, 0x01):
                r = await cmd(c, [0x13, b["scl"], b["sda"], a, reg, 1], 4)
                if r and r[0] == 0x93 and r[1] == 0:
                    log(f"   0x{a:02X} reg 0x{reg:02X} = 0x{r[3]:02X}")
    await release(c)
    save_hw(i2c=buses)


# ---------------------------------------------------------------- display hunt

PROTO = {0: "SPI RDDID 0x04", 1: "QSPI-AMOLED read 03-00-04-00", 2: "3-wire 9-bit LCD"}


def mask_of(pins):
    m = 0
    for p in pins:
        m |= 1 << p
    return list(m.to_bytes(5, "little"))


async def hunt(c, rst, cands, protos=0):
    t = time.time()
    r = await cmd(c, [0x15, 0xFF if rst is None else rst, protos << 4, *mask_of(cands)], 90)
    if not r or r[0] != 0x95:
        log("hunt: no reply", r)
        return []
    hits = []
    for i in range(r[3]):
        h = r[4 + 9 * i:13 + 9 * i]
        hits.append({"cs": h[0], "clk": h[1], "mosi": h[2], "miso": h[3], "proto": h[4], "data": h[5:9].hex()})
    log(f"hunt rst={pn(rst) if rst is not None else 'none'}: {r[2]} pins, {len(hits)} hits, {time.time() - t:.1f}s")
    return hits


async def lcdhunt(c):
    hw = load_hw()
    skip = set()
    if hw.get("motor") is not None:
        skip.add(hw["motor"])
    for b in hw.get("i2c", []):
        skip |= {b["scl"], b["sda"]}
    skip |= set(hw.get("charger_pins", []))
    base = [p for p in VALID if p not in skip]
    # P3_4..P3_6 and P4_0..P4_2 share GPIO lines inside the chip, so they are hunted in two passes.
    # Realtek's reference board puts the screen on P4_x, so that pass goes first.
    passes = [[p for p in base if p not in (28, 29, 30)], [p for p in base if p not in (32, 33, 34)]]
    log("skipping", [pn(p) for p in sorted(skip)] or "nothing")
    all_hits = []
    for i, cands in enumerate(passes, 1):
        await release(c)
        log(f"pass {i}/2: {len(cands)} pins, every CS/CLK/DATA combination (can take up to a minute)...")
        all_hits = await hunt(c, None, cands)
        if all_hits:
            break
    if not all_hits:
        log("no answer without a reset pulse. Trying each pin as the display RESET (up to ~1 min each, Ctrl+C is safe)...")
        for i, cands in enumerate(passes, 1):
            for n, rst in enumerate(cands, 1):
                await release(c)
                log(f"  pass {i}, reset candidate {n}/{len(cands)}: {pn(rst)}")
                h = await hunt(c, rst, cands)
                for x in h:
                    x["rst"] = rst
                all_hits += h
                if h:
                    break
            if all_hits:
                break
    await release(c)
    if not all_hits:
        log("NO DISPLAY ANSWER. Possible reasons: panel needs a power-enable pin, or it never answers reads. Send this log to Claude.")
        save_hw(lcd_hits=[])
        return
    # group identical wiring
    seen = {}
    for x in all_hits:
        k = (x["cs"], x["clk"], x["mosi"], x["miso"], x["proto"], x.get("rst"))
        seen.setdefault(k, x)
    for k, x in seen.items():
        log(f"DISPLAY? CS={pn(x['cs'])} CLK={pn(x['clk'])} MOSI={pn(x['mosi'])} MISO={pn(x['miso'])} "
            f"RST={pn(x['rst']) if x.get('rst') is not None else '-'}  {PROTO[x['proto']]}  answer={x['data']}")
    best = all_hits[0]
    log(f"next: bash run.sh tool3 lcdtest {best['cs']} {best['clk']} {best['mosi']}")
    save_hw(lcd_hits=list(seen.values()), lcd=best)


# ---------------------------------------------------------------- display test

async def spi(c, cs, clk, mosi, data, flags=0, miso=0xFF, nr=0, dc=0):
    return await cmd(c, [0x16, cs, clk, mosi, miso, dc, flags, len(data), *data, nr], 4)


async def fill(c, cs, clk, mosi, header, rgb565, count, flags=0):
    return await cmd(c, [0x17, cs, clk, mosi, 0, flags, len(header), *header, rgb565 >> 8, rgb565 & 0xFF,
                         *count.to_bytes(4, "little")], 30)


async def lcdtest(c, cs, clk, mosi):
    hw = load_hw()
    rst = (hw.get("lcd") or {}).get("rst")
    if rst is not None:
        await cmd(c, [0x03, rst, 0]); await asyncio.sleep(0.02); await cmd(c, [0x03, rst, 1]); await asyncio.sleep(0.15)
    W_, H_ = 368, 448
    # 1) QSPI AMOLED drivers (SH8601 / CO5300 / ICNA3311 / RM67162) in 1-line mode: 02 00 CMD 00 params
    q = lambda cmd_, *p: [0x02, 0x00, cmd_, 0x00, *p]
    log("trying QSPI-AMOLED wake-up...")
    for f in (q(0x11),):
        await spi(c, cs, clk, mosi, f)
    await asyncio.sleep(0.15)
    for f in (q(0x3A, 0x55), q(0x53, 0x20), q(0x51, 0xFF), q(0x2A, 0, 0, (W_ - 1) >> 8, (W_ - 1) & 0xFF),
              q(0x2B, 0, 0, (H_ - 1) >> 8, (H_ - 1) & 0xFF), q(0x29)):
        await spi(c, cs, clk, mosi, f)
    for name, col in (("RED", 0xF800), ("GREEN", 0x07E0), ("BLUE", 0x001F)):
        await fill(c, cs, clk, mosi, [0x02, 0x00, 0x2C, 0x00], col, W_ * H_)
        log("painted", name, "- look at the screen")
        await asyncio.sleep(1.5)
    a = ask("Did the screen light up / change colour? (y/n)")
    if a.startswith("y"):
        save_hw(lcd_working={"cs": cs, "clk": clk, "mosi": mosi, "rst": rst, "mode": "qspi-1line"})
        return
    # 2) plain 3-wire 9-bit LCD (ST7789-like)
    log("trying 3-wire 9-bit LCD wake-up...")
    for f in ([0x11],):
        await spi(c, cs, clk, mosi, f, flags=1)
    await asyncio.sleep(0.15)
    for f in ([0x3A, 0x55], [0x2A, 0, 0, (W_ - 1) >> 8, (W_ - 1) & 0xFF], [0x2B, 0, 0, (H_ - 1) >> 8, (H_ - 1) & 0xFF], [0x29]):
        await spi(c, cs, clk, mosi, f, flags=1)
    await fill(c, cs, clk, mosi, [0x2C], 0xF800, W_ * H_, flags=1)
    a = ask("Red now? (y/n)")
    if a.startswith("y"):
        save_hw(lcd_working={"cs": cs, "clk": clk, "mosi": mosi, "rst": rst, "mode": "9bit"})
        return
    log("no picture. If it's an LCD, the backlight (LEDK) may be on a separate pin - send this log to Claude.")
    await release(c)


# ---------------------------------------------------------------- main

async def main():
    a = sys.argv[1:] or ["status"]
    c = await connect()
    try:
        if a[0] == "status":
            await status(c)
        elif a[0] == "release":
            await release(c)
        elif a[0] == "motor":
            await motor(c)
        elif a[0] == "findbattery":
            await findbattery(c)
        elif a[0] == "battery":
            await battery(c)
        elif a[0] == "i2c":
            await i2c(c)
        elif a[0] == "lcdhunt":
            await lcdhunt(c)
        elif a[0] == "lcdtest":
            await lcdtest(c, int(a[1]), int(a[2]), int(a[3]))
        elif a[0] == "auto":
            await status(c)
            await motor(c)
            if ask("Is the BATTERY connected right now? (y/n)").startswith("y"):
                await findbattery(c)
            else:
                log("skipping the battery test (unplugging the charger would switch the watch off)")
            await i2c(c)
            await lcdhunt(c)
            hw = load_hw()
            if hw.get("lcd"):
                L = hw["lcd"]
                await lcdtest(c, L["cs"], L["clk"], L["mosi"])
            log("ALL DONE - tell Claude 'done'")
        else:
            print(__doc__)
    finally:
        try:
            if c.is_connected:
                await cmd(c, [0x0B], 2)
                await c.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped (Ctrl+C). The watch releases its pins by itself within 30 s.")
    except WatchGone:
        print(time.strftime("%H:%M:%S"), "WATCH DISCONNECTED (lost power?). Results so far are in logs/hw.json. Run: bash waitfor.sh")
