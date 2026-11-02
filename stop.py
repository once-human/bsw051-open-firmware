"""EMERGENCY STOP: drive the probe pins LOW, then reboot the watch (all pins back to default).
Usage: bash run.sh stop"""
import asyncio, subprocess, time
from bleak import BleakScanner, BleakClient
W = "0000b002-0000-1000-8000-00805f9b34fb"
CP = "00006487-3c17-d293-8e48-14fe2e4da212"
ADDR = "00:E0:12:34:56:78"
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
async def main():
    subprocess.run(["bluetoothctl", "disconnect", ADDR], capture_output=True, timeout=10)
    await asyncio.sleep(2)
    dev = None
    for _ in range(4):
        found = await BleakScanner.discover(timeout=6, return_adv=True)
        dev = next((d for a, (d, adv) in found.items() if a.upper() == ADDR or (adv.local_name or "").startswith("ONKAR")), None)
        if dev: break
        subprocess.run(["bluetoothctl", "disconnect", ADDR], capture_output=True, timeout=10)
    if not dev: log("watch not found"); return
    async with BleakClient(dev, timeout=25) as c:
        for pin in (6, 7, 35, 32, 34):          # P0_6, P0_7, P4_3, P4_0, P4_2 -> LOW
            await c.write_gatt_char(W, bytes([0x03, pin, 0]), response=True)
            log(f"pin {pin} -> LOW")
            await asyncio.sleep(0.2)
        log("pins low. Rebooting the watch to reset every pin to its default...")
        try:
            await c.write_gatt_char(CP, bytes([0x05]), response=True)   # DFU system reset (just a reboot)
        except Exception as e:
            log("(disconnect during reboot is normal)", e)
    log("DONE - vibration should be stopped")
asyncio.run(main())
