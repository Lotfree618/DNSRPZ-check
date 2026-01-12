"""內存緩存存儲"""
from datetime import datetime, timezone
from typing import Dict, Optional


class Store:
    """存儲探測結果的內存緩存"""
    
    def __init__(self):
        self._results: Dict[str, Dict] = {}
        self._last_probe: Optional[str] = None
    
    def update(self, domain: str, result: Dict):
        """更新網域探測結果，並同步 polluted 狀態到 JSON"""
        now = datetime.now(timezone.utc).isoformat()
        self._results[domain] = {
            **result,
            "last_probe_at": now
        }
        self._last_probe = now
        
        # 同步 polluted 狀態和檢測時間到 domains.json
        from .domains import update_polluted
        status = result.get("status", "")
        # 非正常狀態視為污染
        is_polluted = status not in ("正常", "空解析")
        update_polluted(domain, is_polluted, now)
    
    def get_all(self) -> Dict[str, Dict]:
        """获取所有域名结果"""
        return self._results.copy()
    
    def get(self, domain: str) -> Optional[Dict]:
        """获取单个域名结果"""
        return self._results.get(domain)
    
    def get_last_probe_time(self) -> Optional[str]:
        """获取最后探测时间"""
        return self._last_probe
    
    def clear_stale(self, current_domains: set):
        """清理不在列表中的域名"""
        stale = set(self._results.keys()) - current_domains
        for d in stale:
            del self._results[d]


# 全局存储实例
store = Store()
