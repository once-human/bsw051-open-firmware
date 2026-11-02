"""Screen ON using the ORIGINAL firmware's exact power-up + init sequence (decoded from the watch's own memory).
   bash run.sh display_stock      (Ctrl+C to stop)

Source (stock firmware, recovered): power/reset routine 0x8602CC, init routine 0x83BBF4 (22 commands,
16-bit register addresses, frame 02 00 HI LO data..., panel driver = FT2308-style AMOLED, likely).
Each variant paints its own colour; you answer once at the end.
"""
import asyncio
from tool5 import connect, cmd, ask, log, pn, save_hw, WatchGone, alive, watch_back

CS, CLK, D0 = 35, 32, 34
W, H = 368, 448

INIT = [  # (hi, lo, data)  - exactly as the stock firmware sends them
    (0xFF, 0x00, [0x23, 0x08, 0x01]),
    (0xFF, 0x80, [0x23, 0x08]),
    (0xC0, 0x83, [0xA4]),
    (0xC0, 0x89, [0xA4]),
    (0xC0, 0x93, [0xA4]),
    (0xC0, 0x99, [0xA4]),
    (0xB2, 0x83, [0x12]),
    (0x3A, 0x00, [0x55]),
    (0x51, 0x00, [0x00, 0x00]),
    (0x35, 0x00, [0x00]),
    (0xC0, 0xC4, [0x80]),
    (0xC3, 0x80, [0xF1, 0xF2, 0xF2, 0xF2, 0, 0, 0, 0, 0, 0, 0, 0, 0x12, 0, 0, 0]),
    (0xC3, 0x90, [0xEE, 0xFF, 0xEE, 0xEE, 0, 0, 0, 0, 0, 0, 0xFF, 0xFF, 0xEE, 0, 0, 0]),
    (0xC3, 0xA0, [0xEF, 0x55, 0xAA, 0xAA, 0x20, 0, 0, 0, 0, 0, 0x10, 0x10, 0xEF, 0, 0, 0]),
    (0xC5, 0xDF, [0x00]),
    (0x11, 0x00, [0x00]),          # sleep out  (+120 ms)
    (0x29, 0x00, [0x00]),          # display on
    (0xFF, 0x00, [0x23, 0x08, 0x01, 0x01]),
    (0xC5, 0xE2, [0xAF]),
    (0xC5, 0xE5, [0x3B]),
    (0xC4, 0x82, [0x52]),
    (0xC4, 0x89, [0x81]),
]

VARIANTS = [  # (colour name, rgb565, extra pins held HIGH besides P0_1)
    ("RED", 0xF800, [3]),                  # P0_1 + P0_3
    ("GREEN", 0x07E0, [3, 23, 19]),        # + P2_7 + P2_3
    ("BLUE", 0x001F, [3, 23, 19, 9]),      # + P1_1
    ("WHITE", 0xFFFF, []),                 # P0_1 only
]


async def frame(c, hi, lo, data):
    f = [0x02, 0x00, hi, lo, *data]
    await cmd(c, [0x16, CS, CLK, D0, 0xFF, 0, 0, len(f), *f, 0])


async def run_variant(c, colour, extra):
    await cmd(c, [0x1B, 1, 1, 10])                    # P0_1 screen power (soft start)
    for p in extra:
        await cmd(c, [0x1B, p, 1, 5])
    await cmd(c, [0x03, 16, 1]); await asyncio.sleep(0.05)   # stock: P2_0 HIGH, 50 ms
    await cmd(c, [0x03, 16, 0]); await asyncio.sleep(0.12)   # P2_0 LOW 120 ms (reset)
    await cmd(c, [0x03, 16, 1]); await asyncio.sleep(0.05)   # P2_0 HIGH, 50 ms
    for hi, lo, data in INIT:
        await frame(c, hi, lo, data)
        if hi == 0x11:
            await asyncio.sleep(0.12)
    await frame(c, 0x51, 0x00, [0xFF, 0xFF])          # brightness up (stock init leaves it at 0)
    await frame(c, 0x2A, 0x00, [0, 0, (W - 1) >> 8, (W - 1) & 0xFF])
    await frame(c, 0x2B, 0x00, [0, 0, (H - 1) >> 8, (H - 1) & 0xFF])
    await cmd(c, [0x17, CS, CLK, D0, 0, 0, 4, 0x02, 0x00, 0x2C, 0x00, colour >> 8, colour & 0xFF,
                  *(W * 160).to_bytes(4, "little")], 15)


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 9:
        raise SystemExit("flash v9 first: bash run.sh ota_flash --go firmware/v9/app_MP.bin")
    ask("Look at the WATCH SCREEN for ~30 s and remember every COLOUR you see. Press Enter.")
    for name, col, extra in VARIANTS:
        try:
            log(f"{name:6s}: power P0_1 {' '.join(pn(p) for p in extra)} + stock reset + stock init + paint")
            await run_variant(c, col, extra)
            await asyncio.sleep(2.0)
        except WatchGone:
            pass
        if not await alive(c):
            log(f"   watch dropped during {name} - reconnecting")
            c = await watch_back(c)
    a = ask("Which colour(s) did you see? (red / green / blue / white / none):")
    save_hw(display_stock={"seen": a})
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
