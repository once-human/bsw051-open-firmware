"""Check our firmware (ONKAR-LIFE): services present, battery value, OTA device info.
Read-only. Usage: bash run.sh lifeline_check"""
import asyncio
from bleak import BleakScanner, BleakClient

async def main():
    found = await BleakScanner.discover(timeout=10, return_adv=True)
    dev = next((d for a, (d, adv) in found.items() if (adv.local_name or "").startswith("ONKAR")), None)
    if not dev: print("ONKAR-LIFE not found"); return
    print("found", dev.address, dev.name)
    async with BleakClient(dev, timeout=25) as c:
        for s in c.services:
            print("SERVICE", s.uuid, s.description)
            for ch in s.characteristics:
                line = f"   {ch.uuid[4:8] if ch.uuid.endswith('00805f9b34fb') else ch.uuid} {','.join(ch.properties)}"
                if "read" in ch.properties:
                    try: line += " = " + bytes(await asyncio.wait_for(c.read_gatt_char(ch), 3)).hex()
                    except Exception as e: line += f" (read failed {e})"
                print(line)
    print("DONE")
asyncio.run(main())
