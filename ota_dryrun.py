"""DRY RUN of the Realtek DFU service: asks questions only, sends NO firmware.
Allowed opcodes (read-only per Realtek RTL8762D SDK dfu_service.c):
  0x0b  report IC type
  0x06  report target image version (per image id)
  0x0d  (1-byte form) device info on older firmware / harmless length error on newer
Every other opcode is blocked in code below.
Usage: bash run.sh ota_dryrun
"""
import asyncio
from bleak import BleakScanner, BleakClient

ADDR = "D7:B1:8B:17:BA:3E"
CP   = "00006487-3c17-d293-8e48-14fe2e4da212"   # DFU control point (write, notify)
SAFE = {0x0B, 0x06, 0x0D}
IMAGES = {0x2790: "OTA header", 0x2791: "SecureBoot", 0x2792: "RomPatch", 0x2793: "App",
          0x2794: "AppData1", 0x2795: "AppData2", 0x2796: "AppData3", 0x2797: "AppData4",
          0x2798: "AppData5", 0x2799: "AppData6", 0x279A: "UpperStack"}
replies = []

def ver(v, img):
    if img == 0x2790:
        return f"{(v>>24)&0xff}.{(v>>16)&0xff}.{(v>>8)&0xff}.{v&0xff}"
    return f"{v&0xf}.{(v>>4)&0xff}.{(v>>12)&0x7fff}.{(v>>27)&0x1f}"

def on_notify(_c, data):
    data = bytes(data); replies.append(data)
    print("    <- notify", data.hex(), flush=True)

async def send(c, payload):
    if payload[0] not in SAFE:
        raise SystemExit(f"BLOCKED opcode 0x{payload[0]:02x} - not in read-only allowlist")
    replies.clear()
    print("  -> write", payload.hex(), flush=True)
    await c.write_gatt_char(CP, payload, response=True)
    for _ in range(20):
        if replies: return replies[0]
        await asyncio.sleep(0.1)
    print("    (no reply in 2s)", flush=True)
    return None

async def main():
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    if not dev:
        print("Watch not found. iPhone Bluetooth OFF? Watch screen awake?"); return
    async with BleakClient(dev, timeout=25) as c:
        bat = bytes(await c.read_gatt_char("00002a19-0000-1000-8000-00805f9b34fb"))[0]
        print("battery %:", bat, flush=True)
        await c.start_notify(CP, on_notify)
        await asyncio.sleep(0.5)

        print("\n## IC type (0x0b)")
        r = await send(c, bytes([0x0B]))
        if r and len(r) >= 4: print(f"   status={r[2]} ic_type={r[3]}")

        print("\n## image versions (0x06 per image id)")
        for img, name in IMAGES.items():
            r = await send(c, bytes([0x06]) + img.to_bytes(2, "little"))
            if r and len(r) >= 11 and r[1] == 0x06:
                v = int.from_bytes(r[3:7], "little"); off = int.from_bytes(r[7:11], "little")
                print(f"   {name:<11} 0x{img:04x}: status={r[2]} version=0x{v:08x} ({ver(v,img)}) offset={off}")
            await asyncio.sleep(0.3)

        print("\n## 1-byte 0x0d (device info on some firmware)")
        await send(c, bytes([0x0D]))

        await c.stop_notify(CP)
    print("DONE")

asyncio.run(main())
