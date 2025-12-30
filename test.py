import dns.resolver
import sys
import time

# --- 配置区域 ---

# 1. 权威 DNS (作为基准对照)
BASELINE_DNS = {
    "Google": "8.8.8.8",
    "Cloudflare": "1.1.1.1"
}

# 2. 台湾主要 ISP DNS 列表
TW_DNS_LIST = [
    {"provider": "HiNet (中华电信)", "ip": "168.95.1.1", "note": "全台最大/最严"},
    {"provider": "HiNet (次要)",     "ip": "168.95.192.1", "note": "备用节点"},
    {"provider": "Seednet (远传)",   "ip": "139.175.55.244", "note": "第二大ISP"},
    {"provider": "TW Mobile (台哥大)","ip": "211.78.130.2", "note": "主要移动宽带"},
    {"provider": "So-net",          "ip": "61.64.127.1", "note": "宽带服务商"},
    {"provider": "TWNIC (Quad 101)","ip": "101.101.101.101", "note": "台湾互联网络中心"},
    {"provider": "TANet (学术网络)", "ip": "163.28.112.1", "note": "教育部/学术网"},
]

# 3. 已知的封锁/警示页面 IP (黑名单)
# 如果解析结果包含这些 IP，直接判定为“已封锁”
BLOCK_PAGE_IPS = {
    "182.173.0.181",  # 台湾 165 反诈骗警示页面 (最常见)
    "104.18.0.0",     # 某些错误配置的阻断
    "127.0.0.1",      # 本地回环 (有时候用于阻断)
    "0.0.0.0"         # 空路由 (有时候用于阻断)
}

# --- 颜色代码 ---
class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# --- 核心函数 ---

def resolve_domain(domain, server_ip, timeout=3):
    """向指定 DNS 发起查询"""
    resolver = dns.resolver.Resolver()
    resolver.nameservers = [server_ip]
    resolver.lifetime = timeout
    resolver.timeout = timeout

    try:
        answers = resolver.resolve(domain, 'A')
        return {
            "status": "ok",
            "ips": sorted([r.to_text() for r in answers])
        }
    except dns.resolver.NXDOMAIN:
        return {"status": "nxdomain", "ips": []}
    except dns.resolver.Timeout:
        return {"status": "timeout", "ips": []}
    except Exception as e:
        return {"status": "error", "msg": str(e), "ips": []}

def main(domain):
    print(f"\n🔍 正在针对域名 {Color.BOLD}{domain}{Color.ENDC} 进行全台 DNS 污染检测...\n")
    print("-" * 70)

    # 1. 获取权威基准 (BaseLine)
    baseline_ips = set()
    print(f"[{Color.BLUE}基准{Color.ENDC}] 正在获取权威解析 (Google & Cloudflare)...")
    
    for name, ip in BASELINE_DNS.items():
        res = resolve_domain(domain, ip)
        if res['status'] == 'ok':
            for addr in res['ips']:
                baseline_ips.add(addr)
            print(f"   ✅ {name:<12} -> {res['ips']}")
        else:
            print(f"   ❌ {name:<12} -> 查询失败 ({res.get('status')})")

    if not baseline_ips:
        print(f"\n{Color.RED}⛔ 严重错误：无法从 Google/Cloudflare 获取任何解析结果。{Color.ENDC}")
        print("可能是域名本身不存在，或你的网络无法访问国际 DNS。")
        return

    print(f"   📝 权威 IP 集合: {Color.BLUE}{baseline_ips}{Color.ENDC}")
    print("-" * 70)
    print(f"{'DNS 提供商':<20} | {'IP':<16} | {'状态':<10} | {'解析结果 / 备注'}")
    print("-" * 70)

    # 2. 遍历台湾 DNS 列表
    for dns_info in TW_DNS_LIST:
        provider = dns_info['provider']
        server_ip = dns_info['ip']
        
        res = resolve_domain(domain, server_ip, timeout=4)
        result_ips = set(res['ips'])
        
        # --- 判定逻辑 ---
        status_text = ""
        ips_display = ""

        if res['status'] == 'timeout':
            status_text = f"{Color.YELLOW}超时{Color.ENDC}"
            ips_display = "网络不可达或UDP被阻断"
        
        elif res['status'] == 'nxdomain':
            # 如果权威有结果，这里却是 NXDOMAIN，说明被故意屏蔽了
            status_text = f"{Color.RED}被阻断{Color.ENDC}"
            ips_display = "NXDOMAIN (域名不存在)"
            
        elif res['status'] == 'ok':
            ips_display = str(res['ips'])
            
            # 检测 A: 是否命中了反诈黑名单 IP
            if not result_ips.isdisjoint(BLOCK_PAGE_IPS):
                status_text = f"{Color.RED}⛔ 已封锁{Color.ENDC}"
                ips_display = f"{Color.RED}{ips_display} (反诈警示页){Color.ENDC}"
            
            # 检测 B: 结果是否完全包含在权威集合里
            elif result_ips.issubset(baseline_ips):
                 status_text = f"{Color.GREEN}✅ 正常{Color.ENDC}"
            
            # 检测 C: 结果有效但 IP 不同 (可能是 CDN 或 隐蔽劫持)
            else:
                status_text = f"{Color.YELLOW}⚠️ 差异{Color.ENDC}"
                ips_display += " (可能是CDN分流)"
        
        else:
            status_text = f"{Color.RED}错误{Color.ENDC}"
            ips_display = res.get('msg', 'Unknown Error')

        # 打印行
        print(f"{provider:<20} | {server_ip:<16} | {status_text:<19} | {ips_display}")

    print("-" * 70)
    print(f"{Color.YELLOW}提示：状态为'差异'不代表一定被封锁，大型网站(如Google/FB)在不同地区IP通常不同。{Color.ENDC}")
    print(f"{Color.RED}提示：如果全部显示'超时'，说明你的本地网络环境禁止了向特定IP发送UDP DNS包。{Color.ENDC}")

if __name__ == "__main__":
    target = ""
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        # 默认测试一个已知的被封锁域名，或者你可以输入 check.wellstsai.com 
        # (check.wellstsai.com 作为一个工具站本身没被封，但可以用来测试解析)
        raw_input = input("请输入域名 (例如 google.com): ").strip()
        target = raw_input if raw_input else "google.com"
    
    main(target)