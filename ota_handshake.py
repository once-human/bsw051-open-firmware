"""HANDSHAKE PROBE (not purely read-only, but writes NO firmware):
Sends only DFU opcode 0x01 START_DFU with an encrypted 16-byte image header, reads the
OK / INVALID reply, then disconnects. Per Realtek SDK, START_DFU only checks the header
(ic type, image id) and sets RAM state; flash is only touched when image DATA arrives,
which this script NEVER sends. Worst case: the watch reboots once after we disconnect.

Step A: find the correct AES byte order using the App header (wrong order -> harmless INVALID).
Step B: with the right order, ask about RomPatch and UpperStack headers (fresh connection each).
Usage: bash run.sh ota_handshake
"""
import asyncio, glob, os
from bleak import BleakScanner, BleakClient
from Crypto.Cipher import AES

ADDR = "D7:B1:8B:17:BA:3E"
CP = "00006487-3c17-d293-8e48-14fe2e4da212"
K = bytes.fromhex("4e46f8c5092b29e29a971a0cd1f610fb1f6763df807a7e70960d4cd3118e601a")
SDK = os.path.expanduser("~/Projects/dafit-watch/sdk/rtl8762d-hmi-sdk-master")
BIN = SDK + "/bin/default_bin/disable_bank_switch/bank0/"

def hdr(path):
    b = open(glob.glob(path)[0], "rb").read()
    h = b[0x200:0x200 + 12]
    assert h[0] == 9, f"not an RTL8762D image header: {path}"
    return h

IMAGES = {
    "App (our build)":   hdr(SDK + "/board/evb_stack_img/silent_ota_gcc/bin/app_MP.bin"),
    "RomPatch 0.0.440.4": hdr(BIN + "Patch_MP_release_*.bin"),
    "UpperStack 1.1.5.0": hdr(BIN + "upperstack_MP_*.bin"),
}
VARIANTS = {
    "A standard":            lambda b: AES.new(K, AES.MODE_ECB).encrypt(b),
    "B reverse all":         lambda b: AES.new(K[::-1], AES.MODE_ECB).encrypt(b[::-1])[::-1],
    "C reverse key":         lambda b: AES.new(K[::-1], AES.MODE_ECB).encrypt(b),
    "D reverse data":        lambda b: AES.new(K, AES.MODE_ECB).encrypt(b[::-1])[::-1],
    "E no encryption":       lambda b: b,
}
STATUS = {1: "OK (accepted)", 2: "INVALID parameter", 3: "operation failed", 6: "length error",
          9: "version error", 255: "unknown opcode"}
reply = []

def on_notify(_c, d):
    reply.append(bytes(d)); print("    <- notify", bytes(d).hex(), flush=True)

async def start_dfu(name, header12, variant):
    pkt = bytes([0x01]) + VARIANTS[variant](header12 + b"\x00" * 4)
    assert pkt[0] == 0x01 and len(pkt) == 17      # only START_DFU, ever
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=25)
    if not dev:
        print("  watch not found (maybe rebooting) - waiting 10s"); await asyncio.sleep(10)
        dev = await BleakScanner.find_device_by_address(ADDR, timeout=25)
        if not dev: print("  still not found, stopping"); return None
    async with BleakClient(dev, timeout=25) as c:
        await c.start_notify(CP, on_notify); await asyncio.sleep(0.4)
        reply.clear()
        print(f"  -> START_DFU {name} [{variant}] header={header12.hex()} pkt={pkt.hex()}", flush=True)
        await c.write_gatt_char(CP, pkt, response=True)
        for _ in range(30):
            if reply: break
            await asyncio.sleep(0.1)
    st = reply[0][2] if reply and len(reply[0]) >= 3 and reply[0][1] == 0x01 else None
    print(f"     RESULT: {STATUS.get(st, st)}", flush=True)
    await asyncio.sleep(6)   # let watch time out / reboot if it wants to
    return st

async def main():
    print("## Step A: find AES byte order (App header)")
    ok = None
    for v in VARIANTS:
        st = await start_dfu("App", IMAGES["App (our build)"], v)
        if st == 1: ok = v; break
    if not ok:
        print("\nNo variant accepted -> stop. (Key/order/header format differs; nothing was written.)"); return
    print(f"\nAES order confirmed: {ok}")
    print("\n## Step B: would the watch take these parts?")
    for name in ("RomPatch 0.0.440.4", "UpperStack 1.1.5.0"):
        await start_dfu(name, IMAGES[name], ok)
    print("DONE")

asyncio.run(main())
