"""READ-ONLY: read every readable characteristic of the Realtek OTA service (d0ff).
Writes NOTHING to the watch. Tells us chip type, image versions, secure/AES flags,
and whether the watch has two firmware banks (= a built-in way back if an update fails).
Usage: bash run.sh rtk_info
"""
import asyncio
from bleak import BleakScanner, BleakClient

ADDR = "D7:B1:8B:17:BA:3E"
OTA_SVC = "0000d0ff-3c17-d293-8e48-14fe2e4da212"

async def main():
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    if not dev:
        print("Watch not found. iPhone Bluetooth OFF? Watch screen awake?"); return
    async with BleakClient(dev, timeout=25) as c:
        bat = bytes(await c.read_gatt_char("00002a19-0000-1000-8000-00805f9b34fb"))
        print("battery %:", bat[0], flush=True)
        svc = c.services.get_service(OTA_SVC)
        for ch in sorted(svc.characteristics, key=lambda x: x.handle):
            if "read" not in ch.properties:
                print(f"skip  {ch.uuid[4:8]} ({','.join(ch.properties)})  -- not read, never touched", flush=True)
                continue
            try:
                v = bytes(await asyncio.wait_for(c.read_gatt_char(ch), 4))
                print(f"READ  {ch.uuid[4:8]} handle={ch.handle} len={len(v)} hex={v.hex()}", flush=True)
            except Exception as e:
                print(f"READ  {ch.uuid[4:8]} failed: {e!r}", flush=True)
    print("DONE")

asyncio.run(main())
