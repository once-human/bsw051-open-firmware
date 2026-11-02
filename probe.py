"""Read-only probe of the BSW051 (Moyoung V2 protocol).
Sends only QUERY commands (see Gadgetbridge MoyoungConstants.java), never SET commands.
"""
import asyncio, time
from bleak import BleakScanner, BleakClient

ADDR = "D7:B1:8B:17:BA:3E"
FEE2 = "0000fee2-0000-1000-8000-00805f9b34fb"  # commands out (write)
FEE3 = "0000fee3-0000-1000-8000-00805f9b34fb"  # answers in (notify)
BATT = "00002a19-0000-1000-8000-00805f9b34fb"

# (label, command byte, payload) - all read-only queries
QUERIES = [
    ("display device function: current", 37, b""),
    ("display device function: list all supported", 37, bytes([0xFF])),
    ("which watch face is showing", 41, b""),
    ("how many watch faces supported", 0x84, b""),
    ("watch face layout (custom face settings)", 57, b""),
    ("quick view / raise wrist", 40, b""),
    ("time system 12/24h", 39, b""),
    ("device version", 46, b""),
    ("language", 43, b""),
    ("power saving", 0xA4, b""),
]


def frame(cmd, payload=b""):
    n = len(payload) + 5
    return bytes([0xFE, 0xEA, 0x20 + (n >> 8), n & 0xFF, cmd]) + payload


buf = bytearray()


def on_notify(_char, data):
    global buf
    chunk = bytes(data)
    print("  <- raw", chunk.hex(), flush=True)
    if not buf and not chunk.startswith(b"\xfe\xea"):
        return
    buf += chunk
    while len(buf) >= 4:
        hi = buf[2]
        if hi == 16:
            length = buf[3]
        elif hi >= 32:
            length = ((hi - 32) << 8) | buf[3]
        else:
            buf.clear()
            return
        if length < 5 or len(buf) < length:
            break
        pkt = bytes(buf[:length])
        del buf[:length]
        print(f"  <- packet cmd={pkt[4]} (0x{pkt[4]:02x}) payload={pkt[5:].hex()}", flush=True)


async def send(client, cmd, payload=b""):
    data = frame(cmd, payload)
    print(f"  -> cmd={cmd} (0x{cmd:02x}) frame={data.hex()}", flush=True)
    for i in range(0, len(data), 20):
        await client.write_gatt_char(FEE2, data[i:i + 20], response=False)
        await asyncio.sleep(0.03)


async def main():
    print("time", time.strftime("%Y-%m-%d %H:%M:%S"), flush=True)
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    if not dev:
        print("Watch not found. iPhone Bluetooth OFF? Watch screen awake?")
        return
    async with BleakClient(dev, timeout=25) as c:
        try:
            print("connected, mtu_size =", c.mtu_size, flush=True)
        except Exception as e:
            print("mtu unknown", e)
        try:
            batt = await c.read_gatt_char(BATT)
            print("battery % =", batt[0], flush=True)
        except Exception as e:
            print("battery read failed", repr(e))
        await c.start_notify(FEE3, on_notify)
        print("notifications on FEE3 started", flush=True)
        for label, cmd, payload in QUERIES:
            print(f"\n## {label}", flush=True)
            try:
                await send(c, cmd, payload)
            except Exception as e:
                print("  send failed", repr(e))
                continue
            await asyncio.sleep(1.5)
        await asyncio.sleep(1)
        await c.stop_notify(FEE3)
    print("\nDONE")


asyncio.run(main())
