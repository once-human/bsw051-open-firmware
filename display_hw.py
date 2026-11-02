"""Screen ON through the chip's own screen hardware (SPIC2), exactly like the stock firmware.  Needs firmware v10.
   bash run.sh display_hw        (Ctrl+C to stop)
Per variant: stock power + reset, stock 22-command init, brightness max, then:
  ALL PIXELS ON (white, 2 s) -> paint the top of the screen in the variant's colour.
"""
import asyncio
from display_stock import INIT
from tool5 import connect, cmd, ask, log, pn, save_hw, WatchGone, alive, watch_back

W, H = 368, 448
VARIANTS = [("RED", 0xF800, []), ("BLUE", 0x001F, [3])]     # P0_1 only, then P0_1 + P0_3


async def hw(c, hi, lo, data=()):
    data = list(data)
    return await cmd(c, [0x1E, hi, lo, len(data), *data])


async def run(c, col, extra):
    r = await cmd(c, [0x1D])                                   # SPIC2 + pins, stock-identical
    await cmd(c, [0x1B, 1, 1, 10])                             # P0_1 screen power
    for p in extra:
        await cmd(c, [0x1B, p, 1, 5])
    await cmd(c, [0x03, 16, 1]); await asyncio.sleep(0.05)    # P2_0 reset sequence (stock timing)
    await cmd(c, [0x03, 16, 0]); await asyncio.sleep(0.12)
    await cmd(c, [0x03, 16, 1]); await asyncio.sleep(0.05)
    for hi, lo, data in INIT:
        await hw(c, hi, lo, data)
        if hi == 0x11:
            await asyncio.sleep(0.12)
    await hw(c, 0x51, 0x00, [0xFF, 0xFF])                    # brightness max
    await hw(c, 0x23, 0x00)                                   # all pixels ON (white)
    await asyncio.sleep(2.0)
    await hw(c, 0x22, 0x00)                                   # all pixels off -> show RAM
    await hw(c, 0x13, 0x00)                                   # normal display mode
    await hw(c, 0x2A, 0x00, [0, 0, (W - 1) >> 8, (W - 1) & 0xFF])
    await hw(c, 0x2B, 0x00, [0, 0, (H - 1) >> 8, (H - 1) & 0xFF])
    await cmd(c, [0x1F, col >> 8, col & 0xFF, *(W * 120).to_bytes(4, "little")], 30)
    return r


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 10:
        raise SystemExit("flash v10 first: bash run.sh ota_flash --go firmware/v10/app_MP.bin")
    ask("Look at the WATCH SCREEN for ~30 s (white flash, then a colour). Press Enter.")
    for name, col, extra in VARIANTS:
        try:
            log(f"{name}: power P0_1 {' '.join(pn(p) for p in extra)} -> stock init via screen hardware -> WHITE 2 s -> {name}")
            await run(c, col, extra)
            await asyncio.sleep(2.0)
        except WatchGone:
            pass
        if not await alive(c):
            log(f"   watch dropped during {name} - reconnecting")
            c = await watch_back(c)
    a = ask("What did you see? (white / red / blue / flicker / noise / none):")
    save_hw(display_hw={"seen": a})
    log("RESULT:", a or "none")
    try:
        await cmd(c, [0x0B], 2); await c.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
