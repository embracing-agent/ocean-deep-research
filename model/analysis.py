"""
湾区中餐馆盈利效率模型 —— 分析层
==================================

对应报告中的七类分析：
  A. 满产单位经济学四因子分解
  B. 基准情景 P&L 对照
  C. 需求扫描（经营杠杆 / 盈亏平衡 / 制度切换）
  D. 相位图（最优业态 = f(需求密度, 租金)）
  E. 敏感性（龙卷风图）
  F. 蒙特卡洛 + 多年生存期望 NPV
  G. 内点最优：定价、桌型配比、面积
"""

from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .engine import (
    PnL,
    UnitEconomics,
    profit_and_loss,
    simulate_table_dynamics,
    unit_economics,
)
from .params import FORMATS, MACRO, FormatSpec, Macro

# 参考市场强度：湾区华人商圈一个"生意还行"的铺位每日通用潜在到店人次
REFERENCE_M = 120.0


# ---------------------------------------------------------------------------
# A. 满产四因子分解
# ---------------------------------------------------------------------------

def factor_decomposition(specs: Sequence[FormatSpec] = FORMATS,
                         macro: Macro = MACRO) -> List[Dict[str, float]]:
    """Π/A ∝ σ_seat × velocity × contribution —— 三个可乘因子的分解。

    这是全模型最重要的恒等式：满产利润密度是三项之积，
    因此"某一项极强、其余极弱"的业态会被"三项都还行"的业态击败。
    """
    out = []
    for s in specs:
        td = simulate_table_dynamics(s)
        ue = unit_economics(s, macro, fill=td.seat_fill)
        out.append({
            "name": s.name,
            "fill_phi": td.seat_fill,
            "cycle_min": s.cycle_min,
            "sigma_seat": ue.sigma_seat,
            "velocity": ue.velocity,
            "check": s.check_dinner,
            "food_per_cover": ue.food_cost_per_cover,
            "contrib_per_cover": ue.contrib_per_cover,
            "revpash_max": ue.revpash_max,
            "goppash_max": ue.contrib_per_seat_hour,
            "contrib_per_sqft_hour": ue.contrib_per_sqft_hour,
            "seat_cap_cph": s.seat_capacity_cph(td.seat_fill),
            "kitchen_cph": s.kitchen_covers_per_hour,
            "binding": "座位" if s.seat_capacity_cph(td.seat_fill)
                       <= s.kitchen_covers_per_hour else "后厨",
            "combine_rate": td.combine_rate,
            "avg_table_used": td.avg_table_used,
        })
    return out


# ---------------------------------------------------------------------------
# B. 基准情景
# ---------------------------------------------------------------------------

def base_case(specs: Sequence[FormatSpec] = FORMATS,
              m: float = REFERENCE_M,
              macro: Macro = MACRO,
              uniform_capture: bool = False) -> List[PnL]:
    fills = {s.name: simulate_table_dynamics(s).seat_fill for s in specs}
    return [
        profit_and_loss(s, m, macro, fill=fills[s.name],
                        uniform_capture=uniform_capture)
        for s in specs
    ]


# ---------------------------------------------------------------------------
# C. 需求扫描
# ---------------------------------------------------------------------------

def demand_sweep(specs: Sequence[FormatSpec] = FORMATS,
                 m_grid: Optional[Sequence[float]] = None,
                 macro: Macro = MACRO,
                 uniform_capture: bool = False,
                 metric: str = "ebitda") -> Dict[str, List[Tuple[float, float]]]:
    if m_grid is None:
        m_grid = [40 + 10 * i for i in range(56)]   # 40 .. 590
    fills = {s.name: simulate_table_dynamics(s).seat_fill for s in specs}
    res: Dict[str, List[Tuple[float, float]]] = {}
    for s in specs:
        curve = []
        for m in m_grid:
            p = profit_and_loss(s, m, macro, fill=fills[s.name],
                                uniform_capture=uniform_capture)
            curve.append((m, getattr(p, metric)))
        res[s.name] = curve
    return res


