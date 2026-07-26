"""
湾区中餐馆盈利效率模型 —— 参数层
==================================

本模块定义模型的全部外生参数。每个参数都标注了量纲、取值理由与不确定区间，
以便做敏感性分析与蒙特卡洛模拟。

参数校准的基准情景（Base Case）：
    地点   : 湾区南湾 / 东湾华人商圈（Cupertino / Milpitas / Fremont 一类的 plaza）
    时点   : 2026 年成本水平
    规模   : 10-15 张桌（题目给定约束）
    合规度 : 完全合规工资（W-2、加州无 tip credit）、市场租金、含业主机会成本

单位约定：
    金额   : 美元 USD
    时间   : 小时 hour（除非显式标注 min）
    面积   : 平方英尺 sqft
    周期   : 月 month（除非显式标注 /yr /day）
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# 全局宏观参数（三种业态共用）
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Macro:
    """湾区共同的宏观 / 制度性参数。"""

    # --- 劳动力 ---
    # 加州 2026 州最低工资约 $16.90；湾区各市地方最低工资更高
    # (SF ~$19.2, Mountain View ~$19.2, Sunnyvale ~$19.0, Cupertino/Palo Alto ~$18.2,
    #  San Jose ~$18.0, Fremont/Milpitas ~$17.8)。取南湾华人商圈中位数。
    min_wage: float = 18.50                # $/hr，前厅基础岗位实际支付工资
    # 雇主负担：FICA 7.65% + 加州餐饮 workers comp（class 9079/9080）约 4-7%
    # + SUI/ETT 约 1-2% + 带薪病假/其它约 3-4%
    payroll_burden: float = 0.20           # 占工资比例
    # 关键：加州【没有 tip credit】。服务员必须拿满最低工资，小费全额归员工。
    # 这是全服务业态在加州相对其它州结构性劣势的根源。
    tip_credit: float = 0.0

    # --- 租金 ---
    rent_psf_month: float = 4.25           # $/sqft/月，已含 NNN（CAM+地税+保险）
    rent_escalator: float = 0.03           # 年递增
    # NNN 部分单列以便敏感性分析（已包含在 rent_psf_month 内，仅作说明）
    nnn_share_of_rent: float = 0.28

    # --- 交易成本 ---
    sales_tax: float = 0.0925              # 圣塔克拉拉县合计销售税
    tip_rate: float = 0.16                 # 顾客平均小费率（刷卡手续费按含税含小费金额计）
    card_fee: float = 0.029                # 刷卡费率
    card_fee_fixed: float = 0.10           # $/笔
    card_share: float = 0.94               # 刷卡占比（湾区现金极少）

    # --- 外卖平台 ---
    # DoorDash/UberEats marketplace 抽成 15%-30%；自营网站 + 自送约 8%-12%
    delivery_commission: float = 0.22      # 混合抽成率

    # --- 资本成本 ---
    sba_rate: float = 0.1025               # SBA 7(a)：Prime(7.5%) + 2.75%
    loan_term_years: int = 10
    equity_share: float = 0.35             # 自有资金比例
    discount_rate: float = 0.16            # 小餐饮股权要求回报率（含失败风险溢价）
    lease_term_years: int = 7

    # --- 常被算漏的两项 ---
    # 维护性资本支出：餐饮设备寿命 5-8 年，必须按收入计提更新储备，
    # 否则第 4-5 年会突然出现 $60k 的冷库/排烟/洗碗机更换而现金流断裂。
    maintenance_capex_ratio: float = 0.018   # 占收入
    # 损耗：收银短溢、偷盗、报废、退菜。餐饮业普遍 0.5%-1.2%。
    shrinkage_ratio: float = 0.007           # 占收入

    # --- 业主机会成本 ---
    # 严谨核算必须计入：业主若不开店，在湾区从事同等强度工作的机会工资
    owner_opportunity_cost: float = 6000.0  # $/月

    # --- 运营日历 ---
    days_per_week: int = 6                 # 每周营业日（周一或周二休）
    weeks_per_year: float = 52.0

    @property
    def days_per_month(self) -> float:
        return self.days_per_week * self.weeks_per_year / 12.0

    @property
    def effective_card_fee(self) -> float:
        """刷卡费占【菜品净收入】的实际比例。

        刷卡金额 = 菜品 × (1 + 销售税 + 小费率)，而手续费只能从菜品收入里出。
        这是很多人算漏的一项：名义 2.9% 实际吃掉约 3.6%。
        """
        gross_multiple = 1.0 + self.sales_tax + self.tip_rate
        return self.card_fee * gross_multiple * self.card_share


MACRO = Macro()


# ---------------------------------------------------------------------------
# 时段需求形状
# ---------------------------------------------------------------------------

HOURS: List[int] = list(range(10, 23))  # 10:00 .. 22:00 共 13 个小时桶

# 湾区郊区华人商圈"通用餐饮客流"形状（与业态无关的商圈潜在需求）。
# 归一化后 × 市场强度 M（人次/日）= 各小时潜在到店人次。
GENERIC_TRAFFIC_WEEKDAY: Dict[int, float] = {
    10: 0.00, 11: 0.55, 12: 1.00, 13: 0.60, 14: 0.20, 15: 0.10, 16: 0.12,
    17: 0.45, 18: 0.95, 19: 0.85, 20: 0.45, 21: 0.18, 22: 0.05,
}
GENERIC_TRAFFIC_WEEKEND: Dict[int, float] = {
    10: 0.05, 11: 0.60, 12: 0.95, 13: 0.85, 14: 0.45, 15: 0.28, 16: 0.30,
    17: 0.70, 18: 1.10, 19: 1.15, 20: 0.85, 21: 0.45, 22: 0.18,
}

# 业态的"时段捕获系数"：同一批客流中，该业态在该时段能转化的比例（相对值）。
# 说明：这是【餐次场合适配】的结构性属性（火锅不适合 45 分钟工作日午餐），
# 不是题目要求排除的"受众差异/产品差异化"。
# analysis.py 中提供 uniform_capture=True 的严格对照组，把它们全部拉平。
CAPTURE_SICHUAN: Dict[int, float] = {
    10: 0.00, 11: 0.90, 12: 1.00, 13: 0.95, 14: 0.50, 15: 0.25, 16: 0.35,
    17: 0.90, 18: 1.00, 19: 1.00, 20: 0.85, 21: 0.40, 22: 0.10,
}
CAPTURE_NOODLE: Dict[int, float] = {
    10: 0.40, 11: 1.05, 12: 1.10, 13: 1.10, 14: 0.90, 15: 0.70, 16: 0.70,
    17: 0.90, 18: 0.90, 19: 0.85, 20: 0.70, 21: 0.50, 22: 0.25,
}
CAPTURE_HOTPOT: Dict[int, float] = {
    10: 0.00, 11: 0.25, 12: 0.35, 13: 0.30, 14: 0.15, 15: 0.10, 16: 0.20,
    17: 0.80, 18: 1.05, 19: 1.15, 20: 1.10, 21: 0.90, 22: 0.60,
}


# ---------------------------------------------------------------------------
# 业态规格
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FormatSpec:
    """单一业态的完整技术-经济规格。"""

    name: str
    name_en: str

    # ---- 物理空间 ----
    total_sqft: float                  # 承租总面积
    kitchen_sqft: float                # 后厨+仓储+卫生间+备餐（不随座位数缩放的刚性面积）
    seats: int                         # 座位数
    tables: int                        # 桌数
    table_mix: Dict[int, int]          # {每桌座位数: 桌数}

    # ---- 翻台物理学 ----
    dwell_min: float                   # 顾客占座时长（进店到离店），分钟
    turn_min: float                    # 清台+复位时间，分钟
    party_size_mean: float             # 平均同行人数
    party_size_sd: float

    # ---- 定价 ----
    check_lunch: float                 # 午市人均消费（税前、小费前）
    check_dinner: float                # 晚市人均消费
    bev_share: float                   # 酒水占客单比例
    bev_cost_ratio: float              # 酒水成本率

    # ---- 成本结构 ----
    food_cost_ratio: float             # 食材成本 / 菜品收入
    supplies_ratio: float              # 堂食易耗品（餐巾、调料台损耗等）
    packaging_ratio: float             # 外卖包装 / 外卖收入
    delivery_share: float              # 外卖占总收入比例

    # ---- 人力（岗位: (人数, 月薪) 或 (人数, 时薪, 每月工时)) ----
    boh_salaried: List[Tuple[str, float, float]]   # (岗位, 人数, 月薪)
    foh_hourly_hours: float            # 前厅每月总工时
    foh_wage_premium: float            # 前厅工资相对最低工资的溢价倍数

    # ---- 厨房产能 ----
    kitchen_covers_per_hour: float     # 后厨可持续出品人次/小时（独立于座位的约束）

    # ---- 设计产量（人力配置的标定点）----
    # 上面 boh_salaried / foh_hourly_hours 描述的是【该月人次达到此值时】的编制。
    # 引擎据此对人力做产量弹性缩放，避免高产量情景出现"用同样的人做三倍生意"的失真。
    design_covers_month: float

    # ---- 固定支出 ----
    utilities_month: float             # 水电气
    other_fixed_month: float           # 保险/POS/牌照/会计/营销/维修/清洁等

    # ---- 资本支出 ----
    capex: float                       # 装修+设备+押金+开办费（二手餐饮铺位）
    capex_shell_premium: float         # 若从毛坯改造额外增加

    # ---- 需求 ----
    capture: Dict[int, float]          # 时段捕获系数
    price_elasticity: float            # 需求价格弹性（绝对值）
    max_wait_min: float                # 顾客可忍受排队时长（决定削峰能力）

    # ---- 风险 ----
    key_person_risk: float             # 关键技术岗位不可替代性 0-1（炒锅师傅风险）
    annual_failure_hazard: float       # 年度倒闭风险率

    # ---- 便捷派生量 ----
    @property
    def cycle_min(self) -> float:
        """一次完整占座周期（用餐 + 清台）。"""
        return self.dwell_min + self.turn_min

    @property
    def cycle_hr(self) -> float:
        return self.cycle_min / 60.0

    @property
    def seat_fill(self) -> float:
        """座位填充率 φ = 平均同行人数 / 平均实际占用桌位数。

        由 table_mix 与 party_size 分布经贪心分配模拟得到（见 engine.simulate_fill）。
        此处给出解析近似，engine 会用模拟值覆盖。
        """
        avg_table = sum(k * v for k, v in self.table_mix.items()) / max(
            1, sum(self.table_mix.values())
        )
        # 一个 party 至少占一桌；若人数超过桌容量则并桌（向上取整到桌容量倍数）
        import math

        occupied = max(1.0, math.ceil(self.party_size_mean / avg_table)) * avg_table
        return min(1.0, self.party_size_mean / occupied)

    @property
    def seat_density(self) -> float:
        """σ = 座位数 / 承租平方英尺。"""
        return self.seats / self.total_sqft

    @property
    def sqft_per_seat(self) -> float:
        return self.total_sqft / self.seats

    def seat_capacity_cph(self, fill: float) -> float:
        """座位产能，人次/小时 = 座位数 × 填充率 / 周期(小时)。"""
        return self.seats * fill / self.cycle_hr

    def capacity_cph(self, fill: float) -> float:
        """实际产能 = min(座位产能, 后厨产能)。"""
        return min(self.seat_capacity_cph(fill), self.kitchen_covers_per_hour)


# ---------------------------------------------------------------------------
# 三种业态的基准参数
# ---------------------------------------------------------------------------

SICHUAN = FormatSpec(
    name="川湘菜馆",
    name_en="Sichuan/Hunan Full-Service",
    # 13 桌 / 54 座。堂食区 54×17=918 sqft（含过道），
    # 中厨需要炒炉线+打荷+凉菜+洗碗+走入式冷库，后厨/仓储/卫生间约 680 sqft
    total_sqft=1600,
    kitchen_sqft=680.0,
    seats=54,
    tables=13,
    table_mix={2: 2, 4: 8, 6: 3},   # 13 桌 = 4+32+18 = 54 座
    dwell_min=65.0,        # 中式全服务出菜快、顾客不久坐，显著短于西餐 90-110 分钟
    turn_min=8.0,
    party_size_mean=3.2,
    party_size_sd=1.4,
    check_lunch=25.0,      # 午市套餐拉低客单，这是常被忽略的结构
    check_dinner=48.0,     # 题目给定"人均 $50"，晚市取 $48
    bev_share=0.06,
    bev_cost_ratio=0.30,
    food_cost_ratio=0.30,
    supplies_ratio=0.010,
    packaging_ratio=0.045,
    delivery_share=0.25,   # 川湘菜适合外卖，湾区外卖占比高
    boh_salaried=[
        ("头锅师傅", 1, 6800.0),   # 湾区炒锅 $6k-8k/月，稀缺
        ("二锅/打荷", 1, 5000.0),
        ("凉菜/蒸菜/备料", 1, 4600.0),
        ("洗碗/杂工", 1, 3700.0),
    ],
    foh_hourly_hours=850.0,   # 服务员 ~637h + 收银/迎宾 ~213h
    foh_wage_premium=1.0,
    kitchen_covers_per_hour=62.0,
    design_covers_month=3000.0,  # 2 个炒炉 ≈ 70 道菜/小时 ≈ 15 桌/小时
    utilities_month=3000.0,        # 炒炉燃气 + 大排烟 + 补风，PG&E 费率高
    other_fixed_month=7100.0,   # 明细：保险850 POS650 会计600 牌照300 营销2000
                                #      维修1200 布草450 管道清洗/垃圾700 杂项350
    capex=340_000.0,
    capex_shell_premium=170_000.0,
    capture=CAPTURE_SICHUAN,
    price_elasticity=1.45,
    max_wait_min=35.0,
    key_person_risk=0.85,          # 炒锅师傅离职 = 味道变 = 客流崩
    annual_failure_hazard=0.155,
)

NOODLE = FormatSpec(
    name="面馆/小吃店",
    name_en="Noodle / Single-Item QSR",
    # 14 桌 / 44 座（2 人桌为主 + 吧台），堂食 44×14=616 sqft（快餐可加密）
    # 后厨仅需煮面档 + 卤味/汤桶 + 小备料 + 洗碗，约 450 sqft
    total_sqft=1100,
    kitchen_sqft=450.0,
    seats=44,
    tables=14,
    # 8 个吧台单座 + 8 张双人桌 + 5 张四人桌 = 44 座（13 张桌 + 吧台）
    # 单座吧台是面馆提升填充率 φ 的关键设计杠杆：单人客不再霸占双人桌
    table_mix={1: 8, 2: 8, 4: 5},
    dwell_min=28.0,
    turn_min=5.0,
    party_size_mean=1.9,      # 单人/双人为主 —— 面馆的结构性弱点
    party_size_sd=0.9,
    check_lunch=22.0,
    check_dinner=25.0,
    bev_share=0.05,
    bev_cost_ratio=0.25,
    food_cost_ratio=0.28,
    supplies_ratio=0.015,
    packaging_ratio=0.055,    # 汤面外带包装成本高
    delivery_share=0.20,      # 汤面外卖体验差，占比低于川菜
    boh_salaried=[
        ("面档主厨", 1, 5200.0),   # 技术门槛远低于炒锅
        ("出餐/组装", 1, 4200.0),
        ("备料", 1, 4000.0),
        ("洗碗(兼职)", 1, 2600.0),
    ],
    foh_hourly_hours=430.0,   # 柜台点单 / 自助取餐 —— 无完整服务员编制
    foh_wage_premium=1.0,
    kitchen_covers_per_hour=95.0,
    design_covers_month=3100.0,  # 多篮煮面机 + 预制卤味，产能远超座位产能
    utilities_month=1900.0,
    other_fixed_month=4900.0,   # 保险600 POS550 会计450 牌照250 营销1500
                                # 维修700 布草150 清洁/垃圾450 杂项250
    capex=235_000.0,
    capex_shell_premium=120_000.0,
    capture=CAPTURE_NOODLE,
    price_elasticity=1.85,    # 单品店可替代性高，价格更敏感
    max_wait_min=20.0,
    key_person_risk=0.35,
    annual_failure_hazard=0.135,
)

HOTPOT = FormatSpec(
    name="火锅店",
    name_en="Hot Pot",
    # 13 桌 / 52 座。火锅需要更宽过道、桌下电磁炉井、每桌独立下排烟，
    # 堂食 52×21=1092 sqft + 调料台 80 sqft；后厨无炒炉但需大冷库/切肉间/重洗碗 620 sqft
    total_sqft=1800,
    kitchen_sqft=700.0,
    seats=52,
    tables=12,
    table_mix={2: 1, 4: 8, 6: 3},   # 12 桌 = 2+32+18 = 52 座
    dwell_min=95.0,        # 结构性长占座 —— 火锅的核心矛盾
    turn_min=15.0,         # 涮锅清理 / 调料台复位 / 重新摆台
    party_size_mean=3.6,   # 群体聚餐属性最强，填充率最高
    party_size_sd=1.5,
    check_lunch=32.0,
    check_dinner=52.0,
    bev_share=0.12,        # 啤酒/饮料附加率最高，且毛利极好
    bev_cost_ratio=0.22,
    food_cost_ratio=0.37,  # 肉类为主，食材成本率结构性最高
    supplies_ratio=0.012,
    packaging_ratio=0.06,
    delivery_share=0.04,   # 基本不可外送（仅 DIY 锅底套装）
    boh_salaried=[
        ("切配/切肉", 2, 4400.0),   # 无需炒锅师傅 —— 火锅最大的成本优势
        ("锅底/备料", 1, 4400.0),
        ("洗碗/杂工", 1, 4000.0),   # 碗碟量极大
        ("洗碗(兼职)", 1, 1200.0),
    ],
    foh_hourly_hours=880.0,   # 火锅前厅重：加汤/上菜/调料台/摆撤台
    foh_wage_premium=1.0,
    kitchen_covers_per_hour=180.0,
    design_covers_month=2350.0,  # 只切配不烹饪，后厨几乎不构成约束
    utilities_month=4400.0,         # 13 桌电磁炉 + 强排烟补风 + 重洗碗 + 大冷库
    other_fixed_month=8900.0,   # 保险1100(明火/电磁炉责任险高) POS700 会计600
                                # 牌照350 营销2400 维修1800(电磁炉故障率高)
                                # 布草500 油烟管道清洗+垃圾1100 杂项350       # 电磁炉维修率高、抽油烟管道清洗频繁、保险高
    capex=480_000.0,                # 每桌独立排烟管道 $6-10k × 13 桌是大头
    capex_shell_premium=180_000.0,
    capture=CAPTURE_HOTPOT,
    price_elasticity=1.30,          # 聚餐场景，价格敏感度最低
    max_wait_min=55.0,              # 目的性消费，愿意等 —— 削峰能力最强
    key_person_risk=0.20,           # 无关键技术岗位，可复制性最好
    annual_failure_hazard=0.145,
)


FORMATS: List[FormatSpec] = [SICHUAN, NOODLE, HOTPOT]
FORMATS_BY_NAME: Dict[str, FormatSpec] = {f.name: f for f in FORMATS}


# ---------------------------------------------------------------------------
# 变体业态（用于扩展讨论）
# ---------------------------------------------------------------------------

# 自助火锅（AYCE）：固定价格 → 免去点单人力、锁定客单，
# 但食材成本率飙升；靠【强制时限】把 dwell 压回来 —— 教科书级的收益管理手段。
HOTPOT_AYCE = replace(
    HOTPOT,
    name="火锅(自助 AYCE)",
    name_en="Hot Pot (AYCE)",
    check_lunch=32.0,
    check_dinner=42.0,
    food_cost_ratio=0.455,
    dwell_min=82.0,          # 强制 90 分钟时限
    turn_min=13.0,
    foh_hourly_hours=760.0,  # 无需反复点单
    price_elasticity=1.55,
)

# 无服务员面馆：扫码点单 + 自助取餐 + 自助收餐，把加州"无 tip credit"
# 的结构性劣势降到最低。
NOODLE_LEAN = replace(
    NOODLE,
    name="面馆(全自助/扫码)",
    name_en="Noodle (Zero-Server)",
    foh_hourly_hours=260.0,
    dwell_min=25.0,
    turn_min=4.0,
    other_fixed_month=3600.0,   # POS/扫码点单订阅费略高
    capex=215_000.0,
)

VARIANTS: List[FormatSpec] = [HOTPOT_AYCE, NOODLE_LEAN]


# ---------------------------------------------------------------------------
# 一致性校验：table_mix 的座位总数必须等于 seats
# ---------------------------------------------------------------------------

def _validate() -> None:
    for f in FORMATS + VARIANTS:
        s_mix = sum(k * v for k, v in f.table_mix.items())
        assert s_mix == f.seats, (
            f"{f.name}: table_mix 座位数 {s_mix} != seats {f.seats}"
        )
        assert f.total_sqft > 0 and f.seats > 0
        assert 0 < f.kitchen_sqft < f.total_sqft
        assert 0 < f.food_cost_ratio < 1
        assert f.cycle_min > 0


_validate()
