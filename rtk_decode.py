"""Decode the newest rtk_info log using Realtek DFU SDK rules (DeviceInfo.parseX0000)."""
import glob, re, os, struct
log = sorted(glob.glob(os.path.join(os.path.dirname(__file__) or ".", "logs/*-rtk_info.txt")))[-1]
vals = dict(re.findall(r"READ\s+(\w{4}) handle=\d+ len=\d+ hex=([0-9a-f]*)", open(log).read()))
print("log:", log)
for k, v in vals.items(): print(f"  {k}: {v}")
def mode_bits(m):
    return {"buffer_check": bool(m & 1), "AES_encrypted_ota": bool(m & 2), "aes_mode": (m & 4) >> 2,
            "copy_image": bool(m & 8), "update_image_flag": (m & 16) >> 4, "rws": bool(m & 32)}
for key in ("fff1", "ffe0", "fff3"):
    b = bytes.fromhex(vals.get(key, ""))
    if len(b) < 2: continue
    print(f"\n== {key} parsed as DEVICE_INFO ==")
    ic, spec = b[0], b[1] & 0x0F
    print("  icType:", ic, " specVersion:", spec)
    if spec == 0:
        if len(b) >= 3: print("  appFreeBank:", b[2] & 0xF, " patchFreeBank:", b[2] >> 4, " (15/15 = single bank, no fallback)")
        if len(b) >= 4: print("  mode:", hex(b[3]), mode_bits(b[3]))
    else:
        if len(b) >= 3: print("  secureVersion:", b[2])
        if len(b) >= 4: print("  mode:", hex(b[3]), mode_bits(b[3]))
        if len(b) >= 6: print("  maxBufferCheckSize:", struct.unpack_from("<H", b, 4)[0])
        if len(b) >= 7: print("  otaTempBufferSize:", b[6])
        if len(b) >= 12: print("  imageVersionIndicator:", hex(struct.unpack_from("<I", b, 8)[0]), "(0 = no bank switching)")
for key, name in (("ffd3", "patch version"), ("ffd4", "app version"), ("ffd5", "patch ext version"), ("ffd2", "bd addr")):
    if key in vals: print(f"{name} ({key}):", vals[key])
