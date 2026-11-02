"""Is P2_5 the panel's high-voltage supply?  Needs firmware v11.
   bash run.sh display_p25      (Ctrl+C to stop)
Panel up + all pixels on, then P2_5 pulses from 1 ms to 1 s, then many short pulses (charges the rail gently) and hold.
Any flash of light = P2_5 feeds the panel. The longest pulse that survives shows how big the surge is.
"""
import asyncio, time
from display_steps import uptime, hold_alive, came_back, COME_BACK_S
from display_lit import panel_up, bright, ALL_ON, te
from display_v11 import step, Dropped
from tool5 import connect, cmd, ask, log, beep, save_hw, alive, WatchGone

P2_5 = 21
PULSES = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]


async def pulse(c, ms):
    r = await cmd(c, [0x08, P2_5, 1, ms & 0xFF, ms >> 8], 4)
    return r is not None and await alive(c)


async def ready(c):
    await panel_up(c)
    await step(c, "brightness 38%", bright(0x60))
    await step(c, "all pixels on", ALL_ON)


async def back(c):
    try:
        await c.disconnect()
    except Exception:
        pass
    by_itself = await came_back(COME_BACK_S)
    c = await connect()
    up, why = await uptime(c)
    log(f"came back by itself: {by_itself} | uptime {up} s, last reset: {why}")
    return c, up


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 11:
        raise SystemExit("flash v11 first: bash run.sh ota_flash --go firmware/v11/app_MP.bin")
    res = {}
    survived = 0
    log("=== WATCH THE SCREEN from now on. Any flash counts.")
    beep("found")
    try:
        await ready(c)
        for ms in PULSES:
            log(f">>> P2_5 pulse {ms} ms")
            if not await pulse(c, ms):
                raise Dropped(f"pulse {ms} ms")
            survived = ms
            log(f"   survived | TE in 0.5 s: {await te(c)}")
            await asyncio.sleep(0.3)
    except (Dropped, WatchGone) as e:
        log(f"!!! DROPPED AT: {e}")
        res["died_at"] = str(e)
        c, res["uptime"] = await back(c)
    res["longest_ok_ms"] = survived
    log(f"longest pulse that survived: {survived} ms")

    short = max(1, survived // 4)
    log(f"=== gentle charge: 60 pulses of {short} ms, then hold P2_5 on. WATCH THE SCREEN.")
    beep("found")
    try:
        await ready(c)
        for i in range(60):
            if not await pulse(c, short):
                raise Dropped(f"charge pulse {i + 1}/60")
        log(">>> holding P2_5 ON")
        await step(c, "P2_5 hold", [0x03, P2_5, 1], hold=6.0)
        log(f"   P2_5 HELD ON and the watch survived | TE in 0.5 s: {await te(c)}")
        res["held"] = True
    except (Dropped, WatchGone) as e:
        log(f"!!! DROPPED AT: {e}")
        res["held"] = False
        res["charge_died_at"] = str(e)
        c, res["charge_uptime"] = await back(c)
    beep("found")
    a = ""
    for _ in range(3):
        a = ask("Did you see ANY flash or light at any point? (flash / glow / nothing):")
        if a:
            break
    save_hw(display_p25={"results": res, "seen": a})
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
