"""域名組管理 - 存儲跳轉鏈上互相關聯的域名"""
import json
from pathlib import Path
from typing import Dict, Set, List, Optional
from filelock import FileLock
from .domains import extract_root_domain

# 域名組 JSON 文件路徑
DOMAIN_GROUPS_FILE = Path(__file__).parent.parent / "domain_groups.json"
DOMAIN_GROUPS_LOCK = Path(__file__).parent.parent / "domain_groups.json.lock"


def _read_groups() -> Dict[str, Set[str]]:
    """讀取域名組數據"""
    if not DOMAIN_GROUPS_FILE.exists():
        return {}
    try:
        with open(DOMAIN_GROUPS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 將列表轉換為集合
            return {k: set(v) for k, v in data.items()}
    except Exception:
        return {}


def _write_groups(groups: Dict[str, Set[str]]):
    """寫入域名組數據（帶文件鎖）"""
    lock = FileLock(str(DOMAIN_GROUPS_LOCK), timeout=5)
    try:
        with lock:
            # 將集合轉換為列表以便 JSON 序列化
            data = {k: sorted(v) for k, v in groups.items()}
            with open(DOMAIN_GROUPS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"寫入域名組失敗: {e}")


def update_domain_group(domains_in_chain: List[str]):
    """
    更新域名組：將跳轉鏈上的所有域名歸入同一組
    
    Args:
        domains_in_chain: 跳轉鏈上的域名列表（已去 www）
    """
    if not domains_in_chain or len(domains_in_chain) < 2:
        return
    
    # 去重並收斂 www
    normalized = set()
    for d in domains_in_chain:
        root = extract_root_domain(d)
        if root:
            normalized.add(root)
    
    if len(normalized) < 2:
        return
    
    groups = _read_groups()
    
    # 找出這些域名已有的所有組成員
    merged_set = set(normalized)
    for domain in normalized:
        if domain in groups:
            merged_set.update(groups[domain])
    
    # 擴展：檢查 merged_set 中每個域名是否有更多關聯
    expanded = True
    while expanded:
        expanded = False
        for domain in list(merged_set):
            if domain in groups:
                before = len(merged_set)
                merged_set.update(groups[domain])
                if len(merged_set) > before:
                    expanded = True
    
    # 更新所有相關域名的組
    for domain in merged_set:
        # 每個域名的相關域名 = 組內除自己以外的所有域名
        groups[domain] = merged_set - {domain}
    
    _write_groups(groups)


def get_related_domains(domain: str) -> List[str]:
    """
    獲取某個域名的相關域名列表
    
    Args:
        domain: 要查詢的域名
        
    Returns:
        相關域名列表（不包含自己）
    """
    root = extract_root_domain(domain)
    if not root:
        return []
    
    groups = _read_groups()
    related = groups.get(root, set())
    return sorted(related)


def extract_domains_from_trace(current_domain: str, redirect_trace: Dict) -> List[str]:
    """
    從跳轉追蹤結果中提取所有域名
    
    Args:
        current_domain: 當前被探測的域名
        redirect_trace: 跳轉追蹤結果
        
    Returns:
        跳轉鏈上所有域名列表
    """
    from urllib.parse import urlparse
    
    domains = []
    
    # 添加當前域名
    root = extract_root_domain(current_domain)
    if root:
        domains.append(root)
    
    # 從跳轉鏈提取域名
    if redirect_trace and redirect_trace.get("chain"):
        for step in redirect_trace["chain"]:
            url = step.get("url", "")
            if url:
                try:
                    parsed = urlparse(url)
                    hostname = parsed.hostname
                    if hostname:
                        root = extract_root_domain(hostname)
                        if root:
                            domains.append(root)
                except Exception:
                    pass
    
    # 添加最終域名
    if redirect_trace and redirect_trace.get("final_domain"):
        root = extract_root_domain(redirect_trace["final_domain"])
        if root:
            domains.append(root)
    
    return domains
