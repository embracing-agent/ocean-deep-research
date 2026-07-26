"""图表输出。静态 PNG，供报告嵌入。

配色取自校验通过的三槽分类色板（blue / orange / aqua）：
全对 CVD ΔE 9.2、常视 ΔE 24.0 均达标；aqua 对浅色底对比度 2.74 < 3:1，
按 relief 规则一律附直接标注 + 图例，identity 不单靠颜色。
"""

from __future__ import annotations

import math
import os
from typing import Dict, List, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, patches
from matplotlib.colors import ListedColormap

# --- CJK 字体 ---
for _p in ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",):
    if os.path.exists(_p):
        font_manager.fontManager.addfont(_p)
plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
INK3 = "#8a8880"
GRID = "#e6e5e1"

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]        # 川湘 / 面馆 / 火锅
COST_RAMP = ["#0d3f78", "#1b5fa8", "#2a78d6", "#5f9ce2", "#95bdec", "#c4d9f5"]
GOOD, BAD = "#1baf7a", "#e34948"

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "outputs")


def _style(ax, title=None, xlabel=None, ylabel=None, grid_axis="y"):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.9, zorder=0)
        ax.set_axisbelow(True)
    if title:
        ax.set_title(title, color=INK, fontsize=12.5, pad=12, loc="left",
                     fontweight="bold")
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2, fontsize=10)


def _fig(w, h):
    fig, ax = plt.subplots(figsize=(w, h), facecolor=SURFACE)
    return fig, ax


def _save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=155, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return path


def _money(v, unit="k"):
    return f"${v/1000:,.0f}k" if unit == "k" else f"${v:,.0f}"


# ---------------------------------------------------------------------------
# 图 1  成本结构
# ---------------------------------------------------------------------------

def chart_cost_structure(pnls) -> str:
    fig, ax = _fig(10.2, 4.6)
    labels = ["食材成本", "人力成本", "租金", "水电气", "平台抽成+包装",
              "其它经营费用"]
    names = [p.spec_name for p in pnls]
    y = list(range(len(pnls)))[::-1]

    rows = []
    for p in pnls:
        r = p.revenue_total
        rows.append([
            p.cogs / r, p.labor_total / r, p.rent / r, p.utilities / r,
            (p.delivery_commission + p.packaging) / r,
            (p.other_fixed + p.supplies + p.shrinkage + p.maintenance_capex
             + p.owner_cost) / r,
        ])

    left = [0.0] * len(pnls)
    for k, lab in enumerate(labels):
        vals = [row[k] for row in rows]
        ax.barh(y, vals, left=left, height=0.52, color=COST_RAMP[k],
                label=lab, zorder=3, edgecolor=SURFACE, linewidth=2)
        for i, (v, l) in enumerate(zip(vals, left)):
            if v > 0.045:
                ax.text(l + v / 2, y[i], f"{v*100:.0f}", ha="center",
                        va="center", color="#ffffff" if k < 3 else INK,
                        fontsize=8.5, zorder=4)
        left = [a + b for a, b in zip(left, vals)]

    for i, p in enumerate(pnls):
        m = p.ebitda_margin
        ax.barh(y[i], max(0.0, m), left=left[i], height=0.52,
                color=GOOD if m > 0 else BAD, zorder=3,
                edgecolor=SURFACE, linewidth=2)
        ax.text(min(1.02, left[i] + max(0.0, m)) + 0.012, y[i],
                f"EBITDA {m*100:+.1f}%", va="center", ha="left",
                color=GOOD if m > 0 else BAD, fontsize=10, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels([f"{n}\n{_money(p.revenue_total)}/月"
                        for n, p in zip(names, pnls)],
                       color=INK, fontsize=10)
    ax.set_xlim(0, 1.24)
    ax.set_xticks([0, .2, .4, .6, .8, 1.0])
    ax.set_xticklabels(["0", "20%", "40%", "60%", "80%", "100%"])
    _style(ax, "成本结构对比（占总收入比例，基准情景 M=120）", grid_axis="x")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.12), ncol=6,
              frameon=False, fontsize=8.8, labelcolor=INK2, handlelength=1.1,
              columnspacing=1.2)
    fig.text(0.5, -0.10,
             "数字为占总收入百分比。「其它经营费用」含业主机会成本 $6,000/月、"
             "维护性资本支出计提与损耗",
             ha="center", fontsize=8.2, color=INK3)
    return _save(fig, "fig01_cost_structure.png")


