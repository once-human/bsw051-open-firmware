"""Does the panel draw real power at full brightness, now the motor is parked?  Needs firmware v11.
   bash run.sh display_max      (Ctrl+C to stop)
Panel up + all pixels on, brightness 38 -> 63 -> 100%. A reboot at high brightness = the panel's lighting supply is really on.
"""
import asyncio
from display_lit import panel_up, bright, ALL_ON, te, regs, look, back
from display_v11 import step, Dropped
from tool5 import connect, cmd, ask, log, beep, save_hw


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 11:
        raise SystemExit("flash v11 first: bash run.sh ota_flash --go firmware/v11/app_MP.bin")
    res = {}
    log("=== Panel starting. Watch the screen; each beep is a new test.")
    try:
        await panel_up(c)
        await step(c, "brightness 38%", bright(0x60))
        await step(c, "all pixels on", ALL_ON)
        await look(c, "white, 38%", bright(0x60))
        await look(c, "white, 63%", bright(0xA0))
        await look(c, "white, 100%", bright(0xFF), 6.0)
        res["regs"] = await regs(c)
        res["te"] = await te(c)
        log("registers:", res["regs"], "| TE in 0.5 s:", res["te"])
        res["survived_max"] = True
    except Dropped as e:
        res["survived_max"] = False
        c = await back(c, res, "base", e)
    beep("found")
    a = ""
    for _ in range(3):
        a = ask("Which TEST number first showed ANY light? Type the number, or 'nothing' (1-3):")
        if a:
            break
    save_hw(display_max={"results": res, "seen": a})
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
