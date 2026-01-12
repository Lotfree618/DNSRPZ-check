"""網域列表讀取與管理"""
import json
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from pathlib import Path
from typing import List, Dict, Optional
from filelock import FileLock
from . import config

# 東八區時區
TZ_UTC8 = timezone(timedelta(hours=8))

# domains.json 路徑
DOMAINS_JSON = Path(__file__).resolve().parent.parent / "domains.json"
DOMAINS_LOCK = Path(__file__).resolve().parent.parent / "domains.json.lock"


def normalize_domain(raw: str) -> str:
    """規範化網域/URL 輸入，提取純網域名稱"""
    s = raw.strip()
    if not s:
        return ""
    
    # 若含 URL 特徵，解析提取 hostname
    if "://" in s or "/" in s or "?" in s or "#" in s:
        if "://" not in s:
            s = "http://" + s
        try:
            parsed = urlparse(s)
            s = parsed.hostname or ""
        except Exception:
            return ""
    
    # 轉小寫，去掉尾部點
    s = s.lower().rstrip(".")
    
    # 簡單校驗
    if not s or " " in s or len(s) > 253:
        return ""
    
    return s


def _read_domains() -> Dict[str, Dict]:
    """讀取 domains.json"""
    if not DOMAINS_JSON.exists():
        return {}
    try:
        with open(DOMAINS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_domains(data: Dict[str, Dict]):
    """寫入 domains.json（帶文件鎖）"""
    lock = FileLock(str(DOMAINS_LOCK), timeout=5)
    with lock:
        with open(DOMAINS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_domains() -> List[str]:
    """載入網域列表（僅網域名稱）"""
    data = _read_domains()
    return sorted(data.keys())


def get_all_domains() -> Dict[str, Dict]:
    """獲取所有網域及其屬性"""
    return _read_domains()


def get_domain(domain: str) -> Optional[Dict]:
    """獲取單個網域屬性"""
    data = _read_domains()
    return data.get(domain)


def add_domain(domain: str, note: str = "") -> tuple[bool, str]:
    """
    新增網域
    返回 (成功與否, 訊息)
    """
    normalized = normalize_domain(domain)
    if not normalized:
        return False, "無效的網域格式"
    
    data = _read_domains()
    if normalized in data:
        return False, "網域已存在"
    
    now = datetime.now(TZ_UTC8).isoformat()
    data[normalized] = {
        "reported": False,
        "polluted": False,
        "note": note,
        "created_at": now
    }
    _write_domains(data)
    return True, normalized


def update_domain(old_domain: str, new_domain: str) -> tuple[bool, str]:
    """
    修改網域名稱
    返回 (成功與否, 訊息)
    """
    normalized_new = normalize_domain(new_domain)
    if not normalized_new:
        return False, "無效的網域格式"
    
    data = _read_domains()
    if old_domain not in data:
        return False, "原網域不存在"
    if normalized_new in data and normalized_new != old_domain:
        return False, "新網域已存在"
    
    # 保留原屬性，但重置 polluted
    old_info = data.pop(old_domain)
    old_info["polluted"] = False  # 新網域需重新檢測
    data[normalized_new] = old_info
    _write_domains(data)
    return True, normalized_new


def delete_domain(domain: str) -> bool:
    """刪除單個網域"""
    data = _read_domains()
    if domain not in data:
        return False
    del data[domain]
    _write_domains(data)
    return True


def batch_delete_domains(domains: List[str]) -> int:
    """批量刪除網域，返回實際刪除數量"""
    data = _read_domains()
    deleted = 0
    for d in domains:
        if d in data:
            del data[d]
            deleted += 1
    if deleted > 0:
        _write_domains(data)
    return deleted


def update_note(domain: str, note: str) -> bool:
    """更新網域備註"""
    data = _read_domains()
    if domain not in data:
        return False
    data[domain]["note"] = note
    _write_domains(data)
    return True


def toggle_reported(domain: str) -> Optional[bool]:
    """
    切換已上報狀態
    返回新狀態，若網域不存在則返回 None
    """
    data = _read_domains()
    if domain not in data:
        return None
    data[domain]["reported"] = not data[domain]["reported"]
    _write_domains(data)
    return data[domain]["reported"]


def update_polluted(domain: str, polluted: bool, last_probe_at: str = None):
    """更新污染狀態和檢測時間（供探測器調用）"""
    data = _read_domains()
    if domain in data:
        data[domain]["polluted"] = polluted
        if last_probe_at:
            data[domain]["last_probe_at"] = last_probe_at
        _write_domains(data)


def import_from_file(filepath: str) -> tuple[int, int]:
    """
    從文件批量導入網域
    返回 (成功數, 跳過數)
    """
    data = _read_domains()
    added = 0
    skipped = 0
    now = datetime.now(TZ_UTC8).isoformat()
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                normalized = normalize_domain(line)
                if not normalized:
                    skipped += 1
                    continue
                if normalized in data:
                    skipped += 1
                    continue
                data[normalized] = {
                    "reported": False,
                    "polluted": False,
                    "note": "",
                    "created_at": now
                }
                added += 1
    except Exception:
        pass
    
    if added > 0:
        _write_domains(data)
    
    return added, skipped
