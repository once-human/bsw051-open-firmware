"""Turn the screen on with the ORIGINAL firmware's own power-up sequence (found in the watch's memory).
   bash run.sh display_on        (Ctrl+C to stop)

Stock sequence (from the stock code at 0x8602CC): P0_1 HIGH (screen power) + P2_0 HIGH, wait 50 ms,
P2_0 LOW (reset) 120 ms, P2_0 HIGH, wait 50 ms.  Screen bus = chip's hardware screen pins (CS P4_3, CLK P4_0, DATA P4_2).
The stock code also drives P0_3, P2_7, P2_3, P1_1 HIGH somewhere - each variant below adds one more.
Every variant paints its OWN colour, so you only answer once at the end: which colour(s) you saw.
"""
import asyncio
from tool5 import connect, cmd, ask, log, pn, save_hw, WatchGone, alive, watch_back

CS, CLK, D0, D1 = 35, 32, 34, 33
W, H = 368, 448
VARIANTS = [  # (name, colour565, extra pins held HIGH on top of P0_1)
    ("RED", 0xF800, []),
    ("GREEN", 0x07E0, [3]),            # + P0_3
    ("BLUE", 0x001F, [3, 23]),         # + P2_7
    ("WHITE", 0xFFFF, [3, 23, 19]),    # + P2_3
    ("YELLOW", 0xFFE0, [3, 23, 19, 9]),  # + P1_1
    ("MAGENTA", 0xF81F, [23, 19, 9]),  # same but P0_3 LOW
]


def q(c_, *p):
    return [0x02, 0x00, c_, 0x00, *p]


async def spi(c, data, nr=0, miso=0xFF):
    return await cmd(c, [0x16, CS, CLK, D0, miso, 0, 0, len(data), *data, nr])


async def power_and_reset(c, extra, p03_low=False):
    await cmd(c, [0x1B, 1, 1, 10])                    # P0_1 HIGH, 100 ms soft ramp (screen power)
    for p in extra:
        await cmd(c, [0x1B, p, 1, 5])
    if p03_low:
        await cmd(c, [0x03, 3, 0])
    await cmd(c, [0x03, 16, 1]); await asyncio.sleep(0.05)   # P2_0 HIGH
    await cmd(c, [0x03, 16, 0]); await asyncio.sleep(0.12)   # P2_0 LOW  = reset
    await cmd(c, [0x03, 16, 1]); await asyncio.sleep(0.12)   # P2_0 HIGH, settle


async def read_id(c):
    out = {}
    for line, miso in (("D0", D0), ("D1", D1)):
        r = await spi(c, [0x03, 0x00, 0x04, 0x00], nr=4, miso=miso)
        if r and r[0] == 0x96:
            out[line] = bytes(r[2:2 + r[1]]).hex()
    return out


async def init_and_paint(c, colour):
    await spi(c, q(0x01)); await asyncio.sleep(0.12)          # soft reset
    await spi(c, q(0x11)); await asyncio.sleep(0.12)          # sleep out
    for f in (q(0xFE, 0x00), q(0x3A, 0x55), q(0x35, 0x00), q(0x53, 0x20), q(0x51, 0xFF),
              q(0x2A, 0, 0, (W - 1) >> 8, (W - 1) & 0xFF), q(0x2B, 0, 0, (H - 1) >> 8, (H - 1) & 0xFF), q(0x29)):
        await spi(c, f)
    await asyncio.sleep(0.02)
    await cmd(c, [0x17, CS, CLK, D0, 0, 0, 4, 0x02, 0x00, 0x2C, 0x00, colour >> 8, colour & 0xFF,
                  *(W * 140).to_bytes(4, "little")], 15)       # top third of the screen


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 9:
        raise SystemExit("flash v9 first: bash run.sh ota_flash --go firmware/v9/app_MP.bin")
    ask("Look at the WATCH SCREEN for the next ~30 s and remember every COLOUR you see. Press Enter.")
    seen_ids = {}
    for name, col, extra in VARIANTS:
        try:
            await power_and_reset(c, extra, p03_low=(name == "MAGENTA"))
            ids = await read_id(c)
            seen_ids[name] = ids
            log(f"{name:8s} pins HIGH: P0_1 {' '.join(pn(p) for p in extra)}  | screen ID read: {ids}")
            await init_and_paint(c, col)
            await asyncio.sleep(1.5)
        except WatchGone:
            pass
        if not await alive(c):
            log(f"   watch dropped during {name} - reconnecting")
            c = await watch_back(c)
    a = ask("Which colour(s) did you see on the screen? (e.g. red, green ... or none):")
    save_hw(display_on={"seen": a, "ids": seen_ids})
    log("RESULT: you saw:", a or "none")
    try:
        await cmd(c, [0x0B], 2); await c.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
