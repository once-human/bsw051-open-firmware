"""Screen hunt on the wiring this chip's screen hardware uses (CS P4_3, CLK P4_0, DATA P4_2).
For every possible RESET pin: reset -> ask the screen its ID -> wake it -> paint white.
WATCH THE SCREEN the whole time. If it flickers/lights at any step, note the # number.
   bash run.sh screen        (Ctrl+C to stop)"""
import asyncio, time
from tool5 import connect, cmd, ask, log, pn, load_hw, save_hw, WatchGone, VALID, alive, watch_back, NOT_DISPLAY

CS, CLK, SIO = 35, 32, 34
BUS = {CS, CLK, SIO, 33, 6, 7}          # bus pins + motor (P0_7) + its neighbour

def spi(data, flags=0, nr=0):
    return [0x16, CS, CLK, SIO, SIO if nr else 0xFF, 0, flags, len(data), *data, nr]

def edges(b):
    if not b:
        return 0
    v = int.from_bytes(b, "big"); n = len(b) * 8
    return bin((v ^ (v >> 1)) & ((1 << (n - 1)) - 1)).count("1")

async def read_ids(c):
    out = {}
    for name, frame, fl in (("qspi 04", [0x03, 0x00, 0x04, 0x00], 0), ("qspi DA", [0x03, 0x00, 0xDA, 0x00], 0),
                            ("spi 04", [0x04], 0), ("9bit 04", [0x04], 1), ("spi 0A", [0x0A], 0)):
        r = await cmd(c, spi(frame, fl, 4))
        if r and r[0] == 0x96:
            b = bytes(r[2:2 + r[1]])
            out[name] = b.hex() + (" <-- REAL?" if edges(b) >= 3 else "")
    return out

async def wake_and_paint(c):
    q = lambda *a: [0x02, 0x00, a[0], 0x00, *a[1:]]
    for f in (q(0x11),):
        await cmd(c, spi(f))
    await asyncio.sleep(0.12)
    for f in (q(0x3A, 0x55), q(0x51, 0xFF), q(0x29), q(0x23)):
        await cmd(c, spi(f))
    await cmd(c, [0x17, CS, CLK, SIO, 0, 0, 4, 0x02, 0x00, 0x2C, 0x00, 0xFF, 0xFF, *(368 * 60).to_bytes(4, "little")], 10)
    # 3-wire 9-bit LCD style
    await cmd(c, spi([0x11], 1)); await asyncio.sleep(0.12)
    await cmd(c, spi([0x29], 1))
    await cmd(c, [0x17, CS, CLK, SIO, 0, 1, 1, 0x2C, 0xFF, 0xFF, *(368 * 60).to_bytes(4, "little")], 10)

async def main():
    c = await connect()
    hw = load_hw()
    danger = set(hw.get("danger", []))
    rsts = [None] + [p for p in VALID if p not in BUS and p not in danger and p not in NOT_DISPLAY]
    ask(f"Look at the WATCH SCREEN. Press Enter to start ({len(rsts)} steps, ~2 s each)")
    hits = []
    try:
        for i, rst in enumerate(rsts, 1):
            name = pn(rst) if rst is not None else "none"
            if rst is not None:
                await cmd(c, [0x03, rst, 0]); await asyncio.sleep(0.02)
                await cmd(c, [0x03, rst, 1]); await asyncio.sleep(0.15)
            ids = await read_ids(c)
            real = {k: v for k, v in ids.items() if "REAL" in v}
            log(f"#{i:2d} reset={name:5s} ids={ids}")
            if real:
                hits.append({"rst": rst, "ids": real})
            await wake_and_paint(c)
            if not await alive(c):
                log(f"   watch dropped at #{i} ({name}) - waiting for it")
                c = await watch_back(c)
                continue
            if rst is not None:
                await cmd(c, [0x0A, rst])
        a = ask("Did the screen flicker / light up / show anything at ANY step? Type the # number (or Enter for no):")
        save_hw(screen_scan={"hits": hits, "user_saw": a})
        log("RESULT:", "screen reacted at #" + a if a else "no visible reaction", "| ID answers:", hits or "none")
    except WatchGone:
        log("watch disconnected - paste this log to Claude")
    finally:
        try:
            await cmd(c, [0x0B], 2); await c.disconnect()
        except Exception:
            pass

asyncio.run(main())
