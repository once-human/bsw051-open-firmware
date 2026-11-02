"""Switch on the screen/sensor power rail, gently, then find the screen.  Fully automatic.
   bash run.sh power_up        (Ctrl+C to stop; only asks you something once the screen is found)

Why: with our firmware NOTHING on the board has a pull-up (no touch, no sensors, no screen answering).
That's what a board looks like when its peripheral power switch is OFF. The stock firmware switched it on;
ours never did. Two pins (P2_3, P2_5) froze the watch the instant we drove them HIGH - the classic sign of
a power switch: the rail's capacitors gulp current and, with no battery, the supply dips and the chip resets.
Here those pins are switched on SLOWLY (PWM ramp) so the rail charges without the dip.
"""
import asyncio, time
from tool5 import connect, cmd, ask, log, pn, load_hw, save_hw, WatchGone, VALID, alive, watch_back, mask_of
from find_screen import BUSES, PROTO, light_it

FIRST = [19, 13, 11, 12]      # P2_3 (ramps on fine), P1_5 + P1_3 + P1_4 (pulled up at boot - unusual)
NEVER = {3, 8, 9, 20, 24, 25, 21}   # log UART, SWD, button, HCI UART, P2_5 = VIBRATION MOTOR (confirmed)
BUSP = {6, 7, 32, 33, 34, 35}


async def safe(c, msg, timeout=8):
    try:
        r = await cmd(c, msg, timeout)
    except WatchGone:
        r = None
    if r is None and not await alive(c):
        return await watch_back(c), None, True
    return c, r, False


async def pullups(c, skip):
    hi = []
    for p in VALID:
        if p in skip:
            continue
        c, r, dead = await safe(c, [0x04, p, 2])
        if dead:
            return c, None
        if r and r[0] == 0x84 and r[2] == 1:
            hi.append(p)
    return c, hi


async def try_power(c, held, pin):
    """soft-start pin HIGH on top of the already-held pins. returns (c, ok)"""
    for ramp_arg, label in ((50, "0.5 s ramp"), (250, "2.5 s ramp")):
        for p in held:                              # re-assert (a reboot would have dropped them)
            await safe(c, [0x1B, p, 1, 5])
        log(f"  switching {pn(pin)} on ({label})...")
        c, r, dead = await safe(c, [0x1B, pin, 1, ramp_arg], 10)
        if not dead and r and r[0] == 0x9B and await alive(c):
            await asyncio.sleep(0.3)
            return c, True
        log(f"  {pn(pin)} still dropped the watch with a {label}")
    return c, False


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 8:
        raise SystemExit("flash v8 first: bash run.sh ota_flash --go firmware/v8/app_MP.bin")
    hw = load_hw()
    others = [p for p in VALID if p not in NEVER | BUSP | set(FIRST)]
    held = []
    c, base = await pullups(c, NEVER | BUSP)
    log("pulled-up pins BEFORE switching anything on:", [pn(p) for p in base or []] or "none")
    bus = BUSES[0]
    cs, clk, sio, d1 = bus
    for lvl in (1, 0):
        for pin in FIRST + others:
            word = "HIGH" if lvl else "LOW"
            log(f"power candidate {pn(pin)} {word}")
            c, r, dead = await safe(c, [0x1B, pin, lvl, 50], 10)
            if dead or not r:
                log(f"  {pn(pin)} {word} dropped the watch - next")
                continue
            await asyncio.sleep(0.3)
            rmask = [p for p in VALID if p not in NEVER | set(bus) | {6, 7, pin} | {11, 12}]
            c, r, dead = await safe(c, [0x1A, cs, clk, sio, d1, 0xFF, 0, *mask_of(rmask), 1], 15)
            if not dead and r and r[0] == 0x9A and r[1] > 0:
                h = r[2:9]
                hit = {"rst": None if h[0] == 0xFF else h[0], "proto": h[1], "line": "d1" if h[2] else "sio", "id": h[3:7].hex()}
                log(f"SCREEN ANSWERED: power {pn(pin)} {word}, reset={pn(hit['rst']) if hit['rst'] is not None else '-'} "
                    f"{PROTO[hit['proto']]} id={hit['id']}")
                save_hw(screen={"bus": bus, "pwr": [pin], "pwr_level": lvl, **hit})
                cands = [p for p in rmask if p != hit["rst"]]
                ok = await light_it(c, bus, hit, pin, lvl, cands)
                log("SCREEN WORKS" if ok else "screen talks; picture not confirmed - send this log")
                return
            if dead:
                continue
            c, hi = await pullups(c, NEVER | BUSP | {pin})
            new = sorted(set(hi or []) - set(base or []))
            if new:
                log(f"  {pn(pin)} {word}: new pull-ups on {[pn(p) for p in new]} (something powered up)")
                save_hw(**{f"rail_{pin}_{lvl}": new})
            await safe(c, [0x0A, pin])
    log("No power pin + reset combination made the screen answer. Send this log to Claude.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
