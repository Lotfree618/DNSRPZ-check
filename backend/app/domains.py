"""域名列表读取与规范化"""
import re
from urllib.parse import urlparse
from pathlib import Path
from typing import List
from . import config


def normalize_domain(raw: str) -> str:
    """规范化域名/URL 输入"""
    s = raw.strip()
    if not s:
        return ""
    
    # 若含 URL 特征，解析提取 hostname
    if "://" in s or "/" in s or "?" in s or "#" in s:
        if "://" not in s:
            s = "http://" + s
        try:
            parsed = urlparse(s)
            s = parsed.hostname or ""
        except Exception:
            return ""
    
    # 转小写，去掉尾部点
    s = s.lower().rstrip(".")
    
    # 简单校验
    if not s or " " in s or len(s) > 253:
        return ""
    
    return s


def load_domains() -> List[str]:
    """从 Domains.txt 加载域名列表"""
    path = Path(config.DOMAINS_FILE)
    if not path.exists():
        return []
    
    domains = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith("#"):
                    continue
                domain = normalize_domain(line)
                if domain:
                    domains.add(domain)
    except Exception:
        pass
    
    return sorted(domains)
