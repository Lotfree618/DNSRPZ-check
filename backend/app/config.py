# DNS配置
BASELINE_RESOLVERS = [
    {"name": "Google DNS", "ip": "8.8.8.8"},
    {"name": "Cloudflare DNS", "ip": "1.1.1.1"},
]

TW_RESOLVERS = [
    {"name": "HiNet（中华电信）", "ip": "168.95.1.1"},
    {"name": "TWNIC Quad101", "ip": "101.101.101.101"},
]

# 黑名单IP（台湾RPZ常见封锁页）
BLOCK_PAGE_IPS = frozenset([
    "182.173.0.181",
    "104.18.0.0",
    "127.0.0.1",
    "0.0.0.0",
])

# 超时设置（秒）
BASELINE_TIMEOUT = 3.0
TW_TIMEOUT = 4.0
