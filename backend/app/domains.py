"""網域列表讀取與管理"""
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from pathlib import Path
from typing import List, Dict, Optional
from filelock import FileLock

# 東八區時區
TZ_UTC8 = timezone(timedelta(hours=8))

# domains.json 路徑
DOMAINS_JSON = Path(__file__).resolve().parent.parent / "domains.json"
DOMAINS_LOCK = Path(__file__).resolve().parent.parent / "domains.json.lock"


def normalize_domain(raw: str) -> str:
    """規範化網域/URL 輸入，提取純網域名稱"""
    import re
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
    
    # 域名格式校驗
    if not s or len(s) > 253:
        return ""
    
    # 必須包含至少一個點（排除 localhost 等）
    if "." not in s:
        return ""
    
    # 只允許合法字符：字母、數字、連字號、點
    if not re.match(r'^[a-z0-9]([a-z0-9\-\.]*[a-z0-9])?$', s):
        return ""
    
    # 檢查每個標籤（點分隔）
    labels = s.split(".")
    for label in labels:
        # 標籤長度限制
        if not label or len(label) > 63:
            return ""
        # 標籤不能以連字號開頭或結尾
        if label.startswith("-") or label.endswith("-"):
            return ""
        # 標籤不能只包含數字（頂級域名限制）
        # 注意：這裡不限制中間標籤
    
    return s


def extract_root_domain(domain: str) -> str:
    """
    從域名中提取根域名
    例：www.example.com -> example.com
    僅處理 www 前綴，其他子域名保持不變
    """
    if not domain:
        return domain
    parts = domain.lower().split(".")
    if len(parts) > 2 and parts[0] == "www":
        return ".".join(parts[1:])
    return domain


def normalize_www_domain(domain: str) -> str:
    """
    將 www 子域名收斂到根域名後進行規範化
    用於自動收錄域名時使用
    """
    if not domain:
        return ""
    root = extract_root_domain(domain)
    return normalize_domain(root)


def auto_add_domain(domain: str, note: str = "自動收錄") -> bool:
    """
    自動收錄域名（用於跳轉追蹤發現的新域名）
    如果 www 子域名則收斂到根域名
    返回是否成功新增
    """
    normalized = normalize_www_domain(domain)
    if not normalized:
        return False
    
    data = _read_domains()
    if normalized in data:
        return False
    
    now = datetime.now(TZ_UTC8).isoformat()
    data[normalized] = {
        "reported": False,
        "polluted": False,
        "note": note,
        "created_at": now
    }
    _write_domains(data)
    return True


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


def batch_set_reported(domains: List[str], reported: bool) -> int:
    """
    批量設置上報狀態
    返回實際更新的數量
    """
    data = _read_domains()
    updated = 0
    for d in domains:
        if d in data:
            data[d]["reported"] = reported
            updated += 1
    if updated > 0:
        _write_domains(data)
    return updated

def update_polluted_and_trace(domain: str, polluted: bool, trace_status: str = None, last_probe_at: str = None):
    """更新污染狀態、追蹤狀態和檢測時間（供探測器調用）"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        data = _read_domains()
        if domain in data:
            data[domain]["polluted"] = polluted
            if trace_status:
                data[domain]["trace_status"] = trace_status
            if last_probe_at:
                data[domain]["last_probe_at"] = last_probe_at
            _write_domains(data)
            logger.debug(f"[domains] 已更新 {domain}: polluted={polluted}, trace_status={trace_status}, 總域名數={len(data)}")
        else:
            logger.warning(f"[domains] 域名不存在，無法更新: {domain}")
    except Exception as e:
        logger.error(f"[domains] 更新失敗 {domain}: {e}", exc_info=True)
        raise


def batch_update_polluted_and_trace(updates: list):
    """
    批量更新多個域名的污染狀態、追蹤狀態和檢測時間
    
    Args:
        updates: [(domain, polluted, trace_status, last_probe_at), ...]
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not updates:
        return
    
    try:
        data = _read_domains()
        updated_count = 0
        
        for domain, polluted, trace_status, last_probe_at in updates:
            if domain in data:
                data[domain]["polluted"] = polluted
                if trace_status:
                    data[domain]["trace_status"] = trace_status
                if last_probe_at:
                    data[domain]["last_probe_at"] = last_probe_at
                updated_count += 1
            else:
                logger.warning(f"[domains] 域名不存在，跳過: {domain}")
        
        if updated_count > 0:
            _write_domains(data)
            logger.debug(f"[domains] 批量更新完成: {updated_count}/{len(updates)} 條記錄")
    except Exception as e:
        logger.error(f"[domains] 批量更新失敗: {e}", exc_info=True)
        raise


# 保留舊函數名以保持兼容性
def update_polluted(domain: str, polluted: bool, last_probe_at: str = None):
    """更新污染狀態和檢測時間（供探測器調用）- 已棄用，使用 update_polluted_and_trace"""
    update_polluted_and_trace(domain, polluted, None, last_probe_at)


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