def regime_transition(spec: FormatSpec, macro: Macro = MACRO,
                      uniform_capture: bool = False) -> Dict[str, float]:
    """求两个关键阈值：

      M_be   —— EBITDA 转正的需求密度（生存线）
      M_cap  —— 高峰时段开始出现产能约束的需求密度（制度切换点）

    M < M_cap：需求约束区，"翻台率"完全不值钱，只有客单价与固定成本重要。
    M > M_cap：产能约束区，"每座位小时贡献"接管一切。
    """
    fill = simulate_table_dynamics(spec).seat_fill
    lo, hi = 20.0, 1400.0

    def eb(m):
        return profit_and_loss(spec, m, macro, fill=fill,
                               uniform_capture=uniform_capture).ebitda

    m_be = float("nan")
    if eb(lo) < 0 < eb(hi):
        a, b = lo, hi
        for _ in range(48):
            mid = 0.5 * (a + b)
            if eb(mid) < 0:
                a = mid
            else:
                b = mid
        m_be = 0.5 * (a + b)

    m_cap = float("nan")
    a, b = lo, hi

    def bound(m):
        p = profit_and_loss(spec, m, macro, fill=fill,
                            uniform_capture=uniform_capture)
        return p.detail["bound_hours_we"] + p.detail["bound_hours_wd"] > 0

    if not bound(lo) and bound(hi):
        for _ in range(48):
            mid = 0.5 * (a + b)
            if bound(mid):
                b = mid
            else:
                a = mid
        m_cap = 0.5 * (a + b)

    p_ref = profit_and_loss(spec, REFERENCE_M, macro, fill=fill,
                            uniform_capture=uniform_capture)
    return {
        "name": spec.name,
        "M_breakeven": m_be,
        "M_capacity_bind": m_cap,
        "safety_ratio": (REFERENCE_M / m_be) if m_be == m_be else float("nan"),
        "headroom_ratio": (m_cap / REFERENCE_M) if m_cap == m_cap else float("nan"),
        "ref_ebitda": p_ref.ebitda,
        "ref_utilization": p_ref.capacity_utilization,
    }


# ---------------------------------------------------------------------------
# D. 相位图
# ---------------------------------------------------------------------------

def phase_diagram(specs: Sequence[FormatSpec] = FORMATS,
                  m_grid: Optional[Sequence[float]] = None,
                  rent_grid: Optional[Sequence[float]] = None,
                  macro: Macro = MACRO,
                  metric: str = "roic",
                  uniform_capture: bool = False):
    """在 (需求密度, 租金) 平面上求逐点最优业态。

    返回 (m_grid, rent_grid, winner_index_matrix, best_value_matrix)
    """
    if m_grid is None:
        m_grid = [60 + 12 * i for i in range(45)]
    if rent_grid is None:
        rent_grid = [2.0 + 0.15 * i for i in range(41)]   # $2.00 - $8.00 /sqft/月
    fills = {s.name: simulate_table_dynamics(s).seat_fill for s in specs}

    winner = [[0] * len(m_grid) for _ in rent_grid]
    best = [[0.0] * len(m_grid) for _ in rent_grid]
    for i, r in enumerate(rent_grid):
        for j, m in enumerate(m_grid):
            vals = []
            for s in specs:
                p = profit_and_loss(s, m, macro, fill=fills[s.name],
                                    rent_psf=r, uniform_capture=uniform_capture)
                v = getattr(p, metric)
                if p.ebitda <= 0:
                    v = -abs(v) if metric == "roic" else v
                vals.append(v)
            k = max(range(len(vals)), key=lambda x: vals[x])
            winner[i][j] = k if vals[k] > 0 else -1     # -1 = 三者皆亏
            best[i][j] = vals[k]
    return list(m_grid), list(rent_grid), winner, best


# ---------------------------------------------------------------------------
# E. 敏感性（龙卷风）
# ---------------------------------------------------------------------------

_TORNADO_SPEC_FIELDS: List[Tuple[str, str, float]] = [
    # (字段, 中文名, ±相对幅度)
    ("check_dinner", "晚市客单价", 0.15),
    ("dwell_min", "用餐时长", 0.15),
    ("food_cost_ratio", "食材成本率", 0.12),
    ("party_size_mean", "同行人数", 0.12),
    ("turn_min", "清台时间", 0.30),
    ("delivery_share", "外卖占比", 0.40),
    ("utilities_month", "水电气", 0.20),
    ("other_fixed_month", "其它固定费", 0.20),
    ("total_sqft", "承租面积", 0.12),
    ("foh_hourly_hours", "前厅工时", 0.15),
]

