import os
import time
import ctypes
import requests
from ctypes import byref, c_int, c_uint, c_ubyte, c_char_p, c_void_p
from datetime import datetime


class Device:
    DLL_NAME = "SynoAPIEx.dll"
    DEFAULT_ADDR = 0xFFFFFFFF
    TIMEOUT_SECONDS = 30
    OUTPUT_DIR = "fingerprint/normal"

    # Constants
    DEVICE_USB, DEVICE_COM, DEVICE_UDISK = 0, 1, 2
    PS_OK, PS_COMM_ERR, PS_NO_FINGER = 0x00, 0x01, 0x02
    IMAGE_X, IMAGE_Y = 256, 288
    IMAGE_BYTES = IMAGE_X * IMAGE_Y

    def __init__(self):
        """Initialize the device and load the DLL."""
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        self.dll = self._load_vendor_dll(self.DLL_NAME)
        self._set_signatures()
        self.handle = None
        self.open_device()

    # ===== DLL Handling =====
    def _load_vendor_dll(self, name: str) -> ctypes.CDLL:
        here = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(here, name)
        return ctypes.WinDLL(candidate if os.path.isfile(candidate) else name)

    def _set_signatures(self):
        dll = self.dll
        HANDLE = c_void_p

        dll.PSOpenDeviceEx.argtypes = [ctypes.POINTER(HANDLE), c_int, c_int, c_int, c_int, c_int]
        dll.PSOpenDeviceEx.restype = c_int

        dll.PSAutoOpen.argtypes = [ctypes.POINTER(HANDLE), ctypes.POINTER(c_int), c_int, c_uint, c_int]
        dll.PSAutoOpen.restype = c_int

        dll.PSGetUSBDevNum.argtypes = [ctypes.POINTER(c_int)]
        dll.PSGetUSBDevNum.restype = c_int

        dll.PSGetUDiskNum.argtypes = [ctypes.POINTER(c_int)]
        dll.PSGetUDiskNum.restype = c_int

        dll.PSCloseDeviceEx.argtypes = [HANDLE]
        dll.PSCloseDeviceEx.restype = c_int

        dll.PSGetImage.argtypes = [HANDLE, c_int]
        dll.PSGetImage.restype = c_int

        dll.PSUpImage.argtypes = [HANDLE, c_int, ctypes.POINTER(c_ubyte), ctypes.POINTER(c_int)]
        dll.PSUpImage.restype = c_int

        dll.PSImgData2BMP.argtypes = [ctypes.POINTER(c_ubyte), c_char_p]
        dll.PSImgData2BMP.restype = c_int

        dll.PSErr2Str.argtypes = [c_int]
        dll.PSErr2Str.restype = ctypes.c_char_p

    # ===== Device Opening =====
    def open_device(self):
        """Try to open the fingerprint device."""
        usb_n = c_int(0)
        self.dll.PSGetUSBDevNum(byref(usb_n))
        udisks = c_int(0)
        self.dll.PSGetUDiskNum(byref(udisks))

        try:
            h, dtype = self._try_PSAutoOpen()
            self.handle = h
            return True
        except Exception:
            try:
                h = self._try_USB_explicit()
                self.handle = h
                return True
            except Exception:
                self.handle = self._try_COM_scan()
                return True

    def _try_PSAutoOpen(self):
        h = c_void_p()
        dtype = c_int(-1)
        rc = self.dll.PSAutoOpen(byref(h), byref(dtype), self.DEFAULT_ADDR, 0, 1)
        if rc == self.PS_OK and h:
            return h, dtype.value
        raise RuntimeError("PSAutoOpen failed")

    def _try_USB_explicit(self):
        for nPackageSize in (2, 3, 1, 0, 4):
            h = c_void_p()
            rc = self.dll.PSOpenDeviceEx(byref(h), self.DEVICE_USB, 1, 1, nPackageSize, 0)
            if rc == self.PS_OK and h:
                return h
        raise RuntimeError("USB open attempts failed.")

    def _try_COM_scan(self):
        for com in range(1, 31):
            for ibaud in (6, 12):
                h = c_void_p()
                rc = self.dll.PSOpenDeviceEx(byref(h), self.DEVICE_COM, com, ibaud, 2, 0)
                if rc == self.PS_OK and h:
                    return h
        raise RuntimeError("COM open attempts failed.")

    def close(self):
        """Close the fingerprint device."""
        if self.handle:
            self.dll.PSCloseDeviceEx(self.handle)
            self.handle = None

    # ===== Error Helper =====
    def _err_text(self, code: int) -> str:
        s = self.dll.PSErr2Str(code)
        return s.decode(errors="ignore") if s else f"Error 0x{code:02X}"

    # ===== Fingerprint Capture =====
    def read_fingerprint(self) -> bytes:
        """Read fingerprint from the device and return image bytes."""
        if not self.handle:
            raise RuntimeError("Device not opened")

        t0 = time.time()
        while True:
            rc = self.dll.PSGetImage(self.handle, self.DEFAULT_ADDR)
            if rc == self.PS_OK:
                break
            if rc == self.PS_NO_FINGER:
                if time.time() - t0 > self.TIMEOUT_SECONDS:
                    raise TimeoutError("No finger detected within timeout.")
                time.sleep(0.15)
                continue
            raise RuntimeError(f"PSGetImage failed: {self._err_text(rc)}")

        img_buf = (c_ubyte * self.IMAGE_BYTES)()
        img_len = c_int(self.IMAGE_BYTES)
        rc = self.dll.PSUpImage(self.handle, self.DEFAULT_ADDR, img_buf, byref(img_len))
        if rc != self.PS_OK:
            raise RuntimeError(f"PSUpImage failed: {self._err_text(rc)}")

        return bytes(bytearray(img_buf)[:img_len.value])

    def save_fingerprint(self, img_bytes: bytes):
        """Save fingerprint image to BMP file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(self.OUTPUT_DIR, f"fingerprint_{timestamp}.bmp")
        buf = (c_ubyte * len(img_bytes)).from_buffer_copy(img_bytes)
        rc = self.dll.PSImgData2BMP(buf, out_path.encode("utf-8"))
        if rc != self.PS_OK:
            raise RuntimeError(f"PSImgData2BMP failed: {self._err_text(rc)}")
        return out_path

    def send_images_to_server(self, img_bytes: bytes, server_url: str):
        """Send fingerprint image to a server via HTTP POST."""
        try:
            files = {"file": ("fingerprint.bmp", img_bytes, "application/octet-stream")}
            response = requests.post(server_url, files=files)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to send to server: {e}")


# Example usage


device = Device()