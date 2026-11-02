"""HARDWARE MAPPER v2 for the BSW051 running ONKAR-LIFE v2  (robust, one pin at a time).

  Phase 0  reboot the watch -> clean known pin state, reconnect
  Phase A  read each pin with pull-up and pull-down (one pin per command, liveness check after each)
           -> a pin that freezes/resets the watch is marked DANGEROUS, saved, and never touched again
  Phase B  you: charger off vs on, button pressed vs released  -> finds those pins
  Phase C  you: confirm the vibration motor pin (P0_6 / P0_7 suspects)
  Phase D  you: every floating pin pulsed 0.4 s, you say what happened
  Phase E  reboot the watch -> all pins back to default
Saves after every step: logs/hwmap.json, logs/hwmap_danger.json
Usage: bash run.sh hwmap            (Ctrl+C anytime, then: bash run.sh stop)
"""
import asyncio, subprocess, time, json, os, sys

ADDR = "00:E0:12:34:56:78"
W, N = "0000b002-0000-1000-8000-00805f9b34fb", "0000b003-0000-1000-8000-00805f9b34fb"
CP = "00006487-3c17-d293-8e48-14fe2e4da212"
NAME = {**{i: f"P0_{i}" for i in range(8)}, **{8+i: f"P1_{i}" for i in range(8)}, **{16+i: f"P2_{i}" for i in range(8)},
        **{24+i: f"P3_{i}" for i in range(7)}, 32: "P4_0", 33: "P4_1", 34: "P4_2", 35: "P4_3", 36: "H_0", 37: "H_1", 38: "H_2"}
BYNAME = {v: k for k, v in NAME.items()}
LOGDIR = os.environ.get("HWMAP_LOGDIR", os.path.expanduser("~/Projects/dafit-watch/logs"))
OUT, DANGER_FILE = os.path.join(LOGDIR, "hwmap.json"), os.path.join(LOGDIR, "hwmap_danger.json")

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def ask(prompt):
    print("\n>>> " + prompt, flush=True)
    line = sys.stdin.readline()
    return line.strip().lower()

class Watch:
    """BLE link to ONKAR-LIFE. Every call is bounded by a timeout; nothing here can hang forever."""
    def __init__(self):
        self.c = None; self.q = asyncio.Queue()
    async def connect(self, tries=8):
        from bleak import BleakScanner, BleakClient
        for _ in range(tries):
            subprocess.run(["bluetoothctl", "disconnect", ADDR], capture_output=True, timeout=10)
            await asyncio.sleep(2)
            try:
                found = await BleakScanner.discover(timeout=6, return_adv=True)
                dev = next((d for a, (d, adv) in found.items()
                            if a.upper() == ADDR or (adv.local_name or "").startswith("ONKAR")), None)
                if dev:
                    self.c = BleakClient(dev, timeout=20); await self.c.connect()
                    await self.c.start_notify(N, lambda _h, d: self.q.put_nowait(bytes(d)))
                    if await self.ping(): return True
            except Exception as e:
                log("  connect error:", e)
            log("  watch not visible yet, retrying...")
        return False
    async def disconnect(self):
        try:
            if self.c: await self.c.disconnect()
        except Exception: pass
    async def cmd(self, b, wait=3.0):
        while not self.q.empty(): self.q.get_nowait()
        try:
            await asyncio.wait_for(self.c.write_gatt_char(W, bytes(b), response=True), 5)
            while True:
                r = await asyncio.wait_for(self.q.get(), wait)
                if r and r[0] == (b[0] | 0x80): return r
        except Exception:
            return None
    async def ping(self):
        r = await self.cmd([0x01], 2.0)
        return bool(r and len(r) >= 4 and r[1:3] == b"OK")
    async def reboot(self):
        try: await asyncio.wait_for(self.c.write_gatt_char(CP, bytes([0x05]), response=True), 5)
        except Exception: pass
        await self.disconnect()

