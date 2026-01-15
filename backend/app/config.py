"""配置文件"""
import os
from pathlib import Path

# 基准 DNS 解析器
BASELINE_RESOLVERS = {
    "8.8.8.8": "Google DNS",
    "1.1.1.1": "Cloudflare DNS",
}

# 台湾 DNS 解析器
TW_RESOLVERS = {
    "168.95.1.1": "中华电信",
    "101.101.101.101": "Twnic",
}

# 黑名单 IP（命中即判定为已封锁）
BLOCK_PAGE_IPS = {
    "182.173.0.181",  # 台湾 165 反诈警示页
    "127.0.0.1",
    "0.0.0.0",
}

# 超时配置（秒）
BASELINE_TIMEOUT = 3
TW_TIMEOUT = 4

# 探测间隔（秒）
PROBE_INTERVAL = 300

# 异常域名探测间隔（秒），默认24小时
ABNORMAL_PROBE_INTERVAL = 300

# 并发限制
MAX_CONCURRENCY = 50

# HTTP 重定向追踪最大跳转次数
MAX_REDIRECTS = 10

# Domains.txt 路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DOMAINS_FILE = os.environ.get("DOMAINS_FILE", str(BASE_DIR / "Domains.txt"))

# 日志配置（DEBUG=调试模式，WARNING=安静模式）
import logging
LOG_LEVEL = logging.WARNING
LOG_FILE = "probe_debug.log"
