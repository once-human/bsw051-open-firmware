"""Pad map: find which chip pin each labelled pad on the board goes to.  ~3 min, no soldering.
   bash run.sh padmap        (Ctrl+C to stop)

You need: one small piece of wire, a paperclip or metal tweezers.
The watch reads all its pins nonstop. You touch the TX pad (it sits at 3.3 V) to a labelled pad;
the pin that flips to 1 IS that pad. The script tells you which pad to touch next and beeps when it sees it.
"""
import asyncio, time
from tool5 import connect, cmd, ask, log, pn, load_hw, save_hw, WatchGone, VALID, alive, watch_back, beep

PADS = ["LCD_RST", "CS", "CLK", "SIO0", "LEDK", "T_RST", "T_INT", "T_SCL", "T_SDA", "SCL", "SDA", "PG", "KEY"]
SKIP = {11, 12, 3}          # the 2 critical pins + P0_3 (that's the TX pad itself, our 3.3 V source)


async def sweep(c, pins):
    hi = set()
    for p in pins:
        try:
            r = await cmd(c, [0x04, p, 2], 3)
        except WatchGone:
            return None
        if r and r[0] == 0x84 and r[2] == 1:
            hi.add(p)
    return hi


async def main():
    c = await connect()
    pins = [p for p in VALID if p not in SKIP]
    log("reading the baseline (don't touch anything)...")
    base = set()
    for _ in range(2):
        s = await sweep(c, pins)
        base |= s or set()
    log("pins already high on their own (can't be detected, skipped):", [pn(p) for p in sorted(base)] or "none")
    watch = [p for p in pins if p not in base]
    found = {}
    src = "TX"
    for pad in PADS:
        a = ask(f"Touch the {src} pad to the {pad} pad and HOLD it. Press Enter while holding (or type s to skip this pad):")
        if a.startswith("s"):
            continue
        hit, t0, seen = None, time.time(), {}
        while time.time() - t0 < 15:
            s = await sweep(c, watch)
            if s is None:
                if not await alive(c):
                    c = await watch_back(c)
                continue
            for p in s:
                seen[p] = seen.get(p, 0) + 1
                if seen[p] >= 2:
                    hit = p
            if hit is not None:
                break
        if hit is not None:
            beep("found")
            found[pad] = hit
            log(f"{pad} = {pn(hit)}")
            save_hw(padmap=found)
        else:
            log(f"{pad}: no pin reacted in 15 s")
            if pad == PADS[0] and src == "TX":
                src = "TXD"
                log("maybe TX isn't the 3.3 V one - next pads use TXD instead (if that fails too, try RX)")
        ask("Release. Press Enter.")
    log("PAD MAP:", {k: pn(v) for k, v in found.items()} or "nothing found")
    try:
        await cmd(c, [0x0B], 2); await c.disconnect()
    except Exception:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
