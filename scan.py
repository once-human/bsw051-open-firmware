import asyncio
from bleak import BleakScanner, BleakClient

ADDR = "D7:B1:8B:17:BA:3E"

async def main():
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=15)
    if not dev:
        print("Not found")
        return
    async with BleakClient(dev) as c:
        for s in c.services:
            print("SERVICE", s.uuid)
            for ch in s.characteristics:
                line = f"  {ch.uuid} {ch.properties}"
                if "read" in ch.properties and ("180a" in s.uuid or "1800" in s.uuid):
                    try:
                        line += f" = {bytes(await asyncio.wait_for(c.read_gatt_char(ch), 3))!r}"
                    except Exception as e:
                        line += f" (read failed: {e})"
                print(line)

asyncio.run(main())
print("DONE")
