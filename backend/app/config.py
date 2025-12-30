from typing import List, Dict

# 超时设置
DNS_TIMEOUT = 2.0  # 秒 (增加一点超时时间)
DNS_LIFETIME = 4.0  # 秒

# Resolver 定义
RESOLVERS: Dict[str, str] = {
    "google": "8.8.8.8",
    "cloudflare": "1.1.1.1",
    "hinet": "168.95.1.1",     # 中华电信
    "so-net": "61.64.127.1",   # So-net (Added from test.py)
    "quad101": "101.101.101.101" # TWNIC
}

# 疑似拦截/污染的 CIDR (宽范围)
SUSPICIOUS_NETWORKS = [
    "0.0.0.0/8",
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
]

# 明确的拦截页/保留 IP (精确匹配)
# 参考 test.py
KNOWN_BLOCK_IPS = {
    "182.173.0.181", # 台湾 165 反诈骗警示页面
    "104.18.0.0",    # 某些配置错误/阻断 (Cloudflare 网段但被用作阻断?) - 保留自 test.py
    "0.0.0.0",
    "127.0.0.1"
}
