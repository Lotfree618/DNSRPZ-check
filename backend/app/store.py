"""内存缓存存储"""
from datetime import datetime, timezone
from typing import Dict, Optional


class Store:
    """存储探测结果的内存缓存"""
    
    def __init__(self):
        self._results: Dict[str, Dict] = {}
        self._last_probe: Optional[str] = None
    
    def update(self, domain: str, result: Dict):
        """更新域名探测结果"""
        now = datetime.now(timezone.utc).isoformat()
        self._results[domain] = {
            **result,
            "last_probe_at": now
        }
        self._last_probe = now
    
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