# ---------------------------------------------------------------------------
# 图 2  单位经济学三因子
# ---------------------------------------------------------------------------

def chart_unit_economics(decomp: List[Dict]) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.0), facecolor=SURFACE)
    names = [d["name"] for d in decomp]
    panels = [
        ("每人次贡献毛利", [d["contrib_per_cover"] for d in decomp], "$", 1),
        ("每座位小时贡献 GOPPASH", [d["goppash_max"] for d in decomp], "$", 1),
        ("每平方英尺小时贡献", [d["contrib_per_sqft_hour"] for d in decomp], "$", 3),
    ]
    for ax, (title, vals, pre, dec) in zip(axes, panels):
        x = range(len(vals))
        ax.bar(x, vals, width=0.56, color=SERIES, zorder=3)
        for i, v in enumerate(vals):
            ax.text(i, v * 1.03, f"{pre}{v:,.{dec}f}", ha="center", va="bottom",
                    color=INK, fontsize=10, fontweight="bold")
        ax.set_xticks(list(x))
        ax.set_xticklabels([n.replace("/", "\n") for n in names], fontsize=9,
                           color=INK)
        ax.set_ylim(0, max(vals) * 1.22)
        _style(ax, title)
    fig.suptitle("满产条件下的三层单位经济学：换一个分母，冠军就换人",
                 color=INK, fontsize=13, fontweight="bold", x=0.06, ha="left",
                 y=1.03)
    fig.text(0.06, -0.05,
             "口径：晚市客单价，扣除食材/酒水成本、刷卡手续费、易耗品、损耗与维护性资本支出计提；满产（座位 100% 周转）",
             fontsize=8.5, color=INK3)
    fig.tight_layout()
    return _save(fig, "fig02_unit_economics.png")


# ---------------------------------------------------------------------------
# 图 3  需求扫描
# ---------------------------------------------------------------------------

def chart_demand_sweep(sweep: Dict[str, List], regimes: List[Dict],
                       ref_m: float) -> str:
    fig, ax = _fig(10.2, 5.2)
    for k, (name, curve) in enumerate(sweep.items()):
        xs = [c[0] for c in curve]
        ys = [c[1] / 1000.0 for c in curve]
        ax.plot(xs, ys, color=SERIES[k], linewidth=2.0, zorder=4, label=name)
        ax.text(xs[-1] + 4, ys[-1], name, color=SERIES[k], fontsize=10,
                va="center", fontweight="bold")

    ax.axhline(0, color=INK2, linewidth=1.1, zorder=2)
    ax.axvline(ref_m, color=INK3, linewidth=1.0, linestyle=(0, (4, 3)), zorder=2)
    ax.text(ref_m + 4, ax.get_ylim()[1] * 0.94, f"基准情景 M={ref_m:.0f}",
            color=INK2, fontsize=9)

    for k, r in enumerate(regimes):
        if r["M_breakeven"] == r["M_breakeven"]:
            ax.plot([r["M_breakeven"]], [0], "o", color=SERIES[k], markersize=8,
                    markeredgecolor=SURFACE, markeredgewidth=2, zorder=6)
            ax.annotate(f"盈亏平衡 M={r['M_breakeven']:.0f}",
                        (r["M_breakeven"], 0), textcoords="offset points",
                        xytext=(2, -20 - k * 13), fontsize=8.6, color=SERIES[k])

    _style(ax, "经营杠杆：EBITDA 对商圈需求密度的响应",
           xlabel="商圈需求密度 M（潜在到店人次/日）", ylabel="月 EBITDA（千美元）")
    ax.legend(loc="upper left", frameon=False, fontsize=9.5, labelcolor=INK2)
    ax.set_xlim(min(min(c[0] for c in cv) for cv in sweep.values()),
                max(max(c[0] for c in cv) for cv in sweep.values()) * 1.10)
    fig.text(0.09, -0.02,
             "曲线在高需求端变平 = 座位产能触顶；斜率 = 每增加一位潜在客人带来的边际利润",
             fontsize=8.5, color=INK3)
    return _save(fig, "fig03_demand_sweep.png")


# ---------------------------------------------------------------------------
# 图 4  相位图
# ---------------------------------------------------------------------------

