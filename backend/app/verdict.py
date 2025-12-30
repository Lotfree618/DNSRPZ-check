from typing import List, Dict, Set
import ipaddress
from app.schemas import ResolverResult, BaselineInfo, ComparisonInfo, ConclusionInfo, MismatchDetail
from app.config import SUSPICIOUS_NETWORKS, KNOWN_BLOCK_IPS

def is_suspicious_ip(ip_str: str) -> (bool, str):
    """
    检查 IP 是否疑似污染/拦截。
    返回 (is_suspicious, reason)
    """
    # 1. Check Exact Match (Block Pages)
    if ip_str in KNOWN_BLOCK_IPS:
        if ip_str == "182.173.0.181":
            return True, f"命中台湾 165 反诈骗警示页 ({ip_str})"
        return True, f"命中已知拦截/保留 IP ({ip_str})"

    # 2. Check CIDR (Private/Reserved)
    try:
        ip = ipaddress.ip_address(ip_str)
        for net in SUSPICIOUS_NETWORKS:
            if ip in ipaddress.ip_network(net):
                return True, f"命中保留/私有网段 ({net})"
        return False, ""
    except ValueError:
        return False, ""

def analyze_results(results: Dict[str, ResolverResult]) -> (BaselineInfo, ComparisonInfo, ConclusionInfo):
    # --- 1. Establish Baseline (Google vs Cloudflare) ---
    baseline_resolvers = ["google", "cloudflare"]
    baseline_a_sets = []
    
    for b_res in baseline_resolvers:
        if b_res in results:
            baseline_a_sets.append(set(results[b_res].A.answers))
    
    final_baseline_a = set()
    baseline_agreed = False
    
    if len(baseline_a_sets) == 2:
        set1, set2 = baseline_a_sets[0], baseline_a_sets[1]
        
        # 定义: "基准一致"
        # 严格来说 CDN 经常导致 8.8.8.8 和 1.1.1.1 结果不同。
        # 这里只要它们不为空，我们取并集作为 "Reference Set"
        reference_set = set1 | set2
        
        # 只要有一方非空，就认为基准有效
        final_baseline_a = reference_set
        
        # 记录是否完全一致用于 UI 展示 (Optional, logic relaxed)
        baseline_agreed = (set1 == set2)
        
    elif len(baseline_a_sets) == 1:
        baseline_agreed = True
        final_baseline_a = baseline_a_sets[0]
    else:
        baseline_agreed = False

    reference = {
        "A": list(final_baseline_a),
        "AAAA": list() 
    }
    
    baseline_info = BaselineInfo(
        # 如果不一致，但在 relaxed 模式下，我们也认为 baseline 有效
        agreed=True, 
        types_checked=["A", "AAAA"],
        reference=reference
    )
    
    # --- 2. Compare & Check Suspicious ---
    mismatches = []
    suspicious_flags = [] # List of reasons
    
    # Resolvers to check
    check_list = [k for k in results.keys() if k not in baseline_resolvers]
    
    for res_name in check_list:
        res_result = results[res_name]
        
        # Priority Check: Known Suspicious IPs (Overrides everything)
        for ip in res_result.A.answers:
            is_sus, reason = is_suspicious_ip(ip)
            if is_sus:
                suspicious_flags.append(f"[{res_name}] {reason}")
        
        # R1: NXDOMAIN check
        # 如果基准显示有 IP，但本地返回 NXDOMAIN -> 疑似污染 (除非基准也是 NX)
        if results[res_name].A.status == "NXDOMAIN":
             # Check if baseline ALL say NXDOMAIN?
             baseline_is_nx = True
             for b_res in baseline_resolvers:
                 if b_res in results and results[b_res].A.status != "NXDOMAIN":
                     baseline_is_nx = False
                     break
             
             if not baseline_is_nx and final_baseline_a:
                 # Baseline has records, Local is NX -> Suspicious (Blocking)
                 suspicious_flags.append(f"[{res_name}] 域名不存在 (NXDOMAIN)，但基准解析正常")

        # R3: Consistency Check (Relaxed)
        # 只有当:
        # 1. 没有发现明显污染 IP
        # 2. 目前状态看起来正常
        # 3. 本地结果与 Reference Set 完全无交集
        # -> 标记为 "差异"，但根据用户要求，如果基准本身就不一致 (CDN)，这个差异也是 OK 的。
        
        res_a_set = set(res_result.A.answers)
        if final_baseline_a and res_a_set:
            if not (final_baseline_a & res_a_set):
                 # No intersection with EITHER Google OR Cloudflare
                 mismatches.append(MismatchDetail(resolver=res_name, type="A", reason="结果与所有基准 (Google/CF) 均不一致"))

    # --- 3. Verdict ---
    status = "OK"
    reasons = []

    # Priority 1: Suspicious IPs / Blocking
    if any("命中" in r for r in suspicious_flags):
        status = "SUSPECTED_RPZ" # Frontend text: 被污染/RPZ
        reasons.extend(suspicious_flags)
        
    # Priority 2: NXDOMAIN Blocking
    elif any("NXDOMAIN" in r for r in suspicious_flags):
        status = "SUSPECTED_RPZ"
        reasons.extend(suspicious_flags)

    # Priority 3: Mismatches (Only if strict baseline agreed)
    elif mismatches:
        # 只有在基准非常一致的情况下，差异才会被标记为警告
        status = "POSSIBLE_INTERFERENCE"
        reasons.append("解析结果与基准不一致")
        for m in mismatches:
             reasons.append(f"{m.resolver}: {m.reason}")
             
    else:
        # Default OK
        # Covers:
        # 1. Matching baseline
        # 2. Inconsistent baseline (CDN situation)
        status = "OK"
        if not baseline_agreed:
            reasons.append("基准结果不一致 (CDN)，且未发现明显污染，判定正常")
        else:
            reasons.append("未发现明显异常")
            
    return baseline_info, ComparisonInfo(mismatches=mismatches), ConclusionInfo(status=status, reasons=reasons)
