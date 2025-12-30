from typing import List, Dict

# 超时设置
DNS_TIMEOUT = 1.5  # 秒
DNS_LIFETIME = 3.0  # 秒

# Resolver 定义
RESOLVERS: Dict[str, str] = {
    "google": "8.8.8.8",
    "cloudflare": "1.1.1.1",
    "hinet": "168.95.1.1",     # 中华电信
    "twm": "211.78.130.2",     # 台湾大哥大
    "fet": "139.175.55.244",   # 远传电信
    "quad101": "101.101.101.101" # TWNIC
}

# 疑似拦截/污染的 IP 段 (不可信结果)
SUSPICIOUS_IPS = [
    "0.0.0.0/8",
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    # "100.64.0.0/10" # CGNAT 视情况启用，这里先不列入，以免误判
]
