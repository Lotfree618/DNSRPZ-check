"""內存緩存存儲"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Store:
    """存儲探測結果的內存緩存（支持批量寫入）"""
    
    def __init__(self):
        self._results: Dict[str, Dict] = {}
        self._last_probe: Optional[str] = None
        self._update_count = 0
        # 待批量寫入的更新隊列
        self._pending_updates: List[Tuple[str, bool, Optional[str], str]] = []
    
    def update(self, domain: str, result: Dict):
        """
        更新網域探測結果到內存緩存
        注意：不會立即寫入 JSON，需調用 flush_pending 批量寫入
        """
        self._update_count += 1
        now = datetime.now(timezone.utc).isoformat()
        self._results[domain] = {
            **result,
            "last_probe_at": now
        }
        self._last_probe = now
        
        status = result.get("status", "")
        trace_status = result.get("trace_status")
        is_polluted = status == "已污染"
        
        logger.debug(f"[Store.update #{self._update_count}] 緩存 {domain}: status={status}, polluted={is_polluted}")
        
        # 加入待寫入隊列
        self._pending_updates.append((domain, is_polluted, trace_status, now))
    
    def flush_pending(self) -> int:
        """
        批量寫入所有待處理的更新到 domains.json
        返回寫入的記錄數
        """
        if not self._pending_updates:
            return 0
        
        from .domains import batch_update_polluted_and_trace
        
        count = len(self._pending_updates)
        updates = self._pending_updates.copy()
        self._pending_updates.clear()
        
        try:
            batch_update_polluted_and_trace(updates)
            logger.info(f"[Store.flush] 批量寫入 {count} 條記錄到 domains.json")
        except Exception as e:
            logger.error(f"[Store.flush] 批量寫入失敗: {e}", exc_info=True)
            # 寫入失敗時恢復隊列
            self._pending_updates.extend(updates)
            raise
        
        return count
    
    def pending_count(self) -> int:
        """獲取待寫入的記錄數"""
        return len(self._pending_updates)
    
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
