"""Fully automatic screen finder (needs firmware v7).
   bash run.sh find_screen          Ctrl+C to stop.  No questions until it has found something.

What it does, by itself:
  1. For "no power pin" and then every pin as the screen's POWER switch (HIGH and LOW),
     the watch pulses every other pin as the screen's RESET and asks the screen for its ID
     4 different ways. The watch only reports an answer if it is real (repeatable, a real
     bit pattern, and gone when the screen is NOT selected).
  2. If the watch freezes on some pin, it reboots itself (watchdog); the script marks that pin
     and carries on.
  3. When the screen answers: wakes it, checks the screen chip says "display on", paints colours,
     and sweeps backlight candidates. Only then it asks you what you saw.
"""
import asyncio, time
from tool5 import (connect, cmd, ask, log, pn, load_hw, save_hw, WatchGone, VALID, alive,
                   watch_back, NOT_DISPLAY, mask_of)

BUSES = [  # (cs, clk, sio, d1) - this chip's hardware screen pins first, then wiring variants
    (35, 32, 34, 33),
    (35, 32, 33, 34),
    (32, 35, 34, 33),
]
PROTO = {0: "SPI 8-bit", 1: "QSPI 1-line (03-00-cmd-00)", 2: "3-wire 9-bit", 3: "QSPI fast-read (0B)"}
W, H = 368, 448


async def search(c, bus, pwr, lvl, rmask):
    cs, clk, sio, d1 = bus
    r = await cmd(c, [0x1A, cs, clk, sio, d1, 0xFF if pwr is None else pwr, lvl, *mask_of(rmask), 1], 15)
    if not r or r[0] != 0x9A:
        return None
    hits = []
    for i in range(r[1]):
        h = r[2 + 7 * i:9 + 7 * i]
        hits.append({"rst": None if h[0] == 0xFF else h[0], "proto": h[1], "line": "d1" if h[2] else "sio",
                     "id": h[3:7].hex()})
    return hits


def frame(proto, cmd_, *params):
    if proto in (1, 3):
        return [0x02, 0x00, cmd_, 0x00, *params], 0
    if proto == 2:
        return [cmd_, *params], 1
    return [cmd_, *params], 0


async def send(c, bus, proto, cmd_, *params):
    cs, clk, sio, d1 = bus
    f, fl = frame(proto, cmd_, *params)
    await cmd(c, [0x16, cs, clk, sio, 0xFF, 0, fl, len(f), *f, 0])


async def read_reg(c, bus, proto, reg, line):
    cs, clk, sio, d1 = bus
    miso = sio if line == "sio" else d1
    if proto in (1, 3):
        f, fl = [0x03, 0x00, reg, 0x00], 0
    else:
        f, fl = [reg], (1 if proto == 2 else 0)
    r = await cmd(c, [0x16, cs, clk, sio, miso, 0, fl, len(f), *f, 2])
    return bytes(r[2:4]).hex() if r and r[0] == 0x96 else None


async def paint(c, bus, proto, color):
    cs, clk, sio, d1 = bus
    if proto in (1, 3):
        hdr, fl = [0x02, 0x00, 0x2C, 0x00], 0
    else:
        hdr, fl = [0x2C], (1 if proto == 2 else 0)
    await cmd(c, [0x17, cs, clk, sio, 0, fl, len(hdr), *hdr, color >> 8, color & 0xFF,
                  *(W * H).to_bytes(4, "little")], 40)


