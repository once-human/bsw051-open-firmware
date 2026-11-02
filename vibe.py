"""Recreate EXACTLY the pin state that made the watch vibrate (v2 screen probe), then find the motor pin.
   bash run.sh vibe        (answer y/n, Ctrl+C to stop)"""
import asyncio
from tool5 import connect, cmd, ask, log, pn, WatchGone

V2_STATE = [  # what v2's lcd_bus_init did, in order
    ("SPI bus: CS=P4_3 high, CLK=P4_0 low, DATA=P4_2, READ=P4_1 floating", None),
    ("P0_6 HIGH", (6, 1)),
    ("P0_7 HIGH", (7, 1)),
]
ORDER = [6, 7, 35, 32, 34, 33]

async def v2_state(c):
    # 0x16 opens the bus exactly like v2 did (GPIO mode, CS high, CLK low, DATA out, READ in, no pull) + a read frame
    await cmd(c, [0x16, 35, 32, 34, 33, 0, 0, 4, 0x03, 0x00, 0x04, 0x00, 3])
    await cmd(c, [0x03, 6, 1])
    await cmd(c, [0x03, 7, 1])

async def main():
    c = await connect()
    try:
        await v2_state(c)
        if not ask("Is it VIBRATING now? (y/n)").startswith("y"):
            log("not vibrating with the v2 state. Trying all 6 pins HIGH together...")
            for p in ORDER:
                await cmd(c, [0x03, p, 1])
            if not ask("Vibrating NOW? (y/n)").startswith("y"):
                log("still no vibration. On charger-only power the motor may not get enough current. Releasing.")
                await cmd(c, [0x0B]); return
        log("Good. Now letting go of one pin at a time - tell me when it STOPS.")
        for p in ORDER:
            await cmd(c, [0x0A, p])
            if ask(f"Let go of {pn(p)}. Still vibrating? (y/n)").startswith("n"):
                log(f"MOTOR PIN = {pn(p)}  (it ran while {pn(p)} was held by us)")
                await cmd(c, [0x0B])
                ask(f"Confirm: press Enter, {pn(p)} goes HIGH for 1 s")
                await cmd(c, [0x08, p, 1, 0xE8, 0x03], 4)
                a = ask("Did it buzz? (y/n)")
                if not a.startswith("y"):
                    ask(f"Press Enter, {pn(p)} goes LOW for 1 s")
                    await cmd(c, [0x08, p, 0, 0xE8, 0x03], 4)
                    a = "LOW" if ask("Did it buzz? (y/n)").startswith("y") else "needs the other pins too"
                else:
                    a = "HIGH"
                log(f"RESULT: motor on {pn(p)}, on = {a}. Paste this to Claude.")
                return
        log("Released all six and it still vibrates?! Paste this to Claude.")
    except WatchGone:
        log("watch disconnected (the motor surge may have browned it out on charger-only power)")
    finally:
        try:
            await cmd(c, [0x0B], 2); await c.disconnect()
        except Exception:
            pass

asyncio.run(main())
