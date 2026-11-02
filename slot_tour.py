"""Step the BSW051 through face slots 0..6 so we can see which slot holds what.
Usage: bash run.sh slot_tour
"""
import asyncio
from bleak import BleakScanner, BleakClient

ADDR = "D7:B1:8B:17:BA:3E"
CTRL = "0000fee2-0000-1000-8000-00805f9b34fb"
NOTI = "0000fee3-0000-1000-8000-00805f9b34fb"
PAUSE = 7


def on_notify(_c, data):
    print("    <- notify", bytes(data).hex(), flush=True)


async def main():
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    if not dev:
        print("Watch not found. iPhone Bluetooth OFF? Watch screen awake?")
        return
    async with BleakClient(dev, timeout=25) as c:
        await c.start_notify(NOTI, on_notify)
        print("WATCH THE SCREEN. Each slot stays ~7 seconds.\n", flush=True)
        for n in [1, 0, 2, 3, 4, 5, 6]:
            await c.write_gatt_char(CTRL, bytes.fromhex("feea200619") + bytes([n]), response=False)
            print(f">>> SLOT {n} selected now (look at the watch)", flush=True)
            await asyncio.sleep(2)
            await c.write_gatt_char(CTRL, bytes.fromhex("feea200529"), response=False)
            await asyncio.sleep(PAUSE - 2)
        await c.stop_notify(NOTI)
    print("DONE. Watch should be back on slot 6.", flush=True)

asyncio.run(main())
