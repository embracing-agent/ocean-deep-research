"""
湾区中餐馆盈利效率模型 —— 计算引擎
====================================

三层结构：

  L1 桌位物理层  simulate_table_dynamics()
      离散事件模拟：同行人数分布 × 桌型配比 → 座位填充率 φ 与桌位吞吐率。
      这是"翻台率"的微观基础，比直接拍一个 φ 严谨得多。

  L2 时段需求层  simulate_day()
      逐小时 min(需求, 产能) 卷积，含排队削峰与流失（balking）。
      自动区分【需求约束区】与【产能约束区】—— 全模型最关键的机制。

  L3 财务层      profit_and_loss()
      完整 P&L + 单位经济学指标 + 资本回报。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .params import (
    GENERIC_TRAFFIC_WEEKDAY,
    GENERIC_TRAFFIC_WEEKEND,
    HOURS,
    MACRO,
    FormatSpec,
    Macro,
)

LUNCH_HOURS = set(range(10, 16))   # 10:00-15:59 记午市客单
DINNER_HOURS = set(range(16, 23))  # 16:00-22:59 记晚市客单


# ===========================================================================
# L1  桌位物理层
# ===========================================================================

@dataclass
class TableDynamics:
    """饱和状态下的桌位动力学结果。"""

    seat_fill: float             # φ：时均在座人数 / 总座位数
    parties_per_hour: float      # 桌位吞吐（组/小时）
    covers_per_hour: float       # 座位产能（人次/小时）
    avg_party: float
    avg_table_used: float        # 平均实际占用的桌容量
    combine_rate: float          # 并桌比例


def _draw_party_size(mean: float, sd: float, rng: random.Random) -> int:
    """同行人数：对数正态截断，保证 >= 1、整数、右偏（现实中确实右偏）。"""
    sigma = math.sqrt(math.log(1.0 + (sd / mean) ** 2))
    mu = math.log(mean) - 0.5 * sigma ** 2
    s = int(round(rng.lognormvariate(mu, sigma)))
    return max(1, min(12, s))


_FILL_CACHE: Dict[tuple, "TableDynamics"] = {}


def simulate_table_dynamics(
    spec: FormatSpec,
    hours: float = 250.0,
    seed: int = 7,
    lookahead: int = 5,
    n_seeds: int = 3,
) -> TableDynamics:
    """在【需求无限】的饱和条件下模拟桌位分配，得到真实的 φ 与吞吐上限。

    分时步（1 分钟）离散事件模拟。迎宾规则贴近真实操作：
      1. 队列先进先出，但允许向后看 `lookahead` 组，
         以便"小桌空出来时先放小组进去"（真实迎宾都这么干）；
      2. 对某一组，选【当前空闲且装得下】的最小桌；
      3. 装不下最大桌时并两张空桌（额外 3 分钟摆台）；
      4. 座位数为 1 的单元表示吧台位，可精确容纳单人 —— 这是提升 φ 的关键设计杠杆。

    输出的 φ 是【时均在座人数 / 总座位数】，即座位填充率的严格定义。
    结果对 `n_seeds` 个随机种子取平均，消除单次模拟噪声。
    """
    if n_seeds > 1:
        runs = [simulate_table_dynamics(spec, hours, seed + 101 * i,
                                        lookahead, n_seeds=1)
                for i in range(n_seeds)]
        k = float(len(runs))
        return TableDynamics(
            seat_fill=sum(r.seat_fill for r in runs) / k,
            parties_per_hour=sum(r.parties_per_hour for r in runs) / k,
            covers_per_hour=sum(r.covers_per_hour for r in runs) / k,
            avg_party=sum(r.avg_party for r in runs) / k,
            avg_table_used=sum(r.avg_table_used for r in runs) / k,
            combine_rate=sum(r.combine_rate for r in runs) / k,
        )

    # 缓存键刻意【不含 cycle_min】：在饱和条件下 φ 是纯装箱属性，
    # 与每桌占用多久无关（已数值验证：dwell 30→140 分钟，φ 变化 < 2%，属模拟噪声）。
    key = (tuple(sorted(spec.table_mix.items())), round(spec.party_size_mean, 4),
           round(spec.party_size_sd, 4), hours, seed, lookahead)
    hit = _FILL_CACHE.get(key)
    if hit is not None:
        # 吞吐量确实依赖周期，按比例换算回当前 spec
        scale = 1.0
        return TableDynamics(
            seat_fill=hit.seat_fill,
            parties_per_hour=hit.seat_fill * spec.seats
            / max(1e-9, hit.avg_party) / spec.cycle_hr,
            covers_per_hour=hit.seat_fill * spec.seats / spec.cycle_hr,
            avg_party=hit.avg_party,
            avg_table_used=hit.avg_table_used,
            combine_rate=hit.combine_rate,
        )

    rng = random.Random(seed)
    caps: List[int] = []
    for cap, n in sorted(spec.table_mix.items()):
        caps.extend([cap] * int(n))
    if not caps:
        return TableDynamics(0.0, 0.0, 0.0, spec.party_size_mean, 0.0, 0.0)

    n_tab = len(caps)
    total_seats = sum(caps)
    free_at = [0.0] * n_tab            # 每张桌的释放时刻（分钟）
    occupied_by = [0] * n_tab          # 当前该桌坐了几个人
    max_cap = max(caps)
    total_minutes = int(hours * 60)
    warmup = int(total_minutes * 0.10)  # 丢弃暖机期，避免开局全空拉低 φ

    queue: List[Tuple[int, int]] = []
    seat_minutes = 0.0
    parties = 0
    party_sum = 0
    table_cap_sum = 0
    combines = 0
    measured_minutes = 0

    for t in range(total_minutes):
        # --- 释放到期桌位 ---
        for i in range(n_tab):
            if occupied_by[i] and free_at[i] <= t:
                occupied_by[i] = 0

        # --- 放弃排队（balking）：等太久的客人会走 ---
        # 这一条不只是为了写实。没有它，一组"进不去任何桌、也凑不出并桌"的大客
        # 会永久卡在队首，把 lookahead 窗口堵死，模拟就此停摆
        # （实测：seed=3 跑 400 小时，φ 从 0.79 假性塌到 0.31）。
        if queue:
            queue = [(sz, at) for sz, at in queue
                     if t - at <= spec.max_wait_min]

        # --- 饱和条件：门口永远有人排队 ---
        while len(queue) < lookahead + 4:
            queue.append((_draw_party_size(spec.party_size_mean,
                                           spec.party_size_sd, rng), t))

        # --- 迎宾循环：只要还能安排就继续安排 ---
        progress = True
        while progress:
            progress = False
            for qi in range(min(lookahead, len(queue))):
                size = queue[qi][0]
                if size <= max_cap:
                    fits = [i for i in range(n_tab)
                            if not occupied_by[i] and caps[i] >= size]
                    if not fits:
                        continue
                    idx = min(fits, key=lambda i: caps[i])
                    occupied_by[idx] = size
                    free_at[idx] = t + spec.cycle_min
                    used_cap = caps[idx]
                else:
                    # 并桌
                    empties = [i for i in range(n_tab) if not occupied_by[i]]
                    empties.sort(key=lambda i: -caps[i])
                    if len(empties) < 2 or caps[empties[0]] + caps[empties[1]] < size:
                        continue
                    i1, i2 = empties[0], empties[1]
                    occupied_by[i1] = size
                    occupied_by[i2] = 0.001  # 占位：并入的第二张桌不再单独计人
                    free_at[i1] = free_at[i2] = t + spec.cycle_min + 3.0
                    used_cap = caps[i1] + caps[i2]
                    combines += 1

                queue.pop(qi)
                parties += 1
                party_sum += size
                table_cap_sum += used_cap
                progress = True
                break

        # --- 统计（跳过暖机期）---
        if t >= warmup:
            seat_minutes += sum(v for v in occupied_by if v >= 1)
            measured_minutes += 1

    elapsed_hours = measured_minutes / 60.0
    seat_fill = seat_minutes / (total_seats * max(1, measured_minutes))
    frac = (total_minutes - warmup) / total_minutes
    pph = parties * frac / max(1e-9, elapsed_hours)
    avg_party = party_sum / max(1, parties)
    result = TableDynamics(
        seat_fill=min(1.0, seat_fill),
        parties_per_hour=pph,
        covers_per_hour=pph * avg_party,
        avg_party=avg_party,
        avg_table_used=table_cap_sum / max(1, parties),
        combine_rate=combines / max(1, parties),
    )
    _FILL_CACHE[key] = result
    return result


# ===========================================================================
# L2  时段需求层
# ===========================================================================

@dataclass
class DayResult:
    covers: float                       # 当日实际服务人次
    covers_lunch: float
    covers_dinner: float
    revenue: float                      # 当日堂食菜品收入（税前、小费前）
    lost_covers: float                  # 因产能不足流失的人次
    hourly_served: Dict[int, float] = field(default_factory=dict)
    hourly_potential: Dict[int, float] = field(default_factory=dict)
    hourly_capacity: Dict[int, float] = field(default_factory=dict)
    bound_hours_capacity: int = 0       # 有多少小时处于产能约束


def simulate_day(
    spec: FormatSpec,
    market_intensity: float,
    fill: float,
    weekend: bool = False,
    uniform_capture: bool = False,
    kitchen_binding: bool = True,
) -> DayResult:
    """逐小时把潜在需求转换为实际服务人次。

    market_intensity M：商圈在该地点每日能提供的【通用餐饮潜在到店人次】。
    这是全模型唯一的外生需求标量，用它扫描即可得到相位图。
    """
    traffic = GENERIC_TRAFFIC_WEEKEND if weekend else GENERIC_TRAFFIC_WEEKDAY
    tot = sum(traffic.values())
    weekend_lift = 1.32 if weekend else 1.0

    cap_cph = spec.seat_capacity_cph(fill)
    if kitchen_binding:
        cap_cph = min(cap_cph, spec.kitchen_covers_per_hour)

    # 排队缓冲：可暂存的人次 = 产能 × 可忍受等待时长
    queue_cap = cap_cph * (spec.max_wait_min / 60.0)

    served_h: Dict[int, float] = {}
    potential_h: Dict[int, float] = {}
    capacity_h: Dict[int, float] = {}
    carry = 0.0
    lost = 0.0
    covers = c_lunch = c_dinner = 0.0
    revenue = 0.0
    bound = 0

    for h in HOURS:
        cap_coef = 1.0 if uniform_capture else spec.capture[h]
        if cap_coef <= 0.02:
            potential_h[h] = 0.0
            served_h[h] = 0.0
            capacity_h[h] = 0.0
            # 打烊时排队清零
            lost += carry
            carry = 0.0
            continue

        potential = market_intensity * (traffic[h] / tot) * cap_coef * weekend_lift
        demand = potential + carry
        served = min(demand, cap_cph)
        if served >= cap_cph - 1e-9 and demand > cap_cph:
            bound += 1

        unmet = demand - served
        new_carry = min(unmet, queue_cap)
        lost += unmet - new_carry
        carry = new_carry

        check = spec.check_lunch if h in LUNCH_HOURS else spec.check_dinner
        revenue += served * check
        covers += served
        if h in LUNCH_HOURS:
            c_lunch += served
        else:
            c_dinner += served

        potential_h[h] = potential
        served_h[h] = served
        capacity_h[h] = cap_cph

    lost += carry
    return DayResult(
        covers=covers,
        covers_lunch=c_lunch,
        covers_dinner=c_dinner,
        revenue=revenue,
        lost_covers=lost,
        hourly_served=served_h,
        hourly_potential=potential_h,
        hourly_capacity=capacity_h,
        bound_hours_capacity=bound,
    )


# ===========================================================================
# L3  财务层
# ===========================================================================

@dataclass
class PnL:
    spec_name: str
    market_intensity: float

    # --- 规模 ---
    covers_month: float
    revenue_dinein: float
    revenue_delivery: float
    revenue_total: float

    # --- 成本 ---
    cogs: float
    card_fees: float
    delivery_commission: float
    packaging: float
    supplies: float
    shrinkage: float
    maintenance_capex: float
    labor_boh: float
    labor_foh: float
    labor_total: float
    rent: float
    utilities: float
    other_fixed: float
    owner_cost: float

    # --- 利润 ---
    prime_cost: float
    ebitda: float
    ebitda_margin: float
    owner_cash_flow: float       # 不计业主机会成本（业主自己干活的现金流）

    # --- 单位经济学 ---
    seat_hours_month: float
    revpash: float               # 每可用座位小时收入
    goppash: float               # 每可用座位小时毛营运利润
    profit_per_sqft_year: float
    profit_per_labor_hour: float
    revenue_per_seat_year: float
    covers_per_seat_day: float

    # --- 风险 / 资本 ---
    breakeven_revenue: float
    breakeven_covers_day: float
    margin_of_safety: float
    operating_leverage: float    # DOL = 贡献毛利 / EBITDA
    roic: float                  # EBITDA / 投入资本
    payback_years: float
    capacity_utilization: float  # 实际人次 / 物理产能人次
    lost_covers_month: float

    detail: Dict[str, float] = field(default_factory=dict)


def _labor_cost(spec: FormatSpec, macro: Macro) -> Tuple[float, float, float]:
    boh_wage = sum(n * m for _, n, m in spec.boh_salaried)
    foh_wage = spec.foh_hourly_hours * macro.min_wage * spec.foh_wage_premium
    b = 1.0 + macro.payroll_burden
    return boh_wage * b, foh_wage * b, (boh_wage + foh_wage) * b


FOH_FLOOR_SHARE = 0.55   # 前厅编制中"无论多冷清都必须在岗"的比例


def _foh_hours_scaled(spec: FormatSpec, covers_month: float) -> float:
    """前厅工时 = 固定值班底 + 随人次线性变动的部分。

    结构：H(c) = H0·s + H0·(1-s)·(c / c_design)

    · 固定部分 s=55%：营业时间内必须有人开门、收银、看场，与客流无关。
      这是小店经营杠杆恶劣的根本原因——它是"面积×营业时长"的函数，不是客流的函数。
    · 变动部分：每人次的边际前厅工时 = H0·(1-s)/c_design。
      川湘约 7.7 min/人次（全服务）、面馆约 3.7（柜台自助）、火锅约 10.1（加汤/摆撤台）。
    """
    ratio = covers_month / max(1e-9, spec.design_covers_month)
    return spec.foh_hourly_hours * (
        FOH_FLOOR_SHARE + (1.0 - FOH_FLOOR_SHARE) * ratio
    )


def _boh_multiplier(spec: FormatSpec, covers_month: float) -> float:
    """后厨编制的产量弹性。

    厨房班底是阶梯成本：技术岗（炒锅/面档）几乎不可削减，
    但备料、打荷、洗碗必须随产量增加。用幂律 c^0.55 近似这个"部分规模经济"：
    产量翻倍 → 后厨成本 +47%；产量减半 → 只能降到 90%（技术岗砍不动）。
    """
    ratio = covers_month / max(1e-9, spec.design_covers_month)
    return max(0.90, min(2.6, ratio ** 0.55))


def profit_and_loss(
    spec: FormatSpec,
    market_intensity: float,
    macro: Macro = MACRO,
    fill: Optional[float] = None,
    uniform_capture: bool = False,
    scale_foh_labor: bool = True,
    rent_psf: Optional[float] = None,
    include_owner_cost: bool = True,
) -> PnL:
    if fill is None:
        fill = simulate_table_dynamics(spec).seat_fill
    rent_psf = macro.rent_psf_month if rent_psf is None else rent_psf

    wd = simulate_day(spec, market_intensity, fill, weekend=False,
                      uniform_capture=uniform_capture)
    we = simulate_day(spec, market_intensity, fill, weekend=True,
                      uniform_capture=uniform_capture)

    # 每周 days_per_week 天：其中 2 天按周末口径（周五晚亦按周末）
    wknd_days = min(2.0, macro.days_per_week)
    wkdy_days = macro.days_per_week - wknd_days
    weeks_pm = macro.weeks_per_year / 12.0

    covers_m = (wd.covers * wkdy_days + we.covers * wknd_days) * weeks_pm
    rev_dinein = (wd.revenue * wkdy_days + we.revenue * wknd_days) * weeks_pm
    lost_m = (wd.lost_covers * wkdy_days + we.lost_covers * wknd_days) * weeks_pm

    # --- 外卖：占总收入 delivery_share，但受后厨余量约束 ---
    ds = spec.delivery_share
    rev_delivery_target = rev_dinein * ds / max(1e-9, 1.0 - ds)
    spare_kitchen = 0.0
    for day, n in ((wd, wkdy_days), (we, wknd_days)):
        for h in HOURS:
            if day.hourly_capacity.get(h, 0.0) > 0:
                spare = max(0.0, spec.kitchen_covers_per_hour - day.hourly_served[h])
                spare_kitchen += spare * n
    spare_kitchen *= weeks_pm
    avg_check = rev_dinein / max(1e-9, covers_m)
    rev_delivery = min(rev_delivery_target, spare_kitchen * avg_check * 0.85)
    rev_total = rev_dinein + rev_delivery

    # --- 变动成本 ---
    food_rev = rev_total * (1.0 - spec.bev_share)
    bev_rev = rev_total * spec.bev_share
    cogs = food_rev * spec.food_cost_ratio + bev_rev * spec.bev_cost_ratio
    card = rev_dinein * macro.effective_card_fee
    commission = rev_delivery * macro.delivery_commission
    packaging = rev_delivery * spec.packaging_ratio
    supplies = rev_dinein * spec.supplies_ratio
    shrinkage = rev_total * macro.shrinkage_ratio

    # --- 人力 ---
    phys_cap_covers = 0.0
    for day, n in ((wd, wkdy_days), (we, wknd_days)):
        phys_cap_covers += sum(day.hourly_capacity.values()) * n
    phys_cap_covers *= weeks_pm
    utilization = covers_m / max(1e-9, phys_cap_covers)

    boh, foh, _ = _labor_cost(spec, macro)
    vol_ratio = covers_m / max(1e-9, spec.design_covers_month)
    if scale_foh_labor:
        scaled_hours = _foh_hours_scaled(spec, covers_m)
        foh = scaled_hours * macro.min_wage * spec.foh_wage_premium * (
            1.0 + macro.payroll_burden
        )
        boh *= _boh_multiplier(spec, covers_m)
    labor = boh + foh

    # --- 固定成本 ---
    rent = spec.total_sqft * rent_psf
    # 水电气：约 55% 与营业时长/面积绑定（照明/空调/冷库/排烟基载），45% 随产量
    utilities = spec.utilities_month * (0.55 + 0.45 * min(2.5, vol_ratio))
    # 其它固定费：保险/维修/清洁/耗材随产量走，牌照/会计/POS 不变
    other = spec.other_fixed_month * (0.70 + 0.30 * min(2.5, vol_ratio))
    owner = macro.owner_opportunity_cost if include_owner_cost else 0.0

    maint_capex = rev_total * macro.maintenance_capex_ratio
    variable = cogs + card + commission + packaging + supplies + shrinkage + maint_capex
    fixed = labor + rent + utilities + other + owner
    ebitda = rev_total - variable - fixed
    prime = cogs + labor

    # --- 单位经济学 ---
    open_hours_day = sum(1 for h in HOURS if spec.capture[h] > 0.02)
    seat_hours_m = spec.seats * open_hours_day * macro.days_per_month
    revpash = rev_dinein / seat_hours_m
    var_dinein = (
        rev_dinein * (1 - spec.bev_share) * spec.food_cost_ratio
        + rev_dinein * spec.bev_share * spec.bev_cost_ratio
        + card + supplies
        + rev_dinein * (macro.shrinkage_ratio + macro.maintenance_capex_ratio)
    )
    goppash = (rev_dinein - var_dinein) / seat_hours_m

    labor_hours_m = spec.foh_hourly_hours + sum(
        n * 190.0 for _, n, _ in spec.boh_salaried
    )

    # --- 盈亏平衡 / 风险 ---
    contribution_rate = (rev_total - variable) / max(1e-9, rev_total)
    fixed_for_be = fixed
    be_rev = fixed_for_be / max(1e-6, contribution_rate)
    be_covers_day = be_rev / max(1e-9, avg_check) / macro.days_per_month
    max_covers_day = phys_cap_covers / macro.days_per_month
    mos = 1.0 - be_rev / max(1e-9, rev_total)
    dol = (rev_total - variable) / ebitda if abs(ebitda) > 1e-6 else float("inf")

    capital = spec.capex
    roic = ebitda * 12.0 / capital
    payback = (capital / (ebitda * 12.0)) if ebitda > 0 else float("inf")

    # --- 更诚实的产能利用率：只看真正有客流的"黄金时段" ---
    prime_hours = [h for h in HOURS
                   if GENERIC_TRAFFIC_WEEKDAY[h] >= 0.40 and spec.capture[h] > 0.02]
    prime_served = prime_cap = 0.0
    peak_util = 0.0
    for day, n in ((wd, wkdy_days), (we, wknd_days)):
        for h in prime_hours:
            prime_served += day.hourly_served.get(h, 0.0) * n
            prime_cap += day.hourly_capacity.get(h, 0.0) * n
        for h in HOURS:
            c = day.hourly_capacity.get(h, 0.0)
            if c > 0:
                peak_util = max(peak_util, day.hourly_served[h] / c)
    prime_util = prime_served / max(1e-9, prime_cap)

    return PnL(
        spec_name=spec.name,
        market_intensity=market_intensity,
        covers_month=covers_m,
        revenue_dinein=rev_dinein,
        revenue_delivery=rev_delivery,
        revenue_total=rev_total,
        cogs=cogs,
        card_fees=card,
        delivery_commission=commission,
        packaging=packaging,
        supplies=supplies,
        shrinkage=shrinkage,
        maintenance_capex=maint_capex,
        labor_boh=boh,
        labor_foh=foh,
        labor_total=labor,
        rent=rent,
        utilities=utilities,
        other_fixed=other,
        owner_cost=owner,
        prime_cost=prime,
        ebitda=ebitda,
        ebitda_margin=ebitda / max(1e-9, rev_total),
        owner_cash_flow=ebitda + owner,
        seat_hours_month=seat_hours_m,
        revpash=revpash,
        goppash=goppash,
        profit_per_sqft_year=ebitda * 12.0 / spec.total_sqft,
        profit_per_labor_hour=ebitda / max(1e-9, labor_hours_m),
        revenue_per_seat_year=rev_total * 12.0 / spec.seats,
        covers_per_seat_day=covers_m / macro.days_per_month / spec.seats,
        breakeven_revenue=be_rev,
        breakeven_covers_day=be_covers_day,
        margin_of_safety=mos,
        operating_leverage=dol,
        roic=roic,
        payback_years=payback,
        capacity_utilization=utilization,
        lost_covers_month=lost_m,
        detail={
            "fill": fill,
            "avg_check": avg_check,
            "contribution_rate": contribution_rate,
            "fixed_cost": fixed,
            "variable_cost": variable,
            "open_hours_day": open_hours_day,
            "max_covers_day": max_covers_day,
            "be_covers_ratio": be_covers_day / max(1e-9, max_covers_day),
            "labor_hours_month": labor_hours_m,
            "labor_ratio": labor / max(1e-9, rev_total),
            "cogs_ratio": cogs / max(1e-9, rev_total),
            "rent_ratio": rent / max(1e-9, rev_total),
            "prime_ratio": prime / max(1e-9, rev_total),
            "capacity_cph": spec.capacity_cph(fill),
            "seat_cap_cph": spec.seat_capacity_cph(fill),
            "bound_hours_wd": wd.bound_hours_capacity,
            "bound_hours_we": we.bound_hours_capacity,
            "revenue_month_day": rev_total / macro.days_per_month,
            "prime_utilization": prime_util,
            "peak_utilization": peak_util,
            "prime_hours_per_day": float(len(prime_hours)),
            "shrinkage": shrinkage,
            "maintenance_capex": maint_capex,
        },
    )


# ===========================================================================
# 静态（满产）单位经济学 —— 用于四因子分解
# ===========================================================================

@dataclass
class UnitEconomics:
    """满产条件下的结构性单位经济学，不含需求因素。"""

    name: str
    sigma_seat: float        # 座位密度  seats / sqft
    velocity: float          # 座位周转  φ / 周期(小时) = 人次 / 座位小时
    contrib_per_cover: float # 每人次贡献毛利（晚市口径）
    contrib_per_seat_hour: float
    contrib_per_sqft_hour: float
    revpash_max: float
    food_cost_per_cover: float
    seat_hours_per_cover: float


def unit_economics(spec: FormatSpec, macro: Macro = MACRO,
                   fill: Optional[float] = None) -> UnitEconomics:
    if fill is None:
        fill = simulate_table_dynamics(spec).seat_fill
    p = spec.check_dinner
    food = p * ((1 - spec.bev_share) * spec.food_cost_ratio
                + spec.bev_share * spec.bev_cost_ratio)
    other_var = p * (macro.effective_card_fee + spec.supplies_ratio)
    contrib = p - food - other_var
    velocity = fill / spec.cycle_hr
    return UnitEconomics(
        name=spec.name,
        sigma_seat=spec.seat_density,
        velocity=velocity,
        contrib_per_cover=contrib,
        contrib_per_seat_hour=contrib * velocity,
        contrib_per_sqft_hour=contrib * velocity * spec.seat_density,
        revpash_max=p * velocity,
        food_cost_per_cover=food,
        seat_hours_per_cover=1.0 / velocity,
    )
