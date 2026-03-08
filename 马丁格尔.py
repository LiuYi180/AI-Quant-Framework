import pandas as pd
import numpy as np
import math

# ==========================
# 全局变量（必须存在且持久）
# ==========================
price_data = pd.Series(dtype=float)   # 历史价格
current_position = 0                  # 当前净多仓数量（单位：合约/手数），负数表示净空（本策略默认只用正）
avg_cost = 0.0                        # 当前持仓平均开仓价格（仅当 current_position != 0 有意义）
martingale_level = 0                  # 当前马丁层级：0 表示无持仓，1 表示已开基础仓，2 表示已加码一次，依此类推
last_signal = None                    # 记录上一个信号（防止无仓平仓等）
ticks_since_entry = 0                 # 自上次开仓起的 tick 计数（用于冷却/保护）

# ==========================
# 参数（可调）
# ==========================
params = {
    'sma_window': 20,                # 用来判断入场的均线窗口
    'entry_z_pct': 0.01,             # 价格低于 SMA 的百分比触发首仓（例如 0.01 = 1% 低于均线）
    'base_order_size': 1,            # 基础手数（首仓手数）
    'max_martingale_level': 5,       # 最大马丁层数（包含首仓），例如 5 层最多会下 5 次单（手数按翻倍）
    'stop_loss_pct': 0.10,           # 累计亏损超过该比例（相对平均成本）时全部平仓（例如 10%）
    'take_profit_pct': 0.015,        # 当均价盈利达到此比例时全部平仓（例如 1.5%）
    'loss_step_pct': 0.03,           # 相对平均成本下跌达到该阈值时触发下一层加码（例如 3%）
    'max_position_limit': 50,        # 绝对持仓上限（单位手数），防止爆仓
    'min_price_valid': 1e-8,
    'entry_cooldown_ticks': 1,       # 每次入场/加码后至少等待多少ticks再允许下一次入场（避免同tick连续下单）
}

# ==========================
# 辅助函数
# ==========================
def safe_float(x):
    try:
        return float(x)
    except:
        return None

def compute_avg_cost(existing_avg, existing_qty, fill_price, fill_qty):
    """
    计算加仓后的平均成本（当持仓全部为多时）
    """
    if existing_qty + fill_qty == 0:
        return 0.0
    return (existing_avg * existing_qty + fill_price * fill_qty) / (existing_qty + fill_qty)

# ==========================
# 主接口：trade_signal
# ==========================
def trade_signal(time, price):
    """
    Args:
        time: str, 时间戳，如 "2024-05-20 14:30:00 open"
        price: float, 当前价格
    Returns:
        one of: "做多","做空","平多","平空","不操作", None
    """
    global price_data, current_position, avg_cost, martingale_level, last_signal, ticks_since_entry

    # 基本校验
    p = safe_float(price)
    if p is None or math.isnan(p) or math.isinf(p) or p <= 0 or p < params['min_price_valid']:
        return "不操作"

    # 存历史（供均线等使用）
    price_data = pd.concat([price_data, pd.Series([p])])
    if len(price_data) < params['sma_window'] + 2:
        # 数据不足时不操作
        return "不操作"

    # 累计 ticks（每次函数调用认为为一次 tick）
    ticks_since_entry += 1

    # 计算 SMA 作为入场参考（只用过去数据）
    sma = price_data.rolling(window=params['sma_window']).mean().iloc[-1]
    if math.isnan(sma):
        return "不操作"

    # 计算当前相对均价的浮动
    if current_position != 0:
        unrealized_return = (p - avg_cost) / (avg_cost + 1e-12)   # 正数表示盈利
    else:
        unrealized_return = 0.0

    # 优先级 1：止盈（当盈利达到 take_profit_pct -> 全部平仓并重置）
    if current_position > 0 and unrealized_return >= params['take_profit_pct']:
        # 平掉所有多仓
        current_position = 0
        avg_cost = 0.0
        martingale_level = 0
        last_signal = "平多"
        ticks_since_entry = 0
        return "平多"

    # 优先级 1b：止损（累计亏损超 stop_loss_pct）
    if current_position > 0 and unrealized_return <= -params['stop_loss_pct']:
        # 立即全部平仓，重置马丁
        current_position = 0
        avg_cost = 0.0
        martingale_level = 0
        last_signal = "平多"
        ticks_since_entry = 0
        return "平多"

    # 如果当前没有仓位：判断是否开启首仓（基于 SMA 下方一定比例）
    if current_position == 0:
        # 要求满足价格位于 SMA 下方若干比例（均值回归风格入场）
        if p <= sma * (1 - params['entry_z_pct']) and ticks_since_entry >= params['entry_cooldown_ticks']:
            # 下首仓
            order_qty = params['base_order_size']
            # 更新持仓与均价
            current_position += order_qty
            avg_cost = p  # 首仓均价
            martingale_level = 1
            last_signal = "做多"
            ticks_since_entry = 0
            return "做多"
        else:
            return "不操作"

    # 若已有多仓，判断是否加码（马丁）
    if current_position > 0:
        # 如果已达到最大马丁层数或持仓上限，不再加码
        if martingale_level >= params['max_martingale_level'] or current_position >= params['max_position_limit']:
            return "不操作"

        # 当价格相对 avg_cost 下跌到下一层阈值时进行加码
        # 比如 loss_step_pct = 0.03 表示相对均价下跌 3% 时触发下层
        if (avg_cost - p) / (avg_cost + 1e-12) >= params['loss_step_pct'] and ticks_since_entry >= params['entry_cooldown_ticks']:
            # 计算下层下单手数：马丁规则通常是翻倍（2^(level-1) * base）
            next_level = martingale_level + 1
            next_order_qty = params['base_order_size'] * (2 ** (next_level - 1))
            # 限制下一下单不超过 position limit
            allowable_qty = params['max_position_limit'] - current_position
            if allowable_qty <= 0:
                return "不操作"
            order_qty = min(next_order_qty, allowable_qty)
            # 执行加码（这里只返回“做多”，实际平台下单量为 order_qty）
            # 更新 avg_cost 与持仓
            new_avg = compute_avg_cost(avg_cost, current_position, p, order_qty)
            current_position += order_qty
            avg_cost = new_avg
            martingale_level = next_level
            last_signal = "做多"
            ticks_since_entry = 0
            return "做多"
        else:
            # 未到加码阈值，且当前未触发平仓/止盈 -> 不操作
            return "不操作"

    # 其它情况一律不操作（该策略不做空）
    return "不操作"
