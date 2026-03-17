import os
import sys
from pathlib import Path

def get_user_data_dir() -> Path:
    """Return the user data directory for the application, ensuring it exists."""
    if sys.platform == "win32":
        # Windows: %APPDATA%\HappySmartLightTool
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/HappySmartLightTool
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux: ~/.local/share/HappySmartLightTool
        base = Path.home() / ".local" / "share"
    
    data_dir = base / "HappySmartLightTool"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent
    except Exception:
        base_path = Path(__file__).parent.parent
    
    return base_path / relative_path
