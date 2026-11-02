"""Upload a MoYoung/Da Fit watch face .bin to the BSW051 (MOYOUNG-V2).
Protocol copied from DaFup-cli.py (VicGuy/DaFup, GPLv3). Face goes to slot 6.
Usage: bash run.sh upload_face faces/hello.bin
"""
import asyncio, sys, time
from bleak import BleakScanner, BleakClient

ADDR = "D7:B1:8B:17:BA:3E"
CTRL = "0000fee2-0000-1000-8000-00805f9b34fb"   # commands (write, no response)
NOTI = "0000fee3-0000-1000-8000-00805f9b34fb"   # answers (notify)
SEND = "0000fee6-0000-1000-8000-00805f9b34fb"   # bulk data (write, no response)
MANU = "00002a29-0000-1000-8000-00805f9b34fb"   # manufacturer name
SLOT = 6
CHUNK = 512
DELAY = 0.3


def on_notify(_c, data):
    print("  <- notify", bytes(data).hex(), flush=True)


async def main(path):
    data = open(path, "rb").read()
    print(f"file {path}: {len(data)} bytes", flush=True)
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    if not dev:
        print("Watch not found. iPhone Bluetooth OFF? Watch screen awake?")
        return
    async with BleakClient(dev, timeout=25) as c:
        manu = bytes(await c.read_gatt_char(MANU)).decode(errors="replace")
        print("manufacturer:", manu, flush=True)
        if manu != "MOYOUNG-V2":
            print("Not MOYOUNG-V2, stopping.")
            return
        await c.start_notify(NOTI, on_notify)

        await c.write_gatt_char(CTRL, bytes.fromhex("feea200974") + len(data).to_bytes(4, "big"), response=False)
        print("start-transfer sent", flush=True)
        await asyncio.sleep(0.5)

        chunk = CHUNK
        pos, n, t0 = 0, 0, time.time()
        while pos < len(data):
            piece = data[pos:pos + chunk]
            try:
                await c.write_gatt_char(SEND, piece, response=False)
            except Exception as e:
                smaller = [x for x in (512, 244, 180, 100, 20) if x < chunk]
                if smaller:
                    chunk = smaller[0]
                    print(f"  write of {len(piece)} bytes failed ({e!r}); retrying with {chunk}-byte chunks", flush=True)
                    continue
                raise
            pos += len(piece)
            n += 1
            if n % 20 == 0 or pos >= len(data):
                print(f"  sent {pos}/{len(data)} bytes ({100*pos//len(data)}%) {time.time()-t0:.0f}s", flush=True)
            await asyncio.sleep(max(0.03, DELAY * chunk / 512))

        await c.write_gatt_char(CTRL, bytes.fromhex("feea20097400000000"), response=False)
        await asyncio.sleep(0.3)
        await c.write_gatt_char(CTRL, bytes.fromhex("feea200ab41130040000"), response=False)
        await asyncio.sleep(0.3)
        await c.write_gatt_char(CTRL, bytes.fromhex("feea200619") + bytes([SLOT]), response=False)
        print(f"finish + select face slot {SLOT} sent", flush=True)
        await asyncio.sleep(3)
        await c.write_gatt_char(CTRL, bytes.fromhex("feea200529"), response=False)  # ask which face is showing
        await asyncio.sleep(2)
        await c.stop_notify(NOTI)
    print("DONE - look at the watch screen now")


if len(sys.argv) < 2:
    print("usage: bash run.sh upload_face faces/hello.bin")
else:
    asyncio.run(main(sys.argv[1]))
