"""Where exactly does ONKAR OS die while powering the screen, and why?   bash run.sh os_diag [ramp_ms]   (Ctrl+C to stop)
Starts the screen (ramp step = ramp_ms, default 100 = the watch's normal), logs every ramp step until RUNNING or the watch
drops, then puts the ramp setting back to normal.
After a drop: reconnects and reads the chip's reset reason (power-on = power dip, WATCHDOG = software hang).  Two attempts.
"""
import asyncio, sys
from tool5 import connect, cmd, log, beep, status, WatchGone

RAMP = [10, 20, 50, 100, 130, 160, 180, 200, 215, 230, 245, 260, 280, 300, 330, 370, 420, 500,
        600, 750, 1000, 1250, 1500, 2000, 2400, 2500]   # onkar_os.inc v18, 0.1 us of 250 us
STEP10 = max(5, int(sys.argv[1]) // 10) if len(sys.argv) > 1 else 10
STATES = ["off", "waiting for boot delay", "powering up", "RUNNING", "sleeping", "updating"]


def duty(i):
    """ramp_i = number of steps already applied"""
    return "P2_5 off" if i == 0 else f"P2_5 {RAMP[min(i, len(RAMP)) - 1] / 25:.1f}%"


async def attempt(c, n):
    log(f"=== attempt {n}: screen start, ramp step >= {STEP10 * 10} ms")
    r = await cmd(c, [0x32, 3, STEP10])
    r = await cmd(c, [0x30, 1], 6)
    last = None
    t = asyncio.get_event_loop().time()
    try:
        while asyncio.get_event_loop().time() - t < 60:
            r = await cmd(c, [0x30, 2], 3)
            if r and r[0] == 0xB0 and len(r) >= 80:
                st, ri = r[1], r[30]
                cur = (st, ri)
                if cur != last:
                    log(f"   {STATES[st] if st < len(STATES) else st} | step {ri}/{len(RAMP)} | {duty(ri)} | boot failures {r[2]}")
                    last = cur
                if st == 3:
                    log("REACHED RUNNING")
                    return c, {"ok": True}
            await asyncio.sleep(0.25)
        return c, {"ok": False, "why": "timeout", "last": last}
    except WatchGone:
        log(f"!!! WATCH DROPPED. last seen: {STATES[last[0]] if last else '?'}, {duty(last[1]) if last else '?'}")
        beep("lost")
        await asyncio.sleep(3)
        c = await connect()
        await status(c)
        return c, {"ok": False, "why": "dropped", "last": last}


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 18:
        raise SystemExit("needs v18")
    await status(c)
    res = []
    for n in (1, 2):
        c, x = await attempt(c, n)
        res.append(x)
        if x["ok"]:
            break
    await cmd(c, [0x32, 3, 10])
    log("RESULT:", res)
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
