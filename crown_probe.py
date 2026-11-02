"""Does the crown produce any signal?   bash run.sh crown_probe   (Ctrl+C to stop)
Beeps twice, then for 60 s reads the two crown pins (P1_0, P2_6) as fast as Bluetooth allows while you turn the crown.
The pins go straight back to the crown decoder after every read (screen keeps running). Also shows the decoder's count.
"""
import asyncio, time
from tool5 import connect, cmd, log, beep

PINS = {"P1_0": 8, "P2_6": 22}


async def qdec(c):
    r = await cmd(c, [0x30, 2], 3)
    return int.from_bytes(bytes(r[47:51]), "little", signed=True) if r and len(r) >= 51 else None


async def main():
    c = await connect()
    q0 = await qdec(c)
    beep("lost")
    log(">>> TURN THE CROWN NOW, slowly, a few clicks each way, for the next 60 s")
    last, changes, n = {}, {k: 0 for k in PINS}, 0
    t0 = time.time()
    while time.time() - t0 < 60:
        for name, p in PINS.items():
            r = await cmd(c, [0x04, p, 3], 2)
            if not r or r[0] != 0x84:
                continue
            v = r[2]
            n += 1
            if name in last and v != last[name]:
                changes[name] += 1
                log(f"   {name} -> {v}")
            last[name] = v
    q1 = await qdec(c)
    log(f"reads {n} | changes: {changes} | decoder count {q0} -> {q1}")
    if any(changes.values()):
        log("RESULT: crown pins DO change -> hardware works, decoder setup is the problem (fixable in firmware)")
    else:
        log("RESULT: no change on either pin -> crown not on these pins, not powered, or it doesn't rotate electrically")
    beep("found")
    await c.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