_TORNADO_MACRO_FIELDS: List[Tuple[str, str, float]] = [
    ("rent_psf_month", "租金单价", 0.20),
    ("min_wage", "最低工资", 0.12),
    ("payroll_burden", "雇主负担率", 0.25),
    ("delivery_commission", "平台抽成", 0.25),
]


def tornado(spec: FormatSpec, m: float = REFERENCE_M,
            macro: Macro = MACRO, metric: str = "ebitda") -> List[Dict[str, float]]:
    fill = simulate_table_dynamics(spec).seat_fill
    base = getattr(profit_and_loss(spec, m, macro, fill=fill), metric)
    rows = []

    for fld, label, amp in _TORNADO_SPEC_FIELDS:
        vals = []
        for sgn in (-1, 1):
            cur = getattr(spec, fld)
            new = cur * (1 + sgn * amp)
            s2 = replace(spec, **{fld: new})
            f2 = simulate_table_dynamics(s2).seat_fill if fld in (
                "party_size_mean", "dwell_min", "turn_min") else fill
            if fld == "total_sqft":
                # 面积变化时按比例调整座位数（保持座位密度）
                s2 = replace(s2, seats=max(8, int(round(spec.seats * (1 + sgn * amp)))))
                f2 = simulate_table_dynamics(s2).seat_fill
            vals.append(getattr(profit_and_loss(s2, m, macro, fill=f2), metric))
        rows.append({"label": label, "low": min(vals), "high": max(vals),
                     "swing": max(vals) - min(vals), "base": base, "amp": amp})

    for fld, label, amp in _TORNADO_MACRO_FIELDS:
        vals = []
        for sgn in (-1, 1):
            cur = getattr(macro, fld)
            m2 = replace(macro, **{fld: cur * (1 + sgn * amp)})
            vals.append(getattr(profit_and_loss(spec, m, m2, fill=fill), metric))
        rows.append({"label": label, "low": min(vals), "high": max(vals),
                     "swing": max(vals) - min(vals), "base": base, "amp": amp})

    rows.sort(key=lambda r: -r["swing"])
    return rows


# ---------------------------------------------------------------------------
# F. 蒙特卡洛 + 生存期望 NPV
# ---------------------------------------------------------------------------

@dataclass
class MCResult:
    name: str
    ebitda: List[float]
    roic: List[float]
    npv: List[float]
    p_loss: float
    p_ruin: float            # 现金流为负且业主净收入 < 0
    median_ebitda: float
    mean_ebitda: float
    p10: float
    p90: float
    cvar10: float            # 最差 10% 情景的平均值
    median_roic: float
    median_npv: float
    p_npv_positive: float


def _pct(xs: List[float], q: float) -> float:
    ys = sorted(xs)
    if not ys:
        return float("nan")
    k = q * (len(ys) - 1)
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return ys[lo] + (ys[hi] - ys[lo]) * (k - lo)


