import sys
import base64
import json
from pathlib import Path

from utils.paths import get_user_data_dir

# Khởi tạo Windows DPAPI nếu đang chạy trên Windows
if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_byte))]

    def _dpapi_encrypt(data: bytes) -> bytes:
        crypt32 = ctypes.windll.crypt32
        
        blob_in = DATA_BLOB()
        blob_in.cbData = len(data)
        # Create a mutable byte buffer
        buf = ctypes.create_string_buffer(data)
        blob_in.pbData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))
        
        blob_out = DATA_BLOB()
        
        # CryptProtectData(pDataIn, szDataDescr, pOptionalEntropy, pvReserved, pPromptStruct, dwFlags, pDataOut)
        # 0x1 = CRYPTPROTECT_UI_FORBIDDEN (không hiện thông báo UI)
        if crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out)):
            result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            kernel32 = ctypes.windll.kernel32
            kernel32.LocalFree(blob_out.pbData)
            return result
        else:
            raise Exception("Mã khóa API Key bằng Windows DPAPI thất bại!")

    def _dpapi_decrypt(data: bytes) -> bytes:
        crypt32 = ctypes.windll.crypt32
        
        blob_in = DATA_BLOB()
        blob_in.cbData = len(data)
        buf = ctypes.create_string_buffer(data)
        blob_in.pbData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))
        
        blob_out = DATA_BLOB()
        
        # CryptUnprotectData(pDataIn, ppszDataDescr, pOptionalEntropy, pvReserved, pPromptStruct, dwFlags, pDataOut)
        if crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out)):
            result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            kernel32 = ctypes.windll.kernel32
            kernel32.LocalFree(blob_out.pbData)
            return result
        else:
            raise Exception("Giải mã API Key bằng DPAPI thất bại! (Lỗi khác user hoặc máy)")

else:
    # Trên macOS/Linux gọi fallback đơn giản (App hiện tại chuyên Windows)
    def _dpapi_encrypt(data: bytes) -> bytes:
        return base64.b64encode(data)
    def _dpapi_decrypt(data: bytes) -> bytes:
        return base64.b64decode(data)


def save_api_key(service: str, key: str):
    """
    Mã hóa cục bộ và lưu trữ API Key vào config_keys.json. 
    Chỉ tài khoản người dùng hiện tại trên máy này mới giải mã được.
    """
    keys_file = get_user_data_dir() / "config_keys.json"
    
    data = {}
    if keys_file.exists():
        try:
            data = json.loads(keys_file.read_text("utf-8"))
        except:
            pass
            
    if not key or not key.strip():
        if service in data:
            del data[service]
    else:
        encrypted_bytes = _dpapi_encrypt(key.encode("utf-8"))
        # Base64 bọc lại cục byte đã bị mã hoá sinh ra để ghi file text JSON an toàn
        data[service] = base64.b64encode(encrypted_bytes).decode("utf-8")
        
    keys_file.write_text(json.dumps(data, indent=4), "utf-8")

def get_api_key(service: str) -> str:
    """Lấy và tự động giải mã API Key theo nhà cung cấp"""
    keys_file = get_user_data_dir() / "config_keys.json"
    if not keys_file.exists():
        return ""
        
    try:
        data = json.loads(keys_file.read_text("utf-8"))
        if service not in data:
            return ""
            
        encrypted_bytes = base64.b64decode(data[service])
        decrypted_bytes = _dpapi_decrypt(encrypted_bytes)
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        print(f"Error decrypting api key for {service}: {e}")
        return ""
