"""
增强版布林带策略 - 目标：夏普比率>2
中低频，均值回归+趋势过滤
"""
import pandas as pd

# ==================== 参数配置 ====================
# 布林带参数
boll_window = 20          # 布林带窗口
boll_std_multiplier = 2.0  # 标准差倍数

# 趋势过滤
ma_trend_period = 60       # 趋势均线

# 止损止盈
stop_loss_pct = 0.04      # 止损4%
take_profit_pct = 0.12    # 止盈12%

# ==================== 全局变量 ====================
price_data = pd.Series()
entry_price = None
last_signal = None
in_position = False
position_direction = None

# ==================== 核心交易信号函数 ====================
def trade_signal(time, price):
    """
    增强版布林带策略
    
    逻辑：
    - 趋势过滤：价格在MA60之上只做多，之下只做空
    - 入场：价格触及布林带上下轨
    - 出场：价格回归中轨、止损、止盈
    """
    global price_data, entry_price, last_signal, in_position, position_direction
    
    price_data = pd.concat([price_data, pd.Series([price])])
    
    min_data_required = max(boll_window, ma_trend_period) + 10
    if len(price_data) < min_data_required:
        return None
    
    # 计算指标
    boll_mid = price_data.rolling(window=boll_window).mean().iloc[-1]
    boll_std = price_data.rolling(window=boll_window).std().iloc[-1]
    boll_upper = boll_mid + boll_std_multiplier * boll_std
    boll_lower = boll_mid - boll_std_multiplier * boll_std
    ma_trend = price_data.rolling(window=ma_trend_period).mean().iloc[-1]
    
    # 趋势判断
    uptrend = price > ma_trend
    downtrend = price < ma_trend
    
    if not in_position:
        # === 空仓 ===
        
        # 做多：上升趋势 + 价格触及下轨
        if uptrend and price < boll_lower:
            entry_price = price
            in_position = True
            position_direction = "做多"
            last_signal = "做多"
            return "做多"
        
        # 做空：下降趋势 + 价格触及上轨
        elif downtrend and price > boll_upper:
            entry_price = price
            in_position = True
            position_direction = "做空"
            last_signal = "做空"
            return "做空"
    
    else:
        # === 持仓 ===
        
        # 计算盈亏
        if position_direction == "做多":
            pnl_pct = (price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - price) / entry_price
        
        # 止损
        if pnl_pct < -stop_loss_pct:
            in_position = False
            position_direction = None
            return "平多" if last_signal == "做多" else "平空"
        
        # 止盈
        if pnl_pct > take_profit_pct:
            in_position = False
            position_direction = None
            return "平多" if last_signal == "做多" else "平空"
        
        # 回归中轨平仓
        if position_direction == "做多" and price > boll_mid:
            in_position = False
            position_direction = None
            last_signal = "平多"
            return "平多"
        elif position_direction == "做空" and price < boll_mid:
            in_position = False
            position_direction = None
            last_signal = "平空"
            return "平空"
    
    return None
