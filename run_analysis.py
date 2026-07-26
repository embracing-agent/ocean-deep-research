#!/usr/bin/env python3
"""跑通全部分析，输出图表 (outputs/*.png) 与结果表 (outputs/results.json / *.csv)。

    python3 run_analysis.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict

from model import charts
from model.analysis import (
    REFERENCE_M,
    ayce_crossover,
    base_case,
    demand_sweep,
    factor_decomposition,
    iso_profit_frontier,
    monte_carlo,
    optimize_footprint,
    optimize_table_mix,
    pricing_diagnostics,
    phase_diagram,
    regime_transition,
    tornado,
)
from model.engine import profit_and_loss, simulate_day, simulate_table_dynamics
from model.params import (FORMATS, HOTPOT, HOTPOT_AYCE, MACRO, NOODLE,
                          SICHUAN, VARIANTS)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUT, exist_ok=True)
RESULTS = {}


def banner(t):
    print("\n" + "=" * 78)
    print(f"  {t}")
    print("=" * 78)


def main():
    t0 = time.time()
    fills = {s.name: simulate_table_dynamics(s).seat_fill for s in FORMATS}

    # ---------------- A. 单位经济学分解 ----------------
    banner("A  满产单位经济学 —— 三因子分解")
    decomp = factor_decomposition()
    hdr = (f"{'业态':<12}{'φ填充':>7}{'周期':>7}{'座位密度':>10}{'周转v':>8}"
           f"{'客单':>8}{'贡献/人次':>10}{'RevPASH':>10}{'GOPPASH':>10}{'$/sqft·h':>10}")
    print(hdr)
    for d in decomp:
        print(f"{d['name']:<12}{d['fill_phi']:>7.3f}{d['cycle_min']:>6.0f}m"
              f"{d['sigma_seat']:>10.4f}{d['velocity']:>8.3f}"
              f"{d['check']:>8.0f}{d['contrib_per_cover']:>10.2f}"
              f"{d['revpash_max']:>10.2f}{d['goppash_max']:>10.2f}"
              f"{d['contrib_per_sqft_hour']:>10.3f}")
    RESULTS["factor_decomposition"] = decomp

    # ---------------- B. 基准 P&L ----------------
    banner(f"B  基准情景 P&L（M={REFERENCE_M:.0f}）")
    pnls = base_case(m=REFERENCE_M)
    for p in pnls:
        d = p.detail
        print(f"\n--- {p.spec_name} ---")
        print(f"  收入 堂食 ${p.revenue_dinein:>10,.0f} | 外卖 ${p.revenue_delivery:>9,.0f}"
              f" | 合计 ${p.revenue_total:>10,.0f}  (年 ${p.revenue_total*12:,.0f})")
        print(f"  食材 {p.cogs/p.revenue_total*100:>5.1f}%  人力 {d['labor_ratio']*100:>5.1f}%"
              f"  Prime {d['prime_ratio']*100:>5.1f}%  租金 {d['rent_ratio']*100:>5.1f}%")
        print(f"  EBITDA ${p.ebitda:>9,.0f}/月 ({p.ebitda_margin*100:>5.1f}%)"
              f"  业主口径现金流 ${p.owner_cash_flow:>9,.0f}/月")
        print(f"  盈亏平衡 ${p.breakeven_revenue:>9,.0f}/月 | 安全边际 {p.margin_of_safety*100:>5.1f}%"
              f" | DOL {p.operating_leverage:>5.2f}")
        print(f"  利用率 全时段 {p.capacity_utilization*100:>4.1f}% / 黄金时段"
              f" {d['prime_utilization']*100:>4.1f}% / 峰值小时 {d['peak_utilization']*100:>5.1f}%")
        print(f"  ROIC {p.roic*100:>6.1f}%  回本 {p.payback_years:>5.1f}年"
              f"  利润/sqft/年 ${p.profit_per_sqft_year:>6.0f}"
              f"  利润/人工小时 ${p.profit_per_labor_hour:>5.2f}")
    RESULTS["base_case"] = [
        {k: v for k, v in asdict(p).items() if k != "detail"} | {"detail": p.detail}
        for p in pnls
    ]

    # 严格"无差异化"对照组
    banner("B'  严格对照组：抹平所有时段捕获差异（uniform_capture=True）")
    pnls_u = base_case(m=REFERENCE_M, uniform_capture=True)
    for p in pnls_u:
        print(f"  {p.spec_name:<12} 收入 ${p.revenue_total:>9,.0f}"
              f"  EBITDA ${p.ebitda:>8,.0f} ({p.ebitda_margin*100:>5.1f}%)"
              f"  ROIC {p.roic*100:>6.1f}%")
    RESULTS["base_case_uniform"] = [
        {"name": p.spec_name, "revenue": p.revenue_total, "ebitda": p.ebitda,
         "margin": p.ebitda_margin, "roic": p.roic} for p in pnls_u
    ]

    # ---------------- C. 需求扫描 / 制度切换 ----------------
    banner("C  需求扫描：生存线与产能约束切换点")
    regimes = [regime_transition(s) for s in FORMATS]
    for r in regimes:
        print(f"  {r['name']:<12} 盈亏平衡 M={r['M_breakeven']:>6.1f}"
              f" | 高峰产能触顶 M={r['M_capacity_bind']:>6.1f}"
              f" | 基准安全倍数 {r['safety_ratio']:>4.2f}x"
              f" | 到触顶还有 {r['headroom_ratio']:>4.2f}x")
    RESULTS["regimes"] = regimes

    sweep = demand_sweep(m_grid=[40 + 8 * i for i in range(66)])
    RESULTS["demand_sweep"] = {k: v for k, v in sweep.items()}

    # 交叉点
    banner("C'  业态优势翻转点")
    for metric in ("ebitda", "roic"):
        sw = demand_sweep(m_grid=[40 + 5 * i for i in range(150)], metric=metric)
        names = list(sw.keys())
        prev = None
        for i in range(len(sw[names[0]])):
            vals = [sw[n][i][1] for n in names]
            w = names[max(range(3), key=lambda k: vals[k])]
            if prev and w != prev:
                print(f"  [{metric}] M≈{sw[names[0]][i][0]:.0f} 时 {prev} → {w}")
            prev = w
        print(f"  [{metric}] 最高需求端 (M={sw[names[0]][-1][0]:.0f}) 胜出：{prev}")

    # ---------------- D. 相位图 ----------------
    banner("D  相位图（argmax ROIC）")
    m_grid, rent_grid, winner, best = phase_diagram(
        m_grid=[60 + 10 * i for i in range(46)],
        rent_grid=[2.0 + 0.15 * i for i in range(41)])
    names = [s.name for s in FORMATS]
    share = {}
    tot = len(m_grid) * len(rent_grid)
    for row in winner:
        for w in row:
            key = names[w] if w >= 0 else "三者皆亏损"
            share[key] = share.get(key, 0) + 1
    for k, v in sorted(share.items(), key=lambda x: -x[1]):
        print(f"  {k:<12} 占参数空间 {v/tot*100:>5.1f}%")
    RESULTS["phase_share"] = {k: v / tot for k, v in share.items()}

    # ---------------- E. 敏感性 ----------------
    banner("E  敏感性（龙卷风，± 见标注）")
    torn = {}
    for s in FORMATS:
        rows = tornado(s)
        torn[s.name] = rows
        print(f"\n  {s.name} — 前 6 项：")
        for r in rows[:6]:
            print(f"    {r['label']:<10} ±{r['amp']*100:>3.0f}%  "
                  f"EBITDA 摆幅 ${r['swing']:>9,.0f}"
                  f"  [{r['low']:>9,.0f} .. {r['high']:>9,.0f}]")
    RESULTS["tornado"] = {k: v for k, v in torn.items()}

    # ---------------- F. 蒙特卡洛 ----------------
    banner("F  蒙特卡洛（3,000 次）+ 7 年生存期望 NPV")
    mcs = [monte_carlo(s, n=3000) for s in FORMATS]
    for m in mcs:
        print(f"  {m.name:<12} P(亏损)={m.p_loss*100:>5.1f}%"
              f"  P(业主现金流为负)={m.p_ruin*100:>5.1f}%"
              f"  中位EBITDA ${m.median_ebitda:>8,.0f}"
              f"  P10 ${m.p10:>9,.0f}  P90 ${m.p90:>9,.0f}"
              f"  CVaR10 ${m.cvar10:>9,.0f}")
        print(f"  {'':<12} 中位ROIC {m.median_roic*100:>6.1f}%"
              f"  中位NPV(7年) ${m.median_npv:>11,.0f}"
              f"  P(NPV>0)={m.p_npv_positive*100:>5.1f}%")
    RESULTS["monte_carlo"] = [
        {k: v for k, v in asdict(m).items()
         if k not in ("ebitda", "roic", "npv")} for m in mcs
    ]

    # ---------------- G. 内点最优 ----------------
    banner("G1  定价：隐含临界弹性与局部利润梯度")
    diags = [pricing_diagnostics(s) for s in FORMATS]
    for r in diags:
        d = r["local_delta"]
        print(f"  {r['name']:<12} ε_crit={r['eps_crit']:.2f}"
              f"  (假设 ε={r['eps_assumed']:.2f} → {r['verdict']})"
              f"  峰值利用率 {r['peak_utilization']*100:>3.0f}%"
              f"  每人次占座 {r['seat_hours_per_cover']:.2f}h"
              f"  食材/人次 ${r['food_per_cover']:.2f}")
        print(f"  {'':<12} ΔEBITDA:  −10% {d['-10%']:>+9,.0f}"
              f" | −5% {d['-5%']:>+9,.0f} | +5% {d['+5%']:>+9,.0f}"
              f" | +10% {d['+10%']:>+9,.0f}")
    RESULTS["pricing_diagnostics"] = diags

    banner("G2  桌型配比最优")
    mixes = [optimize_table_mix(s) for s in FORMATS]
    for r in mixes:
        b = r["best"]
        c = r["current"]
        print(f"  {r['name']:<12} 现配比 {c['mix']} φ={c['fill']:.3f}"
              f" 产能 {c['cph']:.1f}人次/h")
        print(f"  {'':<12} 最优 吧台×{b['n1']} 2人桌×{b['n2']} 4人桌×{b['n4']}"
              f" 6人桌×{b['n6']} ({b['tables']}桌+{b['n1']}吧台/{b['seats']}座)"
              f" φ={b['fill']:.3f} 产能 {b['cph']:.1f}人次/h"
              f"  → 提升 {r['gain_pct']:+.1f}%")
    RESULTS["table_mix"] = [
        {"name": r["name"], "best": r["best"], "current": r["current"],
         "gain_pct": r["gain_pct"]} for r in mixes
    ]

    banner("G3  面积内点最优")
    foots = [optimize_footprint(s) for s in FORMATS]
    for r in foots:
        be, br = r["best_ebitda"], r["best_roic"]
        print(f"  {r['name']:<12} 现 {[s for s in FORMATS if s.name==r['name']][0].total_sqft:.0f} sqft"
              f" | EBITDA最优 {be['sqft']:.0f} sqft ({be['seats']}座, ${be['ebitda']:,.0f}/月)"
              f" | ROIC最优 {br['sqft']:.0f} sqft (ROIC {br['roic']*100:.0f}%)")
    RESULTS["footprint"] = [
        {"name": r["name"], "best_ebitda": r["best_ebitda"],
         "best_roic": r["best_roic"], "rows": r["rows"]} for r in foots
    ]

    # ---------------- H. 变体业态 ----------------
    banner("H  变体业态：把结构性劣势工程化地修掉")
    cx = ayce_crossover(HOTPOT, HOTPOT_AYCE)
    print(f"  AYCE 在同一客流池下 ${cx['ayce_ebitda_at_ref']:,.0f}/月"
          f"  vs 单点火锅 ${cx['base_ebitda_at_ref']:,.0f}/月")
    print(f"  → AYCE 必须把客流从 M={REFERENCE_M:.0f} 拉到 M={cx['M_needed']}"
          f"（{cx['lift_required']*100:+.0f}%）才能追平单点火锅\n")
    RESULTS["ayce_crossover"] = cx

    for v in VARIANTS:
        f = simulate_table_dynamics(v).seat_fill
        p = profit_and_loss(v, REFERENCE_M, fill=f)
        base = {"火锅(自助 AYCE)": HOTPOT, "面馆(全自助/扫码)": NOODLE}[v.name]
        pb = profit_and_loss(base, REFERENCE_M,
                             fill=simulate_table_dynamics(base).seat_fill)
        print(f"  {v.name:<18} 收入 ${p.revenue_total:>9,.0f}"
              f"  EBITDA ${p.ebitda:>8,.0f} ({p.ebitda_margin*100:>5.1f}%)"
              f"  ROIC {p.roic*100:>6.1f}%   [原型 {base.name}: "
              f"${pb.ebitda:,.0f} / {pb.ebitda_margin*100:.1f}% / {pb.roic*100:.0f}%]")
    RESULTS["variants"] = [
        {"name": v.name,
         **{k: getattr(profit_and_loss(
             v, REFERENCE_M, fill=simulate_table_dynamics(v).seat_fill), k)
            for k in ("revenue_total", "ebitda", "ebitda_margin", "roic",
                      "margin_of_safety")}}
        for v in VARIANTS
    ]

    # ---------------- 图表 ----------------
    banner("生成图表")
    paths = []
    paths.append(charts.chart_cost_structure(pnls))
    paths.append(charts.chart_unit_economics(decomp))
    paths.append(charts.chart_demand_sweep(sweep, regimes, REFERENCE_M))
    paths.append(charts.chart_phase(m_grid, rent_grid, winner, names))
    # 用周末剖面：产能约束只在周末高峰真正咬合，工作日看不出差别
    days = [simulate_day(s, REFERENCE_M, fills[s.name], weekend=True)
            for s in FORMATS]
    paths.append(charts.chart_hourly(days, names, weekend_label="周末"))
    paths.append(charts.chart_montecarlo(mcs))
    paths.append(charts.chart_tornado(torn))

    fr = iso_profit_frontier()
    pts = []
    for k, (s, d) in enumerate(zip(FORMATS, decomp)):
        pts.append((s.name, s.cycle_min, s.check_dinner, d["goppash_max"]))
    paths.append(charts.chart_frontier(fr, pts))
    paths.append(charts.chart_footprint(foots))
    for p in paths:
        print(f"  ✓ {os.path.relpath(p)}")

    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(RESULTS, f, indent=1, ensure_ascii=False, default=str)
    print(f"\n  ✓ outputs/results.json")
    print(f"\n耗时 {time.time()-t0:.1f}s")


if __name__ == "__main__":
    sys.exit(main())
