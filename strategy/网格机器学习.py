# mean_reversion_vol_adaptive.py
# 接口要求：trade_signal(time, price)
# 原理：均值回归 + ATR 波动率自适应 + ADX 趋势过滤（只在弱趋势/震荡时交易）

import pandas as pd
import numpy as np
import math

# -----------------------
# 全局变量（引擎要求）
# -----------------------
price_data = pd.Series(dtype=float)    # 存历史收盘价（或tick价）
high_data = pd.Series(dtype=float)     # 仅当有高价时可用（若无，同price）
low_data = pd.Series(dtype=float)      # 仅当有低价时可用（若无，同price）

max_keep = 10000        # 保留历史上限，防止无限增长

# 仓位/信号状态
last_signal = None      # 记录上一次返回的信号
position = "空仓"       # "多"/"空"/"空仓"

# 策略参数（可调）
ma_window = 50             # 短期均线窗口（用于均值）
z_window = 50              # 计算 z-score 的窗口（通常与 ma_window 相同）
atr_window = 14            # ATR 窗口
adx_window = 14            # ADX 窗口
z_entry = 1.3              # z-score 入场阈值（>0 表示价格偏离）
z_exit = 0.4               # z-score 平仓阈值（回归到接近均线）
adx_trend_threshold = 25   # ADX > 此值认为趋势强，禁用均值回归
min_required = max(ma_window, z_window, atr_window, adx_window) + 1

# 价格合法性
min_price_valid = 1e-6

# -----------------------
# 工具函数：指标计算（均使用过去数据，不使用未来）
# -----------------------
def simple_ma(series, window):
    return series.rolling(window=window).mean()

def rolling_std(series, window):
    return series.rolling(window=window).std()

def true_range(high, low, close):
    # high, low, close are pandas Series with aligned indices
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr

def atr(high, low, close, window):
    tr = true_range(high, low, close)
    return tr.rolling(window=window).mean()

def adx(high, low, close, window):
    # Returns ADX series (positive values). Implementation based on Wilder's smoothing.
    # Compute +DM and -DM
    up = high.diff()
    down = -low.diff()
    plus_dm = ((up > down) & (up > 0)) * up
    minus_dm = ((down > up) & (down > 0)) * down

    tr = true_range(high, low, close)
    # Wilder smoothing (recursive). We implement via rolling sums to keep simplicity (approx).
    atr_val = tr.rolling(window=window).mean()
    # smooth DM
    plus_dm_smooth = plus_dm.rolling(window=window).mean()
    minus_dm_smooth = minus_dm.rolling(window=window).mean()

    plus_di = 100.0 * plus_dm_smooth / (atr_val.replace(0, np.nan))
    minus_di = 100.0 * minus_dm_smooth / (atr_val.replace(0, np.nan))
    dx = ( (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) ) * 100.0
    adx_val = dx.rolling(window=window).mean()
    return adx_val

# -----------------------
# 主接口函数：trade_signal
# -----------------------
def trade_signal(time, price):
    """
    Args:
        time: str timestamp like "2024-05-20 14:30:00 open"
        price: float current price
    Returns:
        one of: "做多","做空","平多","平空","不操作", None
    """
    global price_data, high_data, low_data, last_signal, position

    # 基本校验
    if price is None or (not isinstance(price, (float, int))) or price <= 0 or price < min_price_valid:
        return "不操作"

    # 将当前价追加到历史（high/low 使用价格近似，如无高低）
    price_f = float(price)
    price_data = pd.concat([price_data, pd.Series([price_f])])
    high_data = pd.concat([high_data, pd.Series([price_f])])
    low_data = pd.concat([low_data, pd.Series([price_f])])

    # 裁剪历史长度
    if len(price_data) > max_keep:
        price_data = price_data.iloc[-max_keep:]
        high_data = high_data.iloc[-max_keep:]
        low_data = low_data.iloc[-max_keep:]

    # 数据量不足时返回不操作
    if len(price_data) < min_required:
        return "不操作"

    # 计算指标（均使用已存在数据，不使用未来信息）
    close = price_data
    high = high_data
    low = low_data

    ma = simple_ma(close, ma_window).iloc[-1]
    ma_series = simple_ma(close, ma_window)
    # z-score: (price - ma) / rolling_std
    roll_std = rolling_std(close, z_window).iloc[-1]
    if pd.isna(ma) or pd.isna(roll_std) or roll_std == 0:
        return "不操作"

    zscore = (price_f - ma) / roll_std

    # ATR（波动性）用于自适应阈值（如果ATR非常大，放宽入场阈值）
    atr_val = atr(high, low, close, atr_window).iloc[-1]
    if pd.isna(atr_val) or atr_val <= 0:
        # fallback to standard thresholds
        atr_scale = 1.0
    else:
        # normalize by price to convert to ratio
        atr_scale = atr_val / price_f
        # keep scale reasonable
        atr_scale = max(0.2, min(3.0, 0.5 / atr_scale))  # a heuristic scaling factor

    # ADX 趋势强度过滤
    adx_val = adx(high, low, close, adx_window).iloc[-1]
    if pd.isna(adx_val):
        adx_val = 0.0

    # 自适应入场/出场阈值（受ATR影响）
    entry_threshold = z_entry * atr_scale
    exit_threshold = z_exit * atr_scale

    # 决策逻辑：
    # - 如果 ADX 高于阈值（强趋势），不做均值回归（返回不操作或平仓）
    # - 否则：当 zscore > entry_threshold (价格显著高于均线) -> 开空（做空回归）
    #           when zscore < -entry_threshold -> 开多
    # - 平仓：当持仓且 zscore 回归到 exit_threshold 区间时平仓
    signal = "不操作"

    # Trend filter: in strong trend disable new entries and try to avoid being against trend
    in_strong_trend = adx_val > adx_trend_threshold

    # If in strong trend, we prefer to close mean-reversion positions
    if in_strong_trend:
        # if currently holding mean-reversion position, try to close safely
        if position == "多":
            signal = "平多"
            position = "空仓"
            last_signal = signal
            return signal
        elif position == "空":
            signal = "平空"
            position = "空仓"
            last_signal = signal
            return signal
        else:
            # no new entries in strong trend
            return "不操作"

    # Not in strong trend: normal mean-reversion behavior
    # Entry conditions
    if zscore > entry_threshold:
        # price significantly above mean -> expect reversion down -> open 空 (short)
        if position != "空":
            signal = "做空"
            position = "空"
        else:
            signal = "不操作"
    elif zscore < -entry_threshold:
        # price significantly below mean -> expect reversion up -> open 多 (long)
        if position != "多":
            signal = "做多"
            position = "多"
        else:
            signal = "不操作"
    else:
        # Check exit conditions: if currently in position and zscore back within exit threshold -> close
        if position == "多" and zscore > -exit_threshold:
            signal = "平多"
            position = "空仓"
        elif position == "空" and zscore < exit_threshold:
            signal = "平空"
            position = "空仓"
        else:
            signal = "不操作"

    last_signal = signal
    return signal
