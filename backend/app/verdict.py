from typing import List, Dict, Set
import ipaddress
from app.schemas import ResolverResult, BaselineInfo, ComparisonInfo, ConclusionInfo, MismatchDetail
from app.config import SUSPICIOUS_IPS

def is_suspicious_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        for net in SUSPICIOUS_IPS:
            if ip in ipaddress.ip_network(net):
                return True
        return False
    except ValueError:
        return False

def analyze_results(results: Dict[str, ResolverResult]) -> (BaselineInfo, ComparisonInfo, ConclusionInfo):
    # 1. Establish Baseline (Google 8.8.8.8 vs Cloudflare 1.1.1.1)
    # 简化：如果两个都有结果且非空，取交集；或者只要 Status 都是 NOERROR 且都有 IP
    
    baseline_resolvers = ["google", "cloudflare"]
    baseline_a_sets = []
    baseline_aaaa_sets = []
    
    # 收集 baseline 结果
    for b_res in baseline_resolvers:
        if b_res in results:
            # Set of IPs for set comparison
            baseline_a_sets.append(set(results[b_res].A.answers))
            baseline_aaaa_sets.append(set(results[b_res].AAAA.answers))
    
    # 判断 Baseline 是否一致
    # 简单策略：如果两个都成功，看是否有交集（Load Balance 可能导致 IP 不同，但一般会有交集或同属一个 ASN，这里简单看交集或空）
    # 如果其中一个超时或失败，Baseline 降级为取另一个
    
    final_baseline_a = set()
    final_baseline_aaaa = set()
    baseline_agreed = False
    
    if len(baseline_a_sets) == 2:
        # 两个都有结果
        set1, set2 = baseline_a_sets[0], baseline_a_sets[1]
        
        # 只要有一个是空集合（无 A 记录），另一个也是空，或者两者有交集，算一致
        if (not set1 and not set2) or (set1 & set2):
            baseline_agreed = True
            final_baseline_a = set1 & set2 if set1 and set2 else (set1 or set2) # 取交集或者非空那个
        # 特殊情况：CDN 导致 IP 完全不同，但其实都没问题。 MVP 先按不一致处理，标记 UNCERTAIN
        elif set1 and set2 and not (set1 & set2):
             # 尝试合并作为宽容基准? 暂时 strict
             baseline_agreed = False
        else:
            # 一个有 IP 一个没 IP (NXDOMAIN vs NOERROR) -> 不一致
            baseline_agreed = False
    elif len(baseline_a_sets) == 1:
        # 只有一个 baseline 有效 (另一个超时)
        baseline_agreed = True # 降级
        final_baseline_a = baseline_a_sets[0]
    else:
        # 都挂了
        baseline_agreed = False

    # AAAA 同理
    # 简化：Baseline 判定主要看 A 记录，AAAA 辅助。
    
    reference = {
        "A": list(final_baseline_a),
        "AAAA": list() # 暂不作为强基准
    }
    
    baseline_info = BaselineInfo(
        agreed=baseline_agreed,
        types_checked=["A", "AAAA"],
        reference=reference
    )
    
    # 2. Comparison with TW Resolvers
    mismatches = []
    suspicious_flags = [] # (resolver, reason)
    
    tw_resolvers = ["hinet", "twm", "fet", "quad101"]
    
    for res_name in tw_resolvers:
        if res_name not in results:
            continue
            
        res_result = results[res_name]
        
        # Check A records
        res_a_set = set(res_result.A.answers)
        
        # R1: NXDOMAIN/SERVFAIL vs Baseline NOERROR
        if results[res_name].A.status != "NOERROR" and final_baseline_a:
             mismatches.append(MismatchDetail(resolver=res_name, type="A", reason=f"Status {results[res_name].A.status} but baseline has IPs"))
             suspicious_flags.append(f"{res_name} 返回 {results[res_name].A.status}，但基准有 A 记录")

        # R2: Suspicious IPs
        for ip in res_result.A.answers:
            if is_suspicious_ip(ip):
                mismatches.append(MismatchDetail(resolver=res_name, type="A", reason=f"Returned suspicious IP {ip}"))
                suspicious_flags.append(f"{res_name} 返回疑似拦截/保留 IP: {ip}")
        
        # R3: Disagreement (Intersection empty)
        if baseline_agreed and final_baseline_a and res_a_set:
            if not (final_baseline_a & res_a_set):
                 # 进一步检查是否是完全不同的 IP
                 mismatches.append(MismatchDetail(resolver=res_name, type="A", reason="A records mismatch with baseline"))
                 # 暂时不直接定为 SUSPECTED，因为可能是 CDN 区域调度
                 # 除非所有 ISP 都偏离 baseline 指向同一个奇怪 IP？
                 
    # 3. Verdict
    status = "OK"
    reasons = []
    
    if baseline_agreed:
        reasons.append("基准 (Google/Cloudflare) 一致")
    else:
        reasons.append("基准不一致，结果仅供参考")
        status = "UNCERTAIN"

    # 聚合逻辑
    has_suspicious = any("疑似拦截" in r for r in suspicious_flags)
    
    if has_suspicious:
        status = "SUSPECTED_RPZ"
        reasons.extend(suspicious_flags)
    elif mismatches and baseline_agreed:
        # 有不匹配但不是明显保留 IP
        # 比如 Hinet 解析到了 1.2.3.4，Google 是 5.6.7.8 (CDN)
        # 这种情况标记为 POSSIBLE_INTERFERENCE
        status = "POSSIBLE_INTERFERENCE"
        reasons.extend([f"{m.resolver}: {m.reason}" for m in mismatches])
    elif not baseline_agreed and mismatches:
        status = "UNCERTAIN"
        reasons.append("因基准不一致，详细差异未作为判定依据")
    else:
        if status != "UNCERTAIN":
            # Check if it's actually empty/NXDOMAIN everywhere
            is_nx = False
            # Check baseline resolvers for NXDOMAIN
            for b_res in baseline_resolvers:
                if b_res in results and results[b_res].A.status == "NXDOMAIN":
                    is_nx = True
                    break
            
            if is_nx and not final_baseline_a:
                status = "DOMAIN_NOT_FOUND"
                reasons.clear()
                reasons.append("域名不存在 (NXDOMAIN)")
            else:
                status = "OK"
                reasons.clear()
                reasons.append("未发现明显异常")
            
    return baseline_info, ComparisonInfo(mismatches=mismatches), ConclusionInfo(status=status, reasons=reasons)