async def light_it(c, bus, hit, pwr, lvl, cands):
    proto = hit["proto"]
    log(f"Waking the screen ({PROTO[proto]})...")
    await send(c, bus, proto, 0x01)                 # software reset
    await asyncio.sleep(0.15)
    await send(c, bus, proto, 0x11)                 # sleep out
    await asyncio.sleep(0.15)
    for args in ((0x3A, 0x55), (0x36, 0x00), (0x53, 0x20), (0x51, 0xFF),
                 (0x2A, 0, 0, (W - 1) >> 8, (W - 1) & 0xFF), (0x2B, 0, 0, (H - 1) >> 8, (H - 1) & 0xFF), (0x29,)):
        await send(c, bus, proto, *args)
    pm = await read_reg(c, bus, proto, 0x0A, hit["line"])
    log(f"screen chip power-mode register 0x0A = {pm}  (bit 0x04 = display ON, 0x10 = awake)")
    save_hw(screen_power_mode=pm)
    for name, col in (("WHITE", 0xFFFF), ("RED", 0xF800), ("GREEN", 0x07E0), ("BLUE", 0x001F)):
        await paint(c, bus, proto, col)
        log(f"painted {name}")
        await asyncio.sleep(1.0)
    a = ask("LOOK AT THE WATCH: did you see white/red/green/blue? (y/n)")
    if a.startswith("y"):
        save_hw(screen_working=True)
        return True
    log("Panel says it's on but nothing visible -> probably the BACKLIGHT. Painting white and sweeping backlight pins...")
    await paint(c, bus, proto, 0xFFFF)
    for level in (1, 0):
        for i, p in enumerate(cands, 1):
            if p in (pwr, hit["rst"]):
                continue
            print(f"\r   #{level}{i:02d} {pn(p)} {'HIGH' if level else 'LOW'}   ", end="", flush=True)
            try:
                await cmd(c, [0x08, p, level, 0xB0, 0x04], 4)     # 1.2 s on, then back
            except WatchGone:
                c = await watch_back(c)
                return False
        print()
    a = ask("Did the screen glow at any number? Type it (e.g. 107 or 012), or Enter for no:")
    save_hw(backlight_seen=a)
    return bool(a.strip())


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 7:
        raise SystemExit("flash v7 first: bash run.sh ota_flash --go firmware/v7/app_MP.bin")
    t0 = time.time()
    try:
        for bus in BUSES:
            hw = load_hw()
            danger = set(hw.get("danger", []))
            busset = set(bus) | {6, 7}                      # P0_6 = screen D2, P0_7 = motor
            cands = [p for p in VALID if p not in danger and p not in NOT_DISPLAY and p not in busset]
            log(f"BUS CS={pn(bus[0])} CLK={pn(bus[1])} DATA={pn(bus[2])}/{pn(bus[3])}: "
                f"{1 + 2 * len(cands)} power options x {len(cands) + 1} reset options")
            plan = [(None, 0)] + [(p, l) for p in cands for l in (1, 0)]
            for k, (pwr, lvl) in enumerate(plan, 1):
                rmask = [p for p in cands if p != pwr]
                label = "no power pin" if pwr is None else f"power {pn(pwr)}={'HIGH' if lvl else 'LOW'}"
                print(f"\r   [{k:2d}/{len(plan)}] {label:22s}", end="", flush=True)
                try:
                    hits = await search(c, bus, pwr, lvl, rmask)
                except WatchGone:
                    hits = None
                if hits is None:
                    if not await alive(c):
                        print()
                        log(f"watch froze with {label} - marking {pn(pwr)} as never-touch, it reboots itself")
                        if pwr is not None:
                            d = set(load_hw().get("danger", []))
                            d.add(pwr)
                            save_hw(danger=sorted(d))
                        c = await watch_back(c)
                    continue
                if hits:
                    print()
                    for h in hits:
                        log(f"SCREEN ANSWERED  {label}  reset={pn(h['rst']) if h['rst'] is not None else '-'}  "
                            f"{PROTO[h['proto']]} on {h['line']}  id={h['id']}")
                    best = hits[0]
                    save_hw(screen={"bus": bus, "pwr": pwr, "pwr_level": lvl, **best})
                    log(f"found in {time.time() - t0:.0f} s")
                    ok = await light_it(c, bus, best, pwr, lvl, cands)
                    log("SCREEN WORKS" if ok else "screen chip found and talking; picture not confirmed yet - send this log")
                    return
            print()
        log(f"No screen chip answered on any wiring/power/reset combo ({time.time() - t0:.0f} s).")
        log("Most likely: the screen's flex cable is unplugged/loose (the watch was opened), or its power")
        log("comes from a power-management chip over I2C. Paste this log to Claude.")
        save_hw(screen=None)
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
        print("\nstopped.")
