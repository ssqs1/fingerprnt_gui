import os
import time
import ctypes
from ctypes import byref, c_int, c_uint, c_ubyte, c_char_p, c_void_p
from datetime import datetime

# ===== User config =====
DLL_NAME = "SynoAPIEx.dll"         # Put next to this script or add folder to PATH
DEFAULT_ADDR = 0xFFFFFFFF          # Default module address
TIMEOUT_SECONDS = 30               # Wait up to 30s for a finger

# ===== Folder for BMP =====
OUTPUT_DIR = "fingerprint/normal"
os.makedirs(OUTPUT_DIR, exist_ok=True)  # make folder if not exist

number_of_images = 10
# ===== Load DLL safely =====
def load_vendor_dll(name: str) -> ctypes.CDLL:
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(here, name)
        return ctypes.WinDLL(candidate if os.path.isfile(candidate) else name)
    except OSError as e:
        raise SystemExit(
            f"Failed to load {name}. Make sure 64-bit Python matches a 64-bit DLL "
            f"and the DLL is next to this script or in PATH.\nWindows error: {e}"
        )

dll = load_vendor_dll(DLL_NAME)

# ===== Types & constants =====
HANDLE = c_void_p
DEVICE_USB, DEVICE_COM, DEVICE_UDISK = 0, 1, 2
PS_OK, PS_COMM_ERR, PS_NO_FINGER = 0x00, 0x01, 0x02
IMAGE_X, IMAGE_Y = 256, 288
IMAGE_BYTES = IMAGE_X * IMAGE_Y

# ===== Function signatures =====
dll.PSOpenDeviceEx.argtypes = [ctypes.POINTER(HANDLE), c_int, c_int, c_int, c_int, c_int]
dll.PSOpenDeviceEx.restype  = c_int

dll.PSAutoOpen.argtypes = [ctypes.POINTER(HANDLE), ctypes.POINTER(c_int), c_int, c_uint, c_int]
dll.PSAutoOpen.restype  = c_int

dll.PSGetUSBDevNum.argtypes = [ctypes.POINTER(c_int)]
dll.PSGetUSBDevNum.restype  = c_int

dll.PSGetUDiskNum.argtypes = [ctypes.POINTER(c_int)]
dll.PSGetUDiskNum.restype  = c_int

dll.PSCloseDeviceEx.argtypes = [HANDLE]
dll.PSCloseDeviceEx.restype  = c_int

dll.PSGetImage.argtypes = [HANDLE, c_int]
dll.PSGetImage.restype  = c_int

dll.PSUpImage.argtypes = [HANDLE, c_int, ctypes.POINTER(c_ubyte), ctypes.POINTER(c_int)]
dll.PSUpImage.restype  = c_int

dll.PSImgData2BMP.argtypes = [ctypes.POINTER(c_ubyte), c_char_p]
dll.PSImgData2BMP.restype  = c_int

dll.PSErr2Str.argtypes = [c_int]
dll.PSErr2Str.restype  = ctypes.c_char_p

def err_text(code: int) -> str:
    s = dll.PSErr2Str(code)
    return s.decode(errors="ignore") if s else f"Error 0x{code:02X}"

def close_device(h: HANDLE):
    if h:
        dll.PSCloseDeviceEx(h)

# ===== Open helpers =====
def try_PSAutoOpen() -> tuple[HANDLE, int]:
    h = HANDLE()
    dtype = c_int(-1)
    rc = dll.PSAutoOpen(byref(h), byref(dtype), DEFAULT_ADDR, 0, 1)
    if rc == PS_OK and h:
        return h, dtype.value
    raise RuntimeError(f"PSAutoOpen failed: {err_text(rc)}")

def try_USB_explicit() -> HANDLE:
    for nPackageSize in (2, 3, 1, 0, 4):
        h = HANDLE()
        rc = dll.PSOpenDeviceEx(byref(h), DEVICE_USB, 1, 1, nPackageSize, 0)
        if rc == PS_OK and h:
            print(f"[USB] Open OK with nPackageSize={nPackageSize}")
            return h
    raise RuntimeError("USB open attempts failed.")

def try_COM_scan() -> HANDLE:
    for com in range(1, 31):
        for ibaud in (6, 12):
            h = HANDLE()
            rc = dll.PSOpenDeviceEx(byref(h), DEVICE_COM, com, ibaud, 2, 0)
            if rc == PS_OK and h:
                print(f"[COM] Open OK on COM{com} @ {ibaud*9600} bps")
                return h
    raise RuntimeError("COM open attempts failed.")

def open_device_resilient() -> tuple[HANDLE, str]:
    usb_n = c_int(0)
    if dll.PSGetUSBDevNum(byref(usb_n)) == PS_OK:
        print(f"DLL reports USB devices: {usb_n.value}")
    udisks = c_int(0)
    if dll.PSGetUDiskNum(byref(udisks)) == PS_OK:
        print(f"DLL reports UDISK devices: {udisks.value}")

    try:
        h, dtype = try_PSAutoOpen()
        mode = "USB" if dtype == DEVICE_USB else ("COM" if dtype == DEVICE_COM else f"type={dtype}")
        print(f"PSAutoOpen succeeded. Mode: {mode}")
        return h, mode
    except Exception as e:
        print(str(e))

    try:
        h = try_USB_explicit()
        return h, "USB"
    except Exception as e:
        print(str(e))

    h = try_COM_scan()
    return h, "COM"

# ===== Capture helpers =====
def wait_for_finger_and_capture(h: HANDLE, addr: int, timeout_s: int) -> bytes:
    t0 = time.time()
    while True:
        rc = dll.PSGetImage(h, addr)
        if rc == PS_OK:
            break
        if rc == PS_NO_FINGER:
            if time.time() - t0 > timeout_s:
                raise TimeoutError("No finger detected within timeout.")
            time.sleep(0.15)
            continue
        raise RuntimeError(f"PSGetImage failed: {err_text(rc)}")

    img_buf = (c_ubyte * IMAGE_BYTES)()
    img_len = c_int(IMAGE_BYTES)
    rc = dll.PSUpImage(h, addr, img_buf, byref(img_len))
    if rc != PS_OK:
        raise RuntimeError(f"PSUpImage failed: {err_text(rc)}")
    return bytes(bytearray(img_buf)[:img_len.value])

def save_bmp_via_dll(img_bytes: bytes):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_DIR, f"fingerprint_{timestamp}.bmp")
    buf = (c_ubyte * len(img_bytes)).from_buffer_copy(img_bytes)
    rc = dll.PSImgData2BMP(buf, out_path.encode("utf-8"))
    if rc != PS_OK:
        raise RuntimeError(f"PSImgData2BMP failed: {err_text(rc)}")
    print(f"Saved BMP → {out_path}")

# ===== Main =====
def main():
    print("Opening fingerprint device …")
    h = None
    try:
        for i in range(number_of_images):
            h, mode = open_device_resilient()
            print(f"Opened in {mode} mode. Place finger on the sensor …")
            img = wait_for_finger_and_capture(h, DEFAULT_ADDR, TIMEOUT_SECONDS)
            print(f"Captured {len(img)} bytes.")
            save_bmp_via_dll(img)
            print("Done.")
    finally:
        close_device(h)

if __name__ == "__main__":
    main()