def chart_phase(m_grid, rent_grid, winner, names, metric_label="ROIC") -> str:
    fig, ax = _fig(9.6, 5.4)
    cmap = ListedColormap(["#efeeea"] + SERIES)
    data = [[w + 1 for w in row] for row in winner]
    ax.imshow(data, cmap=cmap, vmin=0, vmax=3, origin="lower", aspect="auto",
              extent=[m_grid[0], m_grid[-1], rent_grid[0], rent_grid[-1]],
              interpolation="nearest", alpha=0.92, zorder=2)

    # 区域直接标注放在各自胜出区域的重心（relief 规则：identity 不单靠颜色）
    regions: Dict[int, List] = {}
    for i, r in enumerate(rent_grid):
        for j, m in enumerate(m_grid):
            regions.setdefault(winner[i][j], []).append((m, r))
    for w, cells in regions.items():
        if len(cells) < 0.03 * len(m_grid) * len(rent_grid):
            continue
        cx = sum(c[0] for c in cells) / len(cells)
        cy = sum(c[1] for c in cells) / len(cells)
        label = names[w] if w >= 0 else "三者皆亏损"
        ax.text(cx, cy, label, color="#ffffff" if w >= 0 else INK2,
                fontsize=11.5, fontweight="bold", ha="center", va="center",
                zorder=5, rotation=0 if w >= 0 else 90)

    _style(ax, f"最优业态相位图：argmax {metric_label} = f(需求密度, 租金)",
           xlabel="商圈需求密度 M（潜在到店人次/日）",
           ylabel="租金（$/平方英尺/月，含 NNN）", grid_axis=None)
    handles = [patches.Patch(facecolor=SERIES[k], label=n)
               for k, n in enumerate(names)]
    handles.append(patches.Patch(facecolor="#efeeea", label="三者皆亏损"))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.14),
              ncol=4, frameon=False, fontsize=9, labelcolor=INK2)
    return _save(fig, "fig04_phase_diagram.png")


# ---------------------------------------------------------------------------
# 图 5  时段剖面
# ---------------------------------------------------------------------------

def chart_hourly(days, names, weekend_label="工作日") -> str:
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.7), facecolor=SURFACE,
                             sharey=False)
    for k, (ax, d, name) in enumerate(zip(axes, days, names)):
        hs = sorted(d.hourly_potential.keys())
        open_hs = [h for h in hs if d.hourly_capacity[h] > 0]
        pot = [d.hourly_potential[h] for h in hs]
        srv = [d.hourly_served[h] for h in hs]
        cap = d.hourly_capacity[open_hs[0]]

        # 潜在需求画描边（未被服务的部分才看得出来），实际服务画实心
        ax.bar(hs, pot, width=0.72, facecolor="none", edgecolor="#a9a7a0",
               linewidth=1.2, zorder=3, label="潜在需求")
        ax.bar(hs, srv, width=0.72, color=SERIES[k], zorder=4, label="实际服务")
        ax.hlines(cap, open_hs[0] - 0.5, open_hs[-1] + 0.5, color=BAD,
                  linewidth=1.8, zorder=5, label="座位产能上限")
        ax.text(open_hs[0] - 0.3, cap, f" 产能 {cap:.0f}", color=BAD,
                fontsize=8.5, va="bottom", ha="left", zorder=6)

        ax.set_xticks([11, 13, 15, 17, 19, 21])
        ax.set_xticklabels(["11", "13", "15", "17", "19", "21"])
        ax.set_ylim(0, max(max(pot), cap) * 1.22)
        _style(ax, name)
        ax.set_xlabel("时刻", color=INK2, fontsize=9)
        if k == 0:
            ax.set_ylabel("人次/小时", color=INK2, fontsize=9)
        lost = d.lost_covers
        overflow = sum(max(0.0, p_ - cap) for p_ in pot)
        peak = max(srv[i] / cap for i in range(len(hs)) if cap > 0)
        note = f"峰值利用率 {peak*100:.0f}%\n高峰溢出 {overflow:.0f} 人次"
        if overflow > 0.5:
            note += f"（排队消化 {overflow - lost:.0f}，流失 {lost:.0f}）"
        ax.text(0.98, 1.005, note, transform=ax.transAxes, ha="right",
                va="bottom", fontsize=8.6, linespacing=1.6,
                color=BAD if overflow > 0.5 else INK3, fontweight="bold")
    h, lb = axes[0].get_legend_handles_labels()
    fig.legend(h, lb, loc="lower center", bbox_to_anchor=(0.5, -0.13), ncol=3,
               frameon=False, fontsize=9, labelcolor=INK2,
               handlelength=1.4, columnspacing=2.0)
    fig.suptitle(f"{weekend_label}时段剖面：需求集中在两个窄窗口，产能过剩与产能不足同时存在",
                 color=INK, fontsize=12.5, fontweight="bold", x=0.045,
                 ha="left", y=1.10)
    fig.tight_layout()
    return _save(fig, "fig05_hourly_profile.png")