class Mapper:
    def __init__(self, w):
        self.w = w
        # H_1/H_2 = 32 kHz crystal (Realtek rtl876x.h), H_0 = analog MICBIAS: never touch these
        self.danger = {"H_0", "H_1", "H_2"}
        if os.path.exists(DANGER_FILE): self.danger |= set(json.load(open(DANGER_FILE)))
        self.s = {"classes": {}, "charger": {}, "button": {}, "motor": None, "pulses": {}, "danger": sorted(self.danger)}
    def save(self):
        self.s["danger"] = sorted(self.danger)
        json.dump(self.s, open(OUT, "w"), indent=1); json.dump(sorted(self.danger), open(DANGER_FILE, "w"))
    def safe_pins(self, extra_skip=()):
        return [p for p in NAME if NAME[p] not in self.danger and p not in extra_skip]

    async def recover(self, pin_name):
        log(f"  !! watch stopped answering after touching {pin_name} -> marking it DANGEROUS, reconnecting")
        self.danger.add(pin_name); self.save()
        await self.w.disconnect()
        await asyncio.sleep(8)                                  # give it time to reboot if it reset
        if not await self.w.connect(tries=10):
            log("  watch did not come back. It is probably frozen (not reset).")
            log("  It will restart by itself when the battery runs out and is recharged, or when its watchdog fires.")
            return False
        return True

    async def read_pin(self, p, pull):
        r = await self.w.cmd([0x04, p, pull], 2.0)
        if r and len(r) >= 3 and r[1] == p: return r[2]
        if await self.w.ping(): return None                    # odd reply but watch fine
        ok = await self.recover(NAME[p])
        return "LOST" if not ok else None

    async def snapshot(self, pull, pins):
        out = {}
        for p in pins:
            if NAME[p] in self.danger: continue
            v = await self.read_pin(p, pull)
            if v == "LOST": return None
            if v is not None: out[NAME[p]] = v
        return out

    async def run(self):
        log("PHASE 0: rebooting the watch for a clean pin state")
        if not await self.w.connect(): log("cannot reach the watch - is it frozen? (see notes)"); return
        await self.w.reboot(); await asyncio.sleep(10)
        if not await self.w.connect(): log("watch did not come back after reboot"); return
        log("  ok. known-dangerous pins (skipped):", sorted(self.danger) or "none yet")

        log("PHASE A: classifying every pin (one at a time, ~40 s)")
        pins = self.safe_pins(extra_skip={31})
        up = await self.snapshot(1, pins)
        if up is None: return
        dn = await self.snapshot(2, pins)
        if dn is None: return
        for n in [NAME[p] for p in pins]:
            u, d = up.get(n), dn.get(n)
            if n in self.danger: cls = "DANGEROUS (freezes/resets the watch)"
            elif u is None or d is None: cls = "unreadable"
            elif u == 1 and d == 1: cls = "DRIVEN HIGH (chip output or strong pull-up: I2C/reset/enable/status)"
            elif u == 0 and d == 0: cls = "DRIVEN LOW (chip output, pull-down, or ground)"
            elif u == 1 and d == 0: cls = "floating (no strong driver: free, or input of another chip)"
            else: cls = "odd (high with pull-down, low with pull-up)"
            self.s["classes"][n] = cls
            log(f"  {n:5s} {cls}")
        self.save()
        # I2C buses always need pull-ups -> pairs of DRIVEN HIGH pins are SDA/SCL candidates
        hi = [n for n, c in self.s["classes"].items() if c.startswith("DRIVEN HIGH")]
        log("  DRIVEN HIGH pins (I2C SDA/SCL, resets, enables are among these):", hi)

        log("PHASE B: charger + button")
        bpins = self.safe_pins(extra_skip={31})
        ask("Take the watch OFF the charger, then press Enter")
        off = await self.snapshot(1, bpins); mv_off = await self.battery()
        if off is None: return
        ask("Put it ON the charger and hold it there firmly, then press Enter")
        on = await self.snapshot(1, bpins); mv_on = await self.battery()
        if on is None: return
        ch = {n: [off[n], on[n]] for n in off if n in on and off[n] != on[n]}
        self.s["charger"] = {"pins_changed (off->on)": ch, "battery_raw_off": mv_off, "battery_raw_on": mv_on}
        log("  charger pins changed:", ch or "none", "| battery readings off/on:", mv_off, mv_on); self.save()
        ask("PRESS AND HOLD the side button, and while holding it press Enter")
        pr = await self.snapshot(1, bpins)
        if pr is None: return
        ask("RELEASE the button, then press Enter")
        rl = await self.snapshot(1, bpins)
        if rl is None: return
        bt = {n: [pr[n], rl[n]] for n in pr if n in rl and pr[n] != rl[n]}
        self.s["button"] = bt
        log("  button pins changed:", bt or "none (may be a power key wired to the charger/PMIC, not a GPIO)"); self.save()

        log("PHASE C: vibration motor")
        for n in ("P0_6", "P0_7", "P4_3"):     # the screen probe drove these three high when the motor started
            if n in self.danger: continue
            await self.w.cmd([0x08, BYNAME[n], 1, 0x90, 0x01], 3)      # 400 ms high, then held LOW
            a = ask(f"Did the watch VIBRATE just now? (pulse on {n})  y / n")
            if a.startswith("y"): self.s["motor"] = n; log(f"  MOTOR = {n}"); break
        self.save()

        log("PHASE D: pulse test")
        skip = {31, BYNAME["P0_6"], BYNAME["P0_7"], BYNAME["P4_3"]}
        cand = [p for p in self.safe_pins(extra_skip=skip) if self.s["classes"].get(NAME[p], "").startswith("floating")]
        log(f"  {len(cand)} floating pins:", [NAME[p] for p in cand])
        log("  answer: Enter = nothing | v = vibration | s = screen | l = light | o = other")
        for p in cand:
            r = await self.w.cmd([0x08, p, 1, 0x90, 0x01], 3)
            if r is None and not await self.w.ping():
                if not await self.recover(NAME[p]): return
                self.s["pulses"][NAME[p]] = "watch reset/froze"; self.save(); continue
            await self.w.cmd([0x0A, p], 2)
            a = ask(f"{NAME[p]} pulsed - what happened?")
            if a:
                note = {"v": "vibration", "s": "screen", "l": "light"}.get(a, a)
                if a == "o": note = ask("describe it in a few words:") or "other"
                self.s["pulses"][NAME[p]] = note; self.save(); log(f"  {NAME[p]} -> {note}")
                if a == "v": await self.w.cmd([0x03, p, 0], 2)
        self.save()

        log("PHASE E: reboot (all pins back to default)")
        await self.w.reboot()
        log("RESULT:\n" + json.dumps({k: self.s[k] for k in ("charger", "button", "motor", "pulses", "danger")}, indent=1))
        log("saved", OUT)

    async def battery(self):
        r = await self.w.cmd([0x02], 3)
        return {"raw": r[1] | r[2] << 8, "mV_guess": r[3] | r[4] << 8} if r and len(r) >= 5 else None

async def main():
    m = Mapper(Watch())
    try: await m.run()
    finally:
        m.save(); await m.w.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
