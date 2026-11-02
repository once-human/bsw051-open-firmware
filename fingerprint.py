"""Full read-only fingerprint of the watch: advertisement + every GATT service,
characteristic, descriptor. Reads only standard/info characteristics (safe).
Usage: bash run.sh fingerprint
"""
import asyncio, subprocess
from bleak import BleakScanner, BleakClient

ADDR = "D7:B1:8B:17:BA:3E"
SAFE_READ = ("2a00", "2a01", "2a04", "2a19", "2a23", "2a24", "2a25", "2a26",
             "2a27", "2a28", "2a29", "2a2a", "2a50")

async def main():
    print("## advertisement", flush=True)
    found = await BleakScanner.discover(timeout=12, return_adv=True)
    for addr, (dev, adv) in found.items():
        if addr.upper() == ADDR:
            print("name:", adv.local_name, "| rssi:", adv.rssi)
            print("service_uuids:", adv.service_uuids)
            print("manufacturer_data:", {k: v.hex() for k, v in adv.manufacturer_data.items()})
            print("service_data:", {k: v.hex() for k, v in adv.service_data.items()})
            print("tx_power:", adv.tx_power)
    print("\n## other nearby devices with similar names (classic/second radio?)")
    for addr, (dev, adv) in found.items():
        n = (adv.local_name or "")
        if addr.upper() != ADDR and n and any(s in n.upper() for s in ("BSW", "FIRE", "BOLTT", "CALL", "WATCH")):
            print(" ", addr, n, adv.service_uuids, {k: v.hex() for k, v in adv.manufacturer_data.items()})

    print("\n## GATT", flush=True)
    async with BleakClient(ADDR, timeout=25) as c:
        print("mtu:", c.mtu_size)
        for s in c.services:
            print(f"SERVICE {s.uuid}  ({s.description})  handle={s.handle}")
            for ch in s.characteristics:
                line = f"   CHAR {ch.uuid}  {','.join(ch.properties)}  handle={ch.handle}  ({ch.description})"
                short = ch.uuid[4:8]
                if "read" in ch.properties and ch.uuid.endswith("-0000-1000-8000-00805f9b34fb") and short in SAFE_READ:
                    try:
                        v = bytes(await asyncio.wait_for(c.read_gatt_char(ch), 3))
                        line += f"\n        = {v!r}  hex={v.hex()}"
                    except Exception as e:
                        line += f"\n        (read failed: {e})"
                print(line, flush=True)
                for d in ch.descriptors:
                    print(f"      DESC {d.uuid} handle={d.handle} ({d.description})")
    print("\n## bluetoothctl info")
    try:
        print(subprocess.run(["bluetoothctl", "info", ADDR], capture_output=True, text=True, timeout=10).stdout)
        print(subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True, timeout=10).stdout)
    except Exception as e:
        print("bluetoothctl failed:", e)
    print("DONE")

asyncio.run(main())
