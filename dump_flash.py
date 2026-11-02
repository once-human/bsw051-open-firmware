"""Copy the watch's whole memory to the laptop (read-only, changes nothing on the watch).
   bash run.sh dump_flash        (Ctrl+C is safe: run it again and it continues where it stopped)

Result: logs/flash_dump.bin   - Claude digs the original firmware's screen code out of it.
1 beep when finished, 2 beeps if the watch drops (replug, the script waits and resumes).
"""
import asyncio, json, os, re, time
from tool5 import connect, log, WatchGone, alive, watch_back, beep, W, q

BASE = 0x00800000
HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "logs", "flash_dump.bin")
PROG = os.path.join(HERE, "logs", "flash_dump.json")
CH = 236


async def read_chunks(c, addrs):
    """pipelined reads; returns {addr: bytes}"""
    while not q.empty():
        q.get_nowait()
    for a in addrs:
        await c.write_gatt_char(W, bytes([0x1C, *a.to_bytes(4, "little"), CH]), response=True)
    out = {}
    t0 = time.time()
    while len(out) < len(addrs) and time.time() - t0 < 4:
        try:
            r = await asyncio.wait_for(q.get(), 1.0)
        except asyncio.TimeoutError:
            continue
        if r and r[0] == 0x9C and len(r) >= 5:
            out[int.from_bytes(r[1:5], "little")] = bytes(r[5:])
    return out


async def flash_size(c):
    """the flash repeats itself after its real size; find where"""
    first = (await read_chunks(c, [BASE])).get(BASE)
    for mb in (1, 2, 4, 8):
        a = BASE + mb * 0x100000
        if a + CH > 0x01800000:
            break
        got = (await read_chunks(c, [a])).get(a)
        if got is None or got == first:
            return mb * 0x100000
    return 0x00400000          # cap: 4 MB


async def main():
    c = await connect()
    from tool5 import cmd
    r = await cmd(c, [0x01])
    if not r or r[3] < 9:
        raise SystemExit("flash v9 first: bash run.sh ota_flash --go firmware/v9/app_MP.bin")
    prog = json.load(open(PROG)) if os.path.exists(PROG) else {}
    if "size" not in prog:
        prog["size"] = await flash_size(c)
        prog["next"] = BASE
        open(BIN, "wb").close()
        json.dump(prog, open(PROG, "w"))
    size, nxt = prog["size"], prog["next"]
    log(f"watch memory: {size // 1024} KB. Copying from 0x{nxt:08X} (already have {(nxt - BASE) // 1024} KB)")
    t0, done0 = time.time(), nxt
    with open(BIN, "r+b") as f:
        while nxt < BASE + size:
            addrs = [nxt + i * CH for i in range(6) if nxt + i * CH < BASE + size]
            try:
                got = await read_chunks(c, addrs)
            except Exception:
                got = {}
            if len(got) < len(addrs):
                if not await alive(c):
                    beep("lost")
                    c = await watch_back(c)
                continue
            for a in addrs:
                f.seek(a - BASE)
                f.write(got[a][:min(CH, BASE + size - a)])
            nxt = addrs[-1] + CH
            prog["next"] = nxt
            if (nxt - BASE) % (CH * 6 * 40) < CH * 6:
                json.dump(prog, open(PROG, "w"))
                rate = (nxt - done0) / max(1, time.time() - t0)
                left = (BASE + size - nxt) / max(rate, 1)
                print(f"\r   {(nxt - BASE) // 1024} / {size // 1024} KB  ({rate / 1024:.1f} KB/s, ~{left / 60:.0f} min left)   ",
                      end="", flush=True)
    json.dump(prog, open(PROG, "w"))
    print()
    log(f"DONE: logs/flash_dump.bin ({size // 1024} KB)")
    data = open(BIN, "rb").read()
    hits = sorted({m.group().decode(errors="replace") for m in re.finditer(rb"[ -~]{6,}", data)
                   if re.search(rb"(?i)lcd|st77|sh86|co53|icna|gc9|nv30|jd98|rm6|ili|oled|amoled|okj5|moy-|disp|panel|tp_|touch|motor|vib", m.group())})
    log(f"interesting text found in memory ({len(hits)}):")
    for h in hits[:80]:
        print("    ", h[:100])
    try:
        await cmd(c, [0x0B], 2)
        await c.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped - run it again to continue where it left off.")
