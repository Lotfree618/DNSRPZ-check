"""结果判定与聚合"""
from typing import Dict, List, Set
from . import config


def classify_tw_result(
    result: Dict,
    baseline_ips: Set[str],
    baseline_empty: bool = False
) -> str:
    """对台湾解析器结果进行分类"""
    status = result.get("status")
    ips = set(result.get("ips", []))
    
    if status == "timeout":
        return "超时"
    if status == "error":
        return "错误"
    
    # 基准为空时的特殊处理
    if baseline_empty:
        if status == "nxdomain" or (status == "ok" and len(ips) == 0):
            return "空解析"  # 基准和台湾都无结果，视为正常
        # 基准空但台湾有结果，可能是本地域名
        if status == "ok" and len(ips) > 0:
            return "解析差异"
    
    if status == "nxdomain":
        return "被阻断"
    
    # status == "ok"
    # 检查是否命中黑名单
    if ips & config.BLOCK_PAGE_IPS:
        return "已封锁"
    
    # 检查是否为基准子集
    if not baseline_ips:
        return "错误"  # 基准无结果时标记为错误
    
    if ips.issubset(baseline_ips):
        return "正常"
    
    return "解析差异"


def aggregate_verdict(probe_result: Dict) -> Dict:
    """聚合域名级判定结果"""
    domain = probe_result["domain"]
    baseline_results = probe_result["baseline"]
    tw_results = probe_result["tw"]
    
    # 构建基准 IP 集合
    baseline_ips = set()
    for r in baseline_results:
        if r.get("status") == "ok":
            baseline_ips.update(r.get("ips", []))
    
    baseline_empty = len(baseline_ips) == 0
    
    # 检查台湾解析器是否也全部为空
    tw_all_empty = True
    for r in tw_results:
        if r.get("status") == "ok" and len(r.get("ips", [])) > 0:
            tw_all_empty = False
            break
        if r.get("status") not in ("ok", "nxdomain"):
            tw_all_empty = False
            break
    
    # 分类台湾解析器结果
    tw_classified = []
    reasons = []
    
    for r in tw_results:
        category = classify_tw_result(r, baseline_ips, baseline_empty)
        tw_classified.append({
            **r,
            "category": category
        })
        
        # 收集异常原因（空解析不算异常）
        if category == "被阻断":
            reasons.append("污染：被阻断")
        elif category == "已封锁":
            reasons.append("污染：已封锁")
        elif category == "超时":
            reasons.append("检测失败：超时")
        elif category == "错误":
            reasons.append("检测失败：错误")
    
    # 基准无结果且台湾也为空时，不算异常（空解析）
    # 只有当基准无结果但台湾有结果时才标记异常
    if baseline_empty and not tw_all_empty:
        reasons.append("基准无结果")
    
    # 去重
    reasons = list(dict.fromkeys(reasons))
    
    # 域名级状态
    status = "正常" if not reasons else "异常"
    
    return {
        "domain": domain,
        "status": status,
        "reasons": reasons,
        "baseline": {
            "ips": sorted(baseline_ips),
            "detail": baseline_results
        },
        "tw": tw_classified
    }
