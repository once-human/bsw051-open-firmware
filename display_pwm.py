"""P2_5 (suspected OLED high-voltage supply) fed in small doses by hardware PWM, panel already white.  Needs firmware v13.
   bash run.sh display_pwm      (Ctrl+C to stop)
Charger-only power can't take P2_5 switched hard on (every hard switch-on rebooted the watch). Here P2_5 is only on for a
small slice of each period, raised step by step, so its capacitors fill gradually. Panel is white the whole time:
if the high-voltage side works at all, a dim glow should appear before the watch drops. Watch the screen; answer at the end.
"""
import asyncio
from display_lit import panel_up, bright, ALL_ON, back
from display_v11 import step, Dropped
from tool5 import connect, cmd, ask, log, beep, save_hw

P2_5 = 21
# (period us, list of on-times in us); last entry of each = held fully on
LADDERS = [
    (250, [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 240, 250]),
    (25, [0.5, 1, 2, 3, 4, 5, 7.5, 10, 12.5, 15, 20, 24, 25]),
]
HOLD = 3.0


def pwm(period, high_us):
    h = int(round(high_us * 10))
    return [0x25, P2_5, period & 0xFF, period >> 8, h & 0xFF, h >> 8]


async def white(c):
    await panel_up(c)
    await step(c, "brightness 25%", bright(0x40))
    await step(c, "all pixels on (white)", ALL_ON, hold=1.0)


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 13:
        raise SystemExit("flash v13 first: bash run.sh ota_flash --go firmware/v13/app_MP.bin")
    res = {}
    log("=== Panel goes white (no light expected yet), then P2_5 is fed in rising doses. WATCH THE SCREEN.")
    beep("found")
    for period, ladder in LADDERS:
      for attempt in (1, 2, 3):           # charger-only power sometimes drops the watch during panel setup: retry
        key = f"{period}us#{attempt}"
        res[key] = {"ok_up_to": None}
        reached_p25 = False
        try:
            await white(c)
            for hi in ladder:
                reached_p25 = True
                pct = 100 * hi / period
                name = f"P2_5 on {hi} us of every {period} us ({pct:.0f}%)" if hi < period else "P2_5 held fully ON"
                await step(c, name, pwm(period, hi))
                await step(c, "  display off", [0x1E, 0x28, 0x00, 0])
                await step(c, "  display on", [0x1E, 0x29, 0x00, 0], hold=HOLD)
                res[key]["ok_up_to"] = hi
            log(f"*** {key}: SURVIVED every step including fully on")
            await step(c, "P2_5 off", pwm(period, 0))
        except Dropped as e:
            ok = res[key]["ok_up_to"]
            c = await back(c, res, key, e)
            res[key]["ok_up_to"] = ok
            res[key]["reached_p25"] = reached_p25
        log(f"{key}: last P2_5 step that survived = {res[key]['ok_up_to']} us")
        if reached_p25:
            break
        log("   died before P2_5 was even touched (panel setup) -> trying again")
    beep("found")
    a = ""
    for _ in range(3):
        a = ask("Did you see ANY light on the screen, even very faint? (yes / no):")
        if a:
            break
    save_hw(display_pwm={"results": res, "seen": a})
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
