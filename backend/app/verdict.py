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
        if (not set1 and not set2) or (set1 & set2):
            baseline_agreed = True
            final_baseline_a = set1 & set2 if set1 and set2 else (set1 or set2)
        else:
            # Baseline disagree (e.g. Google differs from Cloudflare)
            baseline_agreed = False
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
        agreed=baseline_agreed,
        types_checked=["A", "AAAA"],
        reference=reference
    )
    
    # --- 2. Compare & Check Suspicious ---
    mismatches = []
    suspicious_flags = [] # List of reasons
    
    # Resolvers to check against baseline
    check_list = [k for k in results.keys() if k not in baseline_resolvers]
    
    for res_name in check_list:
        res_result = results[res_name]
        
        # Check A records
        res_a_set = set(res_result.A.answers)
        
        # Priority Check: Known Suspicious IPs (Overrides everything)
        for ip in res_result.A.answers:
            is_sus, reason = is_suspicious_ip(ip)
            if is_sus:
                mismatches.append(MismatchDetail(resolver=res_name, type="A", reason=reason))
                suspicious_flags.append(f"[{res_name}] {reason}")
        
        # If already flagged as suspicious, skip weaker consistency checks for this resolver
        # But still check other mismatches for completeness if needed? 
        # For clutter reduction, maybe we just record the mismatch.
        
        # R1: NXDOMAIN when Baseline OK
        if results[res_name].A.status == "NXDOMAIN" and final_baseline_a:
             mismatches.append(MismatchDetail(resolver=res_name, type="A", reason="返回 NXDOMAIN 但基准正常"))
             # This is a strong signal too, but sometimes legit (propagation)
             # Adding to suspicious if it happens
             suspicious_flags.append(f"[{res_name}] 域名不存在 (NXDOMAIN)，疑似被阻断")

        # R3: Disagreement
        if final_baseline_a and res_a_set:
            if not (final_baseline_a & res_a_set):
                 # No intersection
                 mismatches.append(MismatchDetail(resolver=res_name, type="A", reason="结果与基准不一致"))
                 
    # --- 3. Verdict ---
    status = "OK"
    reasons = []

    # Priority 1: Any explicit suspicious IP match?
    if any("命中" in r for r in suspicious_flags):
        status = "SUSPECTED_RPZ"
        reasons.extend(suspicious_flags)
        
    # Priority 2: NXDOMAIN block?
    elif any("NXDOMAIN" in r for r in suspicious_flags):
        status = "DOMAIN_NOT_FOUND" # Or SUSPECTED depending on intent. 
        # User wanted NXDOMAIN to be RED. 
        # If baseline is OK, then NXDOMAIN on Hinet is likely BLOCKING.
        # But if baseline is also NXDOMAIN (handled later), then it's just not found.
        
        # Check if baseline is NXDOMAIN logic
        is_baseline_nx = False
        for b_res in baseline_resolvers:
             if b_res in results and results[b_res].A.status == "NXDOMAIN":
                 is_baseline_nx = True
        
        if is_baseline_nx:
             status = "DOMAIN_NOT_FOUND"
             reasons.append("域名不存在 (NXDOMAIN)")
        else:
             # Baseline OK, but Local NX -> Blocking
             status = "SUSPECTED_RPZ" 
             reasons.append("基准解析正常，但本地返回 NXDOMAIN (疑似阻断)")

    # Priority 3: Baseline Disagreement (which prevents us from knowing "Truth")
    elif not baseline_agreed:
        status = "UNCERTAIN"
        reasons.append("基准 (Google/Cloudflare) 结果不一致，无法判定是否污染。")
        reasons.append("提示：CDN 域名在不同网络下 IP 不同属正常现象。")
        
        # If we have disagreements in TW resolvers too, list them
        if mismatches:
            reasons.append("注意：台湾 ISP 解析结果与基准均不相同。")

    # Priority 4: Mismatches with Agreed Baseline
    elif mismatches:
        status = "POSSIBLE_INTERFERENCE"
        reasons.append("解析结果与基准 (Google/CF) 不一致")
        for m in mismatches:
             reasons.append(f"{m.resolver}: {m.reason}")
             
    else:
        status = "OK"
        reasons.append("未发现明显异常")
            
    return baseline_info, ComparisonInfo(mismatches=mismatches), ConclusionInfo(status=status, reasons=reasons)
