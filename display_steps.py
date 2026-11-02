"""Which step kills the watch?  Needs firmware v10.
   bash run.sh display_steps      (Ctrl+C to stop)
Same screen sequence as display_hw, but the watch is checked after EVERY step and nothing waits for Enter
until the end. Starts at low brightness. After a drop: DON'T touch the charger or battery for 40 s - uptime then tells a real reboot from a lost link.
Tries twice, then asks what you saw.
"""
import asyncio, time
from bleak import BleakScanner
from display_stock import INIT
from tool5 import connect, cmd, ask, log, beep, save_hw, WatchGone, alive, ADDR, RESET

W, H = 368, 448
COME_BACK_S = 40


async def uptime(c):
    r = await cmd(c, [0x10])
    if not r or r[0] != 0x90:
        return None, None
    return int.from_bytes(r[2:6], "little"), RESET.get(r[6], hex(r[6]))


async def came_back(seconds):
    t0 = time.time()
    while time.time() - t0 < seconds:
        try:
            found = await BleakScanner.discover(timeout=4, return_adv=True)
        except Exception:
            await asyncio.sleep(2)
            continue
        if any((adv.local_name or "").startswith("ONKAR") or a.upper() == ADDR for a, (d, adv) in found.items()):
            return True
    return False


def steps():
    yield "SPIC2 hardware setup (0x1D)", [0x1D], 0
    yield "screen power P0_1 on", [0x1B, 1, 1, 10], 0.5
    yield "reset P2_0 high", [0x03, 16, 1], 0.05
    yield "reset P2_0 low", [0x03, 16, 0], 0.12
    yield "reset P2_0 high", [0x03, 16, 1], 0.05
    for i, (hi, lo, data) in enumerate(INIT):
        yield f"init {i + 1}/{len(INIT)} reg {hi:02X}{lo:02X}", [0x1E, hi, lo, len(data), *data], 0.12 if hi == 0x11 else 0
    yield "brightness 6%", bright(0x10), 1.0                   # low current first: full white at max browned out
    yield "ALL PIXELS ON (white) at 6% - look now", [0x1E, 0x23, 0x00, 0], 3.0
    yield "white at 19%", bright(0x30), 3.0
    yield "white at 38%", bright(0x60), 3.0
    yield "all pixels off", [0x1E, 0x22, 0x00, 0], 0
    yield "normal mode", [0x1E, 0x13, 0x00, 0], 0
    yield "full screen range (x)", window(0x2A, 0, W - 1), 0
    yield "full screen range (y)", window(0x2B, 0, H - 1), 0
    yield "paint everything black", fill(0x0000, W * H), 0
    yield "square range (x)", window(0x2A, 134, 233), 0
    yield "square range (y)", window(0x2B, 174, 273), 0
    yield "WHITE SQUARE in the middle at 38% - look now", fill(0xFFFF, 100 * 100), 3.0
    yield "white square at max brightness", bright(0xFF), 3.0


def bright(v):
    return [0x1E, 0x51, 0x00, 2, v, v]


def window(reg, a, b):
    return [0x1E, reg, 0x00, 4, a >> 8, a & 0xFF, b >> 8, b & 0xFF]


def fill(col, count):
    return [0x1F, col >> 8, col & 0xFF, *count.to_bytes(4, "little")]


async def hold_alive(c, seconds):
    """Keeps pinging during a hold, so a drop is timed to within ~0.5 s. Returns seconds held if it died, else None."""
    t0 = time.time()
    while time.time() - t0 < seconds:
        await asyncio.sleep(min(0.5, seconds))
        if not await alive(c):
            return time.time() - t0
    return None


async def ladder(c):
    """Returns the step that killed the watch, or None."""
    if not await alive(c):
        return "before any command (link already down)"
    for name, b, hold in steps():
        log(f"   {name}")
        try:
            r = await cmd(c, b, 30 if b[0] == 0x1F else 4.0)
            if r is None or (b[0] in (0x1E, 0x1F) and r[1] != 0):
                log(f"      reply: {r.hex() if r else 'none'}")
            died = await hold_alive(c, hold) if hold else (None if await alive(c) else 0.0)
            if died is not None:
                return f"{name} ({died:.1f} s after it was sent)"
        except WatchGone:
            return name
    return None


async def main():
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 10:
        raise SystemExit("flash v10 first: bash run.sh ota_flash --go firmware/v10/app_MP.bin")
    up, why = await uptime(c)
    log(f"start: uptime {up} s, last reset: {why}")
    log("WATCH THE SCREEN NOW. Starting in 5 s. If the watch drops, DON'T touch the charger or battery until it beeps twice.")
    beep("found")
    await asyncio.sleep(5)
    results = []
    for attempt in (1, 2):
        log(f"=== attempt {attempt} of 2")
        t0 = time.time()
        died = await ladder(c)
        if not died:
            log(f"attempt {attempt}: every step survived ({time.time() - t0:.0f} s)")
            results.append({"died_at": None})
            continue
        log(f"!!! DROPPED AT: {died} ({time.time() - t0:.1f} s in)")
        try:
            await c.disconnect()
        except Exception:
            pass
        log(f"hands off the charger - waiting up to {COME_BACK_S} s for the watch to return by itself")
        by_itself = await came_back(COME_BACK_S)
        log("came back by itself" if by_itself else "did NOT come back by itself -> replug the charger now")
        c = await connect()
        up, why = await uptime(c)
        rebooted = up is not None and up < time.time() - t0
        log(f"uptime {up} s, last reset: {why} ->", "the watch REBOOTED" if rebooted else "only the Bluetooth link dropped, NO reboot")
        results.append({"died_at": died, "by_itself": by_itself, "uptime": up, "reset": why, "rebooted": rebooted})
    beep("found")
    a = ""
    for _ in range(3):
        a = ask("What did you see on the screen? Type it, even if it's just 'nothing' (white / red / flicker / glow / nothing):")
        if a:
            break
    save_hw(display_steps={"results": results, "seen": a})
    log("RESULT:", results, "| you saw:", a or "(no answer)")
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