# ---------------------------------------------------------------------------
# 图 6  蒙特卡洛
# ---------------------------------------------------------------------------

def chart_montecarlo(mcs) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.3), facecolor=SURFACE)

    ax = axes[0]
    lo = min(min(m.ebitda) for m in mcs)
    hi = max(_p(m.ebitda, 0.985) for m in mcs)
    lo = max(lo, -90000)
    bins = [lo + (hi - lo) * i / 46 for i in range(47)]
    for k, m in enumerate(mcs):
        ax.hist([x for x in m.ebitda if lo <= x <= hi], bins=bins,
                histtype="step", linewidth=1.9, color=SERIES[k], zorder=4,
                label=m.name)
    ax.axvline(0, color=INK2, linewidth=1.2, zorder=5)
    ax.text(0, ax.get_ylim()[1] * 0.98, " 盈亏平衡", color=INK2, fontsize=9,
            va="top")
    _style(ax, "月 EBITDA 的概率分布（3,000 次模拟）",
           xlabel="月 EBITDA（美元）", ylabel="频次")
    ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=INK2)

    ax = axes[1]
    x = range(len(mcs))
    vals = [m.p_loss * 100 for m in mcs]
    ax.bar(x, vals, width=0.5, color=SERIES[: len(mcs)], zorder=3)
    for i, (v, m) in enumerate(zip(vals, mcs)):
        ax.text(i, v + 1.2, f"{v:.0f}%", ha="center", color=INK, fontsize=11,
                fontweight="bold")
        ax.text(i, v + 6.0, f"中位 {_money(m.median_ebitda)}/月",
                ha="center", color=INK2, fontsize=8.5)
        ax.text(i, v + 9.5, f"最差10% 均值 {_money(m.cvar10)}/月",
                ha="center", color=INK3, fontsize=8.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels([m.name.replace("/", "\n") for m in mcs], fontsize=9.5,
                       color=INK)
    ax.set_ylim(0, max(vals) * 1.75 + 8)
    _style(ax, "亏损概率 P(EBITDA < 0)")
    ax.set_ylabel("概率", color=INK2, fontsize=10)
    fig.text(0.045, -0.04,
             "不确定性来源：需求强度 lognormal σ=0.42、客单 ±8%、食材成本率 ±10%、"
             "用餐时长 ±10%、租金 ±12%、工资 ±8%、装修超支 lognormal σ=0.22",
             fontsize=8.3, color=INK3)
    fig.tight_layout()
    return _save(fig, "fig06_montecarlo.png")


def _p(xs, q):
    ys = sorted(xs)
    k = q * (len(ys) - 1)
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return ys[lo] + (ys[hi] - ys[lo]) * (k - lo)


# ---------------------------------------------------------------------------
# 图 7  敏感性
# ---------------------------------------------------------------------------

def chart_tornado(rows_by_format: Dict[str, List[Dict]]) -> str:
    n = len(rows_by_format)
    fig, axes = plt.subplots(1, n, figsize=(4.3 * n, 4.6), facecolor=SURFACE)
    if n == 1:
        axes = [axes]
    for k, (ax, (name, rows)) in enumerate(zip(axes, rows_by_format.items())):
        rows = rows[:9][::-1]
        y = list(range(len(rows)))
        base = rows[0]["base"]
        for i, r in enumerate(rows):
            ax.barh(i, (r["high"] - base) / 1000, left=0, height=0.6,
                    color=SERIES[k], zorder=3)
            ax.barh(i, (r["low"] - base) / 1000, left=0, height=0.6,
                    color=SERIES[k], alpha=0.42, zorder=3)
        ax.axvline(0, color=INK2, linewidth=1.1, zorder=5)
        ax.set_yticks(y)
        ax.set_yticklabels([f"{r['label']} ±{r['amp']*100:.0f}%" for r in rows],
                           fontsize=8.8, color=INK)
        _style(ax, name, grid_axis="x")
        ax.set_xlabel("月 EBITDA 变动（千美元）", color=INK2, fontsize=9)
    fig.suptitle("敏感性：谁真正决定这门生意的死活（深色=参数上调，浅色=参数下调）",
                 color=INK, fontsize=12.5, fontweight="bold", x=0.045,
                 ha="left", y=1.04)
    fig.tight_layout()
    return _save(fig, "fig07_tornado.png")


# ---------------------------------------------------------------------------
# 图 8  等贡献前沿
# ---------------------------------------------------------------------------

def chart_frontier(curves, points) -> str:
    fig, ax = _fig(9.4, 5.4)
    XLO, XHI, YHI = 10.0, 130.0, 78.0
    ramp = ["#c4d9f5", "#95bdec", "#5f9ce2", "#2a78d6"]
    for k, (g, pts) in enumerate(sorted(curves.items())):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, color=ramp[min(k, 3)], linewidth=1.7, zorder=3)
        # 标签贴在射线离开可视区之前的最后一点上，而不是曲线数据的末端
        inside = [(x, y) for x, y in zip(xs, ys) if y <= YHI - 4 and x <= XHI]
        if inside:
            lx, ly = inside[-1]
            ax.text(lx + 1.5, ly, f"${g:.0f}/座位·小时",
                    color=ramp[min(k, 3)], fontsize=8.8, ha="left",
                    va="center", fontweight="bold", zorder=4)

    for k, (name, d, p, g) in enumerate(points):
        ax.plot([d], [p], "o", markersize=11, color=SERIES[k],
                markeredgecolor=SURFACE, markeredgewidth=2.2, zorder=6)
        dx, dy, ha = (12, -18, "left") if k != 2 else (-12, -18, "right")
        ax.annotate(f"{name}  ${g:.1f}/座位·小时", (d, p),
                    textcoords="offset points", xytext=(dx, dy), fontsize=9.5,
                    ha=ha, color=SERIES[k], fontweight="bold", zorder=6)

    _style(ax, "等贡献前沿：可行业态落在过原点的射线族上",
           xlabel="占座时长 d + 清台 τ（分钟）", ylabel="人均消费（美元，税前）")
    ax.set_xlim(XLO, XHI)
    ax.set_ylim(0, YHI)
    fig.text(0.09, -0.02,
             "同一条射线上的所有 (客单价, 占座时长) 组合，在座位受限时盈利效率完全等价 ——"
             r"\$25 / 30 分钟的面  ≡  \$50 / 60 分钟的川菜",
             fontsize=8.6, color=INK3)
    return _save(fig, "fig08_frontier.png")


