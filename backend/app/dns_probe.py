import asyncio
import re
from urllib.parse import urlparse
from typing import Optional
import dns.resolver
import dns.asyncresolver
import dns.rdatatype
import dns.exception


def normalize_domain(target: str) -> Optional[str]:
    """
    将用户输入（域名或URL）归一化为hostname
    返回None表示无效输入
    """
    target = target.strip()
    if not target:
        return None

    # URL特征检测
    if "://" in target or "/" in target or "?" in target or "#" in target:
        if not target.startswith(("http://", "https://")):
            target = "http://" + target
        try:
            parsed = urlparse(target)
            hostname = parsed.hostname
            if not hostname:
                return None
            target = hostname
        except Exception:
            return None

    # 转小写、去尾点
    target = target.lower().rstrip(".")

    # 验证域名格式
    if not target or " " in target or len(target) > 253:
        return None

    # IDN转punycode
    try:
        target = target.encode("idna").decode("ascii")
    except Exception:
        pass

    return target


async def query_dns(domain: str, resolver_ip: str, timeout: float) -> dict:
    """
    查询单个DNS服务器的A/AAAA记录
    返回: {"status": "ok"|"nxdomain"|"timeout"|"error", "ips": [...], "msg": "..."}
    """
    resolver = dns.asyncresolver.Resolver()
    resolver.nameservers = [resolver_ip]
    resolver.lifetime = timeout

    ips = []
    # 查询A记录
    for rdtype in [dns.rdatatype.A, dns.rdatatype.AAAA]:
        try:
            answer = await resolver.resolve(domain, rdtype)
            for rdata in answer:
                ips.append(rdata.to_text())
        except dns.resolver.NXDOMAIN:
            return {"status": "nxdomain", "ips": [], "msg": None}
        except dns.resolver.NoAnswer:
            pass  # 该类型无记录，继续
        except dns.exception.Timeout:
            return {"status": "timeout", "ips": [], "msg": "查询超时"}
        except Exception as e:
            return {"status": "error", "ips": [], "msg": str(e)}

    return {"status": "ok", "ips": ips, "msg": None}


async def probe_all(domain: str, baseline_resolvers: list, tw_resolvers: list, 
                    baseline_timeout: float, tw_timeout: float) -> dict:
    """
    并发查询所有DNS服务器
    """
    tasks = []
    
    # 基准DNS
    for r in baseline_resolvers:
        tasks.append(query_dns(domain, r["ip"], baseline_timeout))
    
    # 台湾DNS
    for r in tw_resolvers:
        tasks.append(query_dns(domain, r["ip"], tw_timeout))
    
    results = await asyncio.gather(*tasks)
    
    baseline_results = []
    for i, r in enumerate(baseline_resolvers):
        res = results[i]
        baseline_results.append({
            "name": r["name"],
            "ip": r["ip"],
            **res
        })
    
    tw_results = []
    offset = len(baseline_resolvers)
    for i, r in enumerate(tw_resolvers):
        res = results[offset + i]
        tw_results.append({
            "name": r["name"],
            "ip": r["ip"],
            **res
        })
    
    return {
        "baseline": baseline_results,
        "tw": tw_results
    }
