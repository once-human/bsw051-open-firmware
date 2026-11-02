"""Read battery level (standard BLE battery service). Usage: bash run.sh battery"""
import asyncio
from bleak import BleakScanner, BleakClient
ADDR = "00:E0:12:34:56:78"   # new address under our firmware (old: D7:B1:8B:17:BA:3E)
async def main():
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    if not dev: print("Watch not found"); return
    async with BleakClient(dev, timeout=25) as c:
        lvl = bytes(await c.read_gatt_char("00002a19-0000-1000-8000-00805f9b34fb"))[0]
        print(f"BATTERY {lvl-100}% CHARGING (raw {lvl})" if lvl > 100 else f"BATTERY {lvl}% (not charging)")
asyncio.run(main())
