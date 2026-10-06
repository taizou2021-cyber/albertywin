import sys
from pathlib import Path

# 將專案根目錄加入 Python 搜尋路徑以正常載入 main, database, models 等模組
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from main import app