# ---------------------------------------------------------------------------
# 图 9  面积最优
# ---------------------------------------------------------------------------

def chart_footprint(results) -> str:
    fig, ax = _fig(9.6, 4.8)
    for k, r in enumerate(results):
        xs = [row["sqft"] for row in r["rows"]]
        ys = [row["ebitda"] / 1000 for row in r["rows"]]
        ax.plot(xs, ys, color=SERIES[k], linewidth=2.0, zorder=4, label=r["name"])
        b = r["best_ebitda"]
        ax.plot([b["sqft"]], [b["ebitda"] / 1000], "o", markersize=9,
                color=SERIES[k], markeredgecolor=SURFACE, markeredgewidth=2,
                zorder=6)
        ax.annotate(f"{r['name']} 最优 {b['sqft']:.0f} sqft",
                    (b["sqft"], b["ebitda"] / 1000),
                    textcoords="offset points", xytext=(8, 8), fontsize=9,
                    color=SERIES[k], fontweight="bold")
    ax.axhline(0, color=INK2, linewidth=1.1, zorder=2)
    _style(ax, "面积存在内点最优：太小丢客，太大被租金和值班底薪吃掉（M=120）",
           xlabel="承租面积（平方英尺）", ylabel="月 EBITDA（千美元）")
    ax.legend(loc="lower right", frameon=False, fontsize=9.5, labelcolor=INK2)
    return _save(fig, "fig09_footprint.png")
