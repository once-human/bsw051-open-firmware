"""Control ONKAR OS (firmware v14+) from the laptop.  Every call also sets the watch clock to the laptop's local time.
   bash run.sh os_ctl                   status (default)
   bash run.sh os_ctl start | stop      start the screen now (also clears the boot-failure counter) / turn it off
   bash run.sh os_ctl watch             live status every second: touch bytes, button pins, crown (Ctrl+C to stop)
   bash run.sh os_ctl screen N          0 clock, 1 eyes, 2 paint, 3 info, 4 settings
   bash run.sh os_ctl set KEY VALUE     keys: autostart bright ramp touch_flags button screen touch_rst always_on stream te_sync
                                        e.g.  set stream 1   (other drawing method, if the picture still has stripes)
                                              set button P2_2 (or auto)
   bash run.sh os_ctl tap X Y | swipe left|right|up|down | press   fake input
   bash run.sh os_ctl i2c ADDR W1,W2.. N   raw read on the touch bus, e.g.  i2c 2E 20,00,00,2C 8
   bash run.sh os_ctl probe             search for the touch chip again
"""
import asyncio, sys, time
from tool5 import connect, cmd, log, pn

KEYS = {"autostart": 1, "bright": 2, "ramp": 3, "touch_flags": 4, "button": 5, "screen": 6, "touch_rst": 7,
        "always_on": 8, "stream": 9, "te_sync": 10}
STATES = ["off", "waiting for boot delay", "powering up", "RUNNING", "sleeping", "updating"]
SCREENS = ["clock", "eyes", "paint", "info", "settings"]
EV = {"tap": 1, "left": 2, "right": 3, "up": 4, "down": 5, "long": 6, "press": 7}
PINS = {f"P{p}_{i}": p * 8 + i for p in range(4) for i in range(8)}


def u16(r, i): return r[i] | r[i + 1] << 8
def u32(r, i): return int.from_bytes(bytes(r[i:i + 4]), "little")
def s32(r, i): return int.from_bytes(bytes(r[i:i + 4]), "little", signed=True)


def show(r):
    if not r or r[0] != 0xB0 or len(r) < 40:
        log("no/short status answer:", r and bytes(r).hex())
        return
    st = STATES[r[1]] if r[1] < len(STATES) else r[1]
    log(f"state: {st} | screen: {SCREENS[r[8]] if r[8] < 5 else r[8]} | brightness {r[9]} | boot failures {r[2]} | "
        f"start at boot {'on' if r[3] else 'off'} | drawing mode {r[31]} | frames {u32(r, 14)}")
    tch = f"0x{r[4]:02X} on SCL {pn(r[5])} SDA {pn(r[6])}" if r[4] else "not found"
    log(f"touch: {tch} | reads {u32(r, 18)} | gestures {u32(r, 22)} | last x,y {u16(r, 10)},{u16(r, 12)} | "
        f"raw {bytes(r[32:40]).hex(' ')}")
    if len(r) >= 52:
        lv, e = r[40], [u16(r, 41), u16(r, 43), u16(r, 45)]
        log(f"pins (level/changes): P2_2 {lv & 1}/{e[0]}  P2_4 {lv >> 1 & 1}/{e[1]}  P3_1 {lv >> 2 & 1}/{e[2]} | "
            f"crown {s32(r, 47)} | button {'auto' if r[51] == 0xFF else pn(r[51])} presses {u32(r, 26)}")


async def main():
    a = sys.argv[1:] or ["status"]
    c = await connect()
    r = await cmd(c, [0x01])
    if not r or r[3] < 14:
        raise SystemExit("flash v14 first: bash run.sh ota_flash --go firmware/v14/app_MP.bin")
    t = int(time.time() - time.timezone + (3600 if time.localtime().tm_isdst > 0 else 0))
    await cmd(c, [0x31] + list(t.to_bytes(4, "little")), 2)
    w = a[0]
    if w == "start":
        show(await cmd(c, [0x30, 1]))
        log("screen powering up: takes ~25 s (soft start). Run 'bash run.sh os_ctl' to see it reach RUNNING.")
    elif w == "stop":
        show(await cmd(c, [0x30, 0]))
    elif w == "screen":
        await cmd(c, [0x32, 6, int(a[1])])
    elif w == "set":
        k, v = KEYS[a[1]], a[2]
        v = 0xFF if v == "auto" else PINS[v.upper()] if v.upper() in PINS else int(v, 0)
        r = await cmd(c, [0x32, k, v])
        log("saved" if r and r[0] == 0xB2 else f"no answer {r}")
    elif w in ("tap", "swipe", "press", "long"):
        ev = EV["press" if w == "press" else a[1] if w == "swipe" else w]
        x, y = (int(a[1]), int(a[2])) if w in ("tap", "long") and len(a) >= 3 else (184, 224)
        await cmd(c, [0x33, ev, x & 255, x >> 8, y & 255, y >> 8])
    elif w == "i2c":
        wr = [int(x, 16) for x in a[2].split(",")] if a[2] != "-" else []
        r = await cmd(c, [0x35, int(a[1], 16), len(wr)] + wr + [int(a[3])])
        log("ACK, data:" if r and r[1] == 0 else "NO ACK:", r and bytes(r[3:]).hex(" "))
    elif w == "probe":
        r = await cmd(c, [0x34], 6)
        log(f"touch chip: 0x{r[1]:02X} on SCL {pn(r[2])} SDA {pn(r[3])}" if r and r[1] else f"none found ({r})")
    elif w == "watch":
        log("live status every second, Ctrl+C to stop")
        while True:
            show(await cmd(c, [0x30, 2]))
            await asyncio.sleep(1)
    if w != "watch":
        show(await cmd(c, [0x30, 2]))
    await c.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