def monte_carlo(spec: FormatSpec, n: int = 3000, m_median: float = REFERENCE_M,
                macro: Macro = MACRO, seed: int = 11) -> MCResult:
    """不确定性来源（均取实证上合理的离散度）：

      需求强度   对数正态 σ=0.42（餐饮选址成败的方差极大，这是主导项）
      客单价     ±8%
      食材成本率 ±10%（湾区食材价格波动 + 损耗管理水平）
      用餐时长   ±10%
      租金       ±12%
      工资       ±8%
      外卖占比   ±30%
      资本支出   对数正态 σ=0.22（装修超支是常态，且右偏）
    """
    rng = random.Random(seed)
    fill0 = simulate_table_dynamics(spec).seat_fill

    ebitdas, roics, npvs = [], [], []
    ruin = 0
    for _ in range(n):
        m = m_median * math.exp(rng.gauss(0.0, 0.42))
        k_check = 1.0 + rng.gauss(0.0, 0.08)
        k_food = 1.0 + rng.gauss(0.0, 0.10)
        k_dwell = 1.0 + rng.gauss(0.0, 0.10)
        k_rent = 1.0 + rng.gauss(0.0, 0.12)
        k_wage = 1.0 + rng.gauss(0.0, 0.08)
        k_deliv = max(0.0, 1.0 + rng.gauss(0.0, 0.30))
        k_capex = math.exp(rng.gauss(0.05, 0.22))   # 均值上偏：装修普遍超支

        s2 = replace(
            spec,
            check_lunch=spec.check_lunch * k_check,
            check_dinner=spec.check_dinner * k_check,
            food_cost_ratio=min(0.62, spec.food_cost_ratio * k_food),
            dwell_min=max(12.0, spec.dwell_min * k_dwell),
            delivery_share=min(0.55, spec.delivery_share * k_deliv),
            capex=spec.capex * k_capex,
        )
        m2 = replace(macro,
                     rent_psf_month=macro.rent_psf_month * k_rent,
                     min_wage=macro.min_wage * k_wage)
        # 直接复用 fill0：本次抽样只扰动了用餐时长，而 φ 与用餐时长无关
        # （见 engine.simulate_table_dynamics 的缓存说明），桌型配比与同行人数分布未变。
        # 在这里重跑离散事件模拟不仅白花 3 倍算力，还会往结果里注入纯粹的模拟噪声。
        p = profit_and_loss(s2, m, m2, fill=fill0)
        ebitdas.append(p.ebitda)
        roics.append(p.roic)
        if p.owner_cash_flow < 0:
            ruin += 1

        # --- 7 年生存期望 NPV（含年度倒闭风险与租金递增）---
        npv = -s2.capex
        alive = 1.0
        for yr in range(1, macro.lease_term_years + 1):
            rent_mult = (1 + macro.rent_escalator) ** (yr - 1)
            wage_mult = (1 + 0.035) ** (yr - 1)      # 加州最低工资年增
            price_mult = (1 + 0.028) ** (yr - 1)     # 提价（略低于成本增速）
            s3 = replace(s2,
                         check_lunch=s2.check_lunch * price_mult,
                         check_dinner=s2.check_dinner * price_mult)
            m3 = replace(m2,
                         rent_psf_month=m2.rent_psf_month * rent_mult,
                         min_wage=m2.min_wage * wage_mult)
            py = profit_and_loss(s3, m, m3, fill=fill0)
            cf = py.ebitda * 12.0
            alive *= (1.0 - spec.annual_failure_hazard)
            # 失败情景：当年止损，残值约为设备的 20%
            salvage = 0.20 * s2.capex * spec.annual_failure_hazard * alive
            npv += (alive * cf + salvage) / (1 + macro.discount_rate) ** yr
        npvs.append(npv)

    return MCResult(
        name=spec.name,
        ebitda=ebitdas, roic=roics, npv=npvs,
        p_loss=sum(1 for x in ebitdas if x < 0) / len(ebitdas),
        p_ruin=ruin / n,
        median_ebitda=_pct(ebitdas, 0.5),
        mean_ebitda=sum(ebitdas) / len(ebitdas),
        p10=_pct(ebitdas, 0.10), p90=_pct(ebitdas, 0.90),
        cvar10=sum(sorted(ebitdas)[: max(1, n // 10)]) / max(1, n // 10),
        median_roic=_pct(roics, 0.5),
        median_npv=_pct(npvs, 0.5),
        p_npv_positive=sum(1 for x in npvs if x > 0) / len(npvs),
    )


# ---------------------------------------------------------------------------
# G. 内点最优
# ---------------------------------------------------------------------------

def optimize_price(spec: FormatSpec, m0: float = REFERENCE_M,
                   macro: Macro = MACRO,
                   k_grid: Optional[Sequence[float]] = None) -> Dict[str, float]:
    """价格内点最优。

    需求响应：M(k) = M0 · k^(-ε)，k 为客单价相对基准的倍数。
    在【产能约束区】，最优价高于 Lerner 加成价，多出来的部分正是
    座位小时的影子价格 μ —— 这是"翻台率"与"客单价"真正的数学连接点。
    """
    if k_grid is None:
        k_grid = [0.60 + 0.02 * i for i in range(46)]   # 0.60x .. 1.50x
    fill = simulate_table_dynamics(spec).seat_fill
    eps = spec.price_elasticity

    curve = []
    for k in k_grid:
        # 关键：食材成本是【每份的美元成本】，不随定价变动。
        # 模型内部用 food_cost_ratio（占收入比），因此改价时必须反向缩放该比率，
        # 否则降价会同步"降低"食材成本，把降价算成免费的，最优价会被严重低估。
        s2 = replace(spec, check_lunch=spec.check_lunch * k,
                     check_dinner=spec.check_dinner * k,
                     food_cost_ratio=min(0.85, spec.food_cost_ratio / k),
                     bev_cost_ratio=min(0.85, spec.bev_cost_ratio / k))
        m = m0 * (k ** (-eps))
        p = profit_and_loss(s2, m, macro, fill=fill)
        curve.append((k, p.ebitda, p.revenue_total, p.covers_month,
                      p.capacity_utilization))

    k_star, eb_star = max(((k, e) for k, e, *_ in curve), key=lambda x: x[1])
    p_star = spec.check_dinner * k_star
    util_star = [c[4] for c in curve if abs(c[0] - k_star) < 1e-9][0]

    # 每人次的【美元】食材成本（含酒水），与定价无关
    f_dollar = spec.check_dinner * (
        (1 - spec.bev_share) * spec.food_cost_ratio
        + spec.bev_share * spec.bev_cost_ratio
    )
    lerner = f_dollar * eps / (eps - 1.0)
    seat_hours_per_cover = spec.cycle_hr / fill
    # p* = ε/(ε-1)·(f + μ·s)  ⟹  μ = [p*(ε-1)/ε - f] / s
    # 需求约束区 μ 应 ≈ 0；解出的负值不是"负影子价格"，
    # 而是高固定成本下【以价换量摊薄固定成本】的激励，故单独命名。
    implied = (p_star * (eps - 1.0) / eps - f_dollar) / seat_hours_per_cover
    mu = max(0.0, implied)
    fixed_absorption = min(0.0, implied)

    return {
        "name": spec.name,
        "k_star": k_star,
        "p_star": p_star,
        "p_base": spec.check_dinner,
        "ebitda_star": eb_star,
        "lerner_price": lerner,
        "shadow_price_per_seat_hour": mu,
        "fixed_cost_absorption_incentive": fixed_absorption,
        "utilization_at_optimum": util_star,
        "seat_hours_per_cover": seat_hours_per_cover,
        "elasticity": eps,
        "curve": curve,
    }


def pricing_diagnostics(spec: FormatSpec, m0: float = REFERENCE_M,
                        macro: Macro = MACRO) -> Dict[str, object]:
    """比"求最优价"更稳健的三个诊断量。

    常弹性需求 M(p)=M0·p^(-ε) 是无界的：只要 ε 略大于 1，模型就会一路建议涨价，
    最优点常落在"利用率 20%、价格翻倍"这种明显外推过头的地方。
    真实餐厅面对的是【局部】弹性——比品类弹性高得多，因为隔壁就是替代品。

    所以这里不报"最优价"，而报三个不依赖外推的量：

      ε_crit  使当前售价恰为最优的隐含弹性。
              ε < ε_crit → 该涨价；ε > ε_crit → 该降价。
              把它和你对自己需求弹性的判断比一比，比信一个外推的最优价可靠得多。
      局部利润梯度  ±5% / ±10% 调价对 EBITDA 的影响（按给定 ε）。
      解析上界   Lerner 加成 ε/(ε-1)·(f + μs)，作为价格的理论天花板参考。
    """
    fill = simulate_table_dynamics(spec).seat_fill

    def eb_at(k: float, eps: float) -> float:
        s2 = replace(spec, check_lunch=spec.check_lunch * k,
                     check_dinner=spec.check_dinner * k,
                     food_cost_ratio=min(0.85, spec.food_cost_ratio / k),
                     bev_cost_ratio=min(0.85, spec.bev_cost_ratio / k))
        return profit_and_loss(s2, m0 * (k ** (-eps)), macro, fill=fill).ebitda

    # --- ε_crit：使 dΠ/dk|_{k=1} = 0 的弹性（二分）---
    h = 0.02

    def grad(eps: float) -> float:
        return (eb_at(1 + h, eps) - eb_at(1 - h, eps)) / (2 * h)

    lo, hi = 1.05, 6.0
    eps_crit = float("nan")
    if grad(lo) > 0 > grad(hi):
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if grad(mid) > 0:
                lo = mid
            else:
                hi = mid
        eps_crit = 0.5 * (lo + hi)

    eps = spec.price_elasticity
    base = eb_at(1.0, eps)
    local = {f"{round((k - 1) * 100):+d}%": eb_at(k, eps) - base
             for k in (0.90, 0.95, 1.05, 1.10)}

    f_dollar = spec.check_dinner * (
        (1 - spec.bev_share) * spec.food_cost_ratio
        + spec.bev_share * spec.bev_cost_ratio)
    p_ref = profit_and_loss(spec, m0, macro, fill=fill)
    return {
        "name": spec.name,
        "eps_crit": eps_crit,
        "eps_assumed": eps,
        "verdict": ("该涨价" if eps < eps_crit else "该降价")
                   if eps_crit == eps_crit else "无内点解",
        "local_delta": local,
        "base_ebitda": base,
        "food_per_cover": f_dollar,
        "seat_hours_per_cover": spec.cycle_hr / fill,
        "peak_utilization": p_ref.detail["peak_utilization"],
    }


def ayce_crossover(base: FormatSpec, ayce: FormatSpec, macro: Macro = MACRO,
                   m_grid: Optional[Sequence[float]] = None) -> Dict[str, object]:
    """自助（AYCE）相对单点火锅需要多少【额外客流】才划算。

    在"无差异化、同一客流池"的假设下 AYCE 必然更差：客单更低、食材成本率更高。
    它唯一的经济学理由是【把需求曲线推出去】。这里量化这个门槛：
    AYCE 需要多大的 M 才能追平单点火锅在基准 M 下的 EBITDA。
    """
    if m_grid is None:
        m_grid = [60 + 5 * i for i in range(120)]
    fb = simulate_table_dynamics(base).seat_fill
    fa = simulate_table_dynamics(ayce).seat_fill
    target = profit_and_loss(base, REFERENCE_M, macro, fill=fb).ebitda
    need = None
    for m in m_grid:
        if profit_and_loss(ayce, m, macro, fill=fa).ebitda >= target:
            need = m
            break
    same_m = profit_and_loss(ayce, REFERENCE_M, macro, fill=fa)
    return {
        "base_ebitda_at_ref": target,
        "ayce_ebitda_at_ref": same_m.ebitda,
        "M_needed": need,
        "lift_required": (need / REFERENCE_M - 1) if need else None,
    }


def optimize_table_mix(spec: FormatSpec, seats_target: Optional[int] = None,
                       macro: Macro = MACRO) -> Dict[str, object]:
    """在座位总数近似不变的约束下，枚举 1/2/4/6 座单元配比，最大化座位产能。

    这是"10-15 桌"这个题设下真正存在的、可解的离散最优化问题。
    1 座单元 = 吧台位；把它纳入枚举，才能看出"给单人客配单座"这个杠杆值多少。
    """
    if seats_target is None:
        seats_target = spec.seats
    best = None
    results = []
    for n1 in range(0, 15, 2):
        for n2 in range(0, 17):
            for n4 in range(0, 15):
                rem = seats_target - n1 - 2 * n2 - 4 * n4
                for n6 in {max(0, rem // 6), max(0, rem // 6 + 1)}:
                    seats = n1 + 2 * n2 + 4 * n4 + 6 * n6
                    units = n1 + n2 + n4 + n6
                    tables = n2 + n4 + n6          # 吧台位不算"桌"
                    if abs(seats - seats_target) > 2 or not (6 <= tables <= 20):
                        continue
                    mix = {k: v for k, v in
                           ((1, n1), (2, n2), (4, n4), (6, n6)) if v}
                    s2 = replace(spec, table_mix=mix, seats=seats, tables=tables)
                    td = simulate_table_dynamics(s2, hours=100, seed=3, n_seeds=2)
                    cph = s2.seat_capacity_cph(td.seat_fill)
                    results.append({
                        "n1": n1, "n2": n2, "n4": n4, "n6": n6,
                        "tables": tables, "units": units, "seats": seats,
                        "fill": td.seat_fill, "cph": cph,
                        "combine_rate": td.combine_rate,
                    })
                    if best is None or cph > best["cph"]:
                        best = results[-1]
    results.sort(key=lambda r: -r["cph"])
    cur = simulate_table_dynamics(spec, hours=100, seed=3, n_seeds=2)
    return {
        "name": spec.name,
        "best": best,
        "top5": results[:5],
        "current": {"mix": dict(spec.table_mix), "fill": cur.seat_fill,
                    "cph": spec.seat_capacity_cph(cur.seat_fill)},
        "gain_pct": (best["cph"] / spec.seat_capacity_cph(cur.seat_fill) - 1) * 100
        if best else 0.0,
    }


def optimize_footprint(spec: FormatSpec, m: float = REFERENCE_M,
                       macro: Macro = MACRO,
                       scale_grid: Optional[Sequence[float]] = None) -> Dict[str, object]:
    """面积内点最优：座位数与面积同比例缩放，求 EBITDA / ROIC 最大的规模。

    需求给定时，"店开多大"存在真正的内点最优：
    太小 → 高峰被截断、丢客；太大 → 租金与最低值班人力被空座吃掉。
    """
    if scale_grid is None:
        scale_grid = [0.22 + 0.04 * i for i in range(36)]  # 0.22x .. 1.62x
    dining_sqft = spec.total_sqft - spec.kitchen_sqft
    rows = []
    for g in scale_grid:
        seats = max(8, int(round(spec.seats * g)))
        mix = {k: max(0, int(round(v * g))) for k, v in spec.table_mix.items()}
        if sum(mix.values()) == 0:
            continue
        # 后厨/仓储/卫生间是刚性面积，不随座位数缩放 —— 这是小店经营杠杆差的物理根源
        total = spec.kitchen_sqft + dining_sqft * g
        s2 = replace(spec, total_sqft=total, seats=seats,
                     tables=sum(mix.values()), table_mix=mix,
                     capex=spec.capex * (0.30 + 0.70 * total / spec.total_sqft),
                     foh_hourly_hours=spec.foh_hourly_hours * (0.45 + 0.55 * g),
                     utilities_month=spec.utilities_month * (0.35 + 0.65 * g),
                     kitchen_covers_per_hour=spec.kitchen_covers_per_hour * (0.5 + 0.5 * g))
        f2 = simulate_table_dynamics(s2, hours=250, seed=5).seat_fill
        p = profit_and_loss(s2, m, macro, fill=f2)
        rows.append({"scale": g, "sqft": s2.total_sqft, "seats": seats,
                     "ebitda": p.ebitda, "roic": p.roic,
                     "util": p.capacity_utilization,
                     "profit_psf": p.profit_per_sqft_year})
    best_e = max(rows, key=lambda r: r["ebitda"])
    best_r = max(rows, key=lambda r: r["roic"])
    return {"name": spec.name, "rows": rows,
            "best_ebitda": best_e, "best_roic": best_r}


def iso_profit_frontier(macro: Macro = MACRO,
                        targets: Sequence[float] = (12.0, 18.0, 24.0, 32.0),
                        dwell_grid: Optional[Sequence[float]] = None):
    """(客单价, 占座时长) 平面上的等贡献毛利曲线。

    GOPPASH = φ·(p - f(p)) / (d+τ)。令其等于常数 G，解出 p(d)：
        p = G·(d+τ) / (φ·(1-θ_eff))
    即在该平面上，可行业态落在一族过原点的直线上 —— 斜率 = 单位座位小时贡献要求。
    """
    if dwell_grid is None:
        dwell_grid = [15 + 5 * i for i in range(23)]   # 15 .. 125 分钟
    theta_eff = 0.34    # 食材+刷卡+易耗品的综合变动成本率（跨业态中位）
    phi = 0.75
    tau = 9.0
    curves = {}
    for g in targets:
        curves[g] = [
            (d, g * ((d + tau) / 60.0) / (phi * (1 - theta_eff)))
            for d in dwell_grid
        ]
    return curves
