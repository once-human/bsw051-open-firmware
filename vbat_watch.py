"""Supply voltage (chip VBAT) while ONKAR OS starts the screen.   bash run.sh vbat_watch [seconds]   (Ctrl+C to stop)
Polls VBAT (0x02) + OS state (0x30 02) as fast as Bluetooth allows, logs every reading during a screen start, reconnects
after a drop. Shows whether the charger-only supply sags before the chip dies.
"""
import asyncio, sys, time
from tool5 import connect, cmd, log, beep, WatchGone

STATES = ["off", "wait", "ramp", "RUN", "sleep", "dfu"]
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 120


async def main():
    t_end = time.time() + DUR
    c = await connect()
    lo = 99999
    while time.time() < t_end:
        try:
            r = await cmd(c, [0x02], 2)
            s = await cmd(c, [0x30, 2], 2)
            mv = (r[3] | r[4] << 8) if r and r[0] == 0x82 and len(r) >= 5 else None
            st = STATES[s[1]] if s and s[0] == 0xB0 and s[1] < len(STATES) else "?"
            ri = s[30] if s and len(s) > 30 else -1
            if mv:
                lo = min(lo, mv)
            log(f"VBAT {mv} mV | {st} step {ri} | fails {s[2] if s else '?'} | lowest {lo}")
        except WatchGone:
            log("!!! dropped")
            await asyncio.sleep(2)
            c = await connect()
            lo = 99999
    beep("found")
    try:
        await c.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
