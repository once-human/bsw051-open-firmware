"""DRY RUN 2: ask the watch "would you accept image X at version Y?" (opcode 0x0d).
Per Realtek SDK this only COMPARES versions and sets a RAM flag. No firmware is sent.
Allowlist enforced: only 0x0d.
Usage: bash run.sh ota_dryrun2
"""
import asyncio
from bleak import BleakScanner, BleakClient

ADDR = "D7:B1:8B:17:BA:3E"
CP = "00006487-3c17-d293-8e48-14fe2e4da212"
TESTS = [  # (label, image_id, version)
    ("App     SDK 1.8.0.28 (newer than watch 1.0.0.18)", 0x2793, 0xE0000081),
    ("App     same as watch 1.0.0.18",                    0x2793, 0x90000001),
    ("App     OLDER 1.0.0.1  (is downgrade blocked?)",    0x2793, 0x08000001),
    ("Patch   SDK 0.0.440.4 (newer than watch 0.0.239.11)", 0x2792, 0x201B8000),
    ("Patch   OLDER 0.0.110.13 (downgrade?)",             0x2792, 0x6806E000),
    ("UpperStack SDK 1.1.5.0 (does watch know this id?)", 0x279A, 0x00005011),
    ("SecureBoot SDK 0.0.2.2",                            0x2791, 0x10002000),
]
got = []
def on_notify(_c, d):
    got.append(bytes(d)); print("    <- notify", bytes(d).hex(), flush=True)

async def main():
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    if not dev:
        print("Watch not found. iPhone Bluetooth OFF? Watch screen awake?"); return
    async with BleakClient(dev, timeout=25) as c:
        await c.start_notify(CP, on_notify); await asyncio.sleep(0.5)
        for label, img, v in TESTS:
            payload = bytes([0x0D]) + img.to_bytes(2, "little") + v.to_bytes(4, "little")
            assert payload[0] == 0x0D
            got.clear(); print(f"\n## {label}\n  -> write {payload.hex()}", flush=True)
            await c.write_gatt_char(CP, payload, response=True)
            for _ in range(20):
                if got: break
                await asyncio.sleep(0.1)
            if got and len(got[0]) >= 3:
                print("   RESULT:", "ACCEPT (status 1)" if got[0][2] == 1 else f"REJECT (status {got[0][2]})", flush=True)
            else:
                print("   RESULT: no reply", flush=True)
            await asyncio.sleep(0.3)
        await c.stop_notify(CP)
    print("DONE")

asyncio.run(main())
