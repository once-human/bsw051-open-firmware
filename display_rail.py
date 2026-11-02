"""Last P2_5 test: the exact stock rail cycle (H_1/H_2 included), then panel + white at full brightness.  Needs firmware v12.
   bash run.sh display_rail      (Ctrl+C to stop)
"""
import asyncio
from display_lit import panel_up, bright, ALL_ON, te, regs, look, back
from display_v11 import step, Dropped
from tool5 import connect, cmd, ask, log, beep, save_hw


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 12:
        raise SystemExit("flash v12 first: bash run.sh ota_flash --go firmware/v12/app_MP.bin")
    res = {}
    log("=== Stock rail cycle. Watch the screen.")
    beep("found")
    await asyncio.sleep(3)
    try:
        await step(c, "exact stock rail cycle (P2_5 on)", [0x24], 6, 2.0)
        log("P2_5 IS ON AND THE WATCH SURVIVED")
        res["rail_survived"] = True
        await panel_up(c)
        await step(c, "brightness 38%", bright(0x60))
        await look(c, "white, 38%", ALL_ON)
        await look(c, "white, 100%", bright(0xFF), 6.0)
        res["regs"] = await regs(c)
        res["te"] = await te(c)
        log("registers:", res["regs"], "| TE in 0.5 s:", res["te"])
    except Dropped as e:
        res.setdefault("rail_survived", False)
        c = await back(c, res, "base", e)
    beep("found")
    a = ""
    for _ in range(3):
        a = ask("Did you see ANY light on the screen? (yes / no):")
        if a:
            break
    save_hw(display_rail={"results": res, "seen": a})
    log("RESULT:", res, "| you saw:", a or "(no answer)")
    try:
        await cmd(c, [0x0B], 2)
        await c.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
