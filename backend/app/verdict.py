"""结果判定与聚合"""
from typing import Dict, List, Set
from . import config


def classify_tw_result(
    result: Dict,
    baseline_ips: Set[str]
) -> str:
    """对台湾解析器结果进行分类"""
    status = result.get("status")
    ips = set(result.get("ips", []))
    
    if status == "timeout":
        return "超时"
    if status == "error":
        return "错误"
    if status == "nxdomain":
        # 如果基准也为空，则不算被阻断
        if not baseline_ips:
            return "空解析"
        return "被阻断"
    
    # status == "ok"
    if not ips:
        # 如果基准也为空，则为空解析
        if not baseline_ips:
            return "空解析"
        return "被阻断"
    
    # 检查是否命中黑名单
    if ips & config.BLOCK_PAGE_IPS:
        return "已封锁"
    
    # 检查是否为基准子集
    if not baseline_ips:
        return "空解析"
    
    if ips.issubset(baseline_ips):
        return "正常"
    
    return "解析差异"


def aggregate_verdict(probe_result: Dict) -> Dict:
    """聚合域名级判定结果"""
    domain = probe_result["domain"]
    baseline_results = probe_result["baseline"]
    tw_results = probe_result["tw"]
    redirect_trace = probe_result.get("redirect_trace")
    
    # 构建基准 IP 集合
    baseline_ips = set()
    for r in baseline_results:
        if r.get("status") == "ok":
            baseline_ips.update(r.get("ips", []))
    
    # 检查台湾解析器是否都为空
    tw_all_empty = True
    for r in tw_results:
        if r.get("status") == "ok" and r.get("ips"):
            tw_all_empty = False
            break
        if r.get("status") not in ("ok", "nxdomain"):
            tw_all_empty = False
            break
    
    # 分类台湾解析器结果
    tw_classified = []
    reasons = []
    has_empty_resolution = False
    
    for r in tw_results:
        category = classify_tw_result(r, baseline_ips)
        tw_classified.append({
            **r,
            "category": category
        })
        
        # 收集异常原因
        if category == "被阻断":
            reasons.append("污染：被阻断")
        elif category == "已封锁":
            reasons.append("污染：已封锁")
        elif category == "超时":
            reasons.append("检测失败：超时")
        elif category == "错误":
            reasons.append("检测失败：错误")
        elif category == "空解析":
            has_empty_resolution = True
    
    # 去重
    reasons = list(dict.fromkeys(reasons))
    
    # 域名级状态判定
    # 如果基准和台湾都为空，则为"空解析"（正常的一种）
    if not baseline_ips and tw_all_empty and has_empty_resolution and not reasons:
        status = "空解析"
    elif not reasons:
        status = "正常"
    else:
        status = "异常"
    
    return {
        "domain": domain,
        "status": status,
        "reasons": reasons,
        "baseline": {
            "ips": sorted(baseline_ips),
            "detail": baseline_results
        },
        "tw": tw_classified,
        "redirect_trace": redirect_trace
    }
