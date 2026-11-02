"""Real pictures on the screen: P2_5 soft-started by PWM (what first lit the screen, 22:09), then colour fills.  Needs firmware v13.
   bash run.sh display_show      (Ctrl+C to stop)
Watch the screen. Numbered pictures, one beep each:
  1 whole screen RED   2 GREEN   3 BLUE   4 black with a white square in the middle   5 four coloured quarters
Answer at the end with what you saw.
"""
import asyncio
from display_lit import panel_up, bright, back
from display_v11 import step, fill, Dropped
from tool5 import connect, cmd, ask, log, beep, save_hw

P2_5 = 21
W, H = 368, 448
RAMP = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 240, 250]   # us of every 250 us; 250 = held on


def pwm(high_us, period=250):
    h = int(round(high_us * 10))
    return [0x25, P2_5, period & 0xFF, period >> 8, h & 0xFF, h >> 8]


async def light_up(c):
    await panel_up(c)
    await step(c, "brightness 38%", bright(0x60))
    await step(c, "black screen first", fill(0, W - 1, 0, H - 1, 0x0000), 30)
    log("soft-starting P2_5 (the screen's high-voltage supply)...")
    # exactly the 250 us ladder that lit the screen at 22:08 (light from ~60%), display off/on at every step, 1 s per step.
    # The 25 us ladder gave NO light even fully on (power chip latched off by fast pulses? unproven) - don't use it.
    for hi in RAMP:
        await step(c, f"   P2_5 {100 * hi // 250}%", pwm(hi))
        await step(c, "      display off", [0x1E, 0x28, 0x00, 0])
        await step(c, "      display on", [0x1E, 0x29, 0x00, 0], hold=1.0)


async def picture(c, n, name, cmds, hold=4.0):
    log(f">>> PICTURE {n}: {name} - LOOK AT THE SCREEN")
    beep("found")
    for b in cmds[:-1]:
        await step(c, f"   {name} (part)", b, 30)
    await step(c, f"   {name}", cmds[-1], 30, hold)


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 13:
        raise SystemExit("flash v13 first: bash run.sh ota_flash --go firmware/v13/app_MP.bin")
    res = {"done": 0}
    log("=== Screen comes up, then 5 pictures. WATCH THE SCREEN.")
    for attempt in (1, 2, 3):
        try:
            await light_up(c)
            await picture(c, 1, "whole screen RED", [fill(0, W - 1, 0, H - 1, 0xF800)])
            res["done"] = 1
            await picture(c, 2, "whole screen GREEN", [fill(0, W - 1, 0, H - 1, 0x07E0)])
            res["done"] = 2
            await picture(c, 3, "whole screen BLUE", [fill(0, W - 1, 0, H - 1, 0x001F)])
            res["done"] = 3
            await picture(c, 4, "black + white square in the middle",
                          [fill(0, W - 1, 0, H - 1, 0x0000), fill(134, 233, 174, 273, 0xFFFF)])
            res["done"] = 4
            hw, hh = W // 2, H // 2
            await picture(c, 5, "four quarters: red top-left, green top-right, blue bottom-left, white bottom-right",
                          [fill(0, hw - 1, 0, hh - 1, 0xF800), fill(hw, W - 1, 0, hh - 1, 0x07E0),
                           fill(0, hw - 1, hh, H - 1, 0x001F), fill(hw, W - 1, hh, H - 1, 0xFFFF)], 6.0)
            res["done"] = 5
            break
        except Dropped as e:
            done = res["done"]
            c = await back(c, res, f"attempt{attempt}", e)
            res["done"] = done
            log(f"pictures shown before the drop: {done} -> trying again")
    beep("found")
    a = ""
    for _ in range(3):
        a = ask("What did you see? Type the picture numbers you saw correctly (e.g. 1 2 3 4 5), or 'only white', or 'nothing':")
        if a:
            break
    save_hw(display_show={"results": res, "seen": a})
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
