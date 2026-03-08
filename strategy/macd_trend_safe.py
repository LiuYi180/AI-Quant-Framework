"""
安全版MACD趋势策略 - 目标：夏普比率>2
中低频，带多重过滤
"""
import pandas as pd

# ==================== 参数配置 ====================
# MACD参数
macd_fast = 12
macd_slow = 26
macd_signal = 9

# 均线过滤
ma_period = 50

# 止损止盈
stop_loss_pct = 0.06
take_profit_pct = 0.18

# ==================== 全局变量 ====================
price_data = pd.Series()
macd_data = pd.Series()  # 存储MACD值
signal_data = pd.Series()  # 存储信号线值
entry_price = None
last_signal = None
in_position = False
position_direction = None

# ==================== 简单MACD计算 ====================
def calculate_macd(prices, fast=12, slow=26, signal=9):
    """简单MACD计算"""
    if len(prices) < slow + signal:
        return 0, 0, 0
    
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

# ==================== 核心交易信号函数 ====================
def trade_signal(time, price):
    """
    安全版MACD趋势策略
    
    逻辑：
    1. 趋势过滤：价格在MA50之上只做多，之下只做空
    2. MACD金叉做多，死叉做空
    3. 止损6%，止盈18%
    """
    global price_data, macd_data, signal_data, entry_price, last_signal, in_position, position_direction
    
    price_data = pd.concat([price_data, pd.Series([price])])
    
    min_data_required = max(macd_slow, macd_signal, ma_period) + 10
    if len(price_data) < min_data_required:
        return None
    
    # 计算指标
    macd_val, signal_val, hist_val = calculate_macd(price_data, macd_fast, macd_slow, macd_signal)
    ma = price_data.rolling(window=ma_period).mean().iloc[-1]
    
    # 记录历史MACD和信号线（用于判断交叉）
    macd_data = pd.concat([macd_data, pd.Series([macd_val])])
    signal_data = pd.concat([signal_data, pd.Series([signal_val])])
    
    # 趋势判断
    uptrend = price > ma
    downtrend = price < ma
    
    # 判断金叉死叉
    macd_cross_up = False
    macd_cross_down = False
    
    if len(macd_data) >= 2:
        prev_macd = macd_data.iloc[-2]
        prev_signal = signal_data.iloc[-2]
        macd_cross_up = (prev_macd <= prev_signal) and (macd_val > signal_val)  # 金叉
        macd_cross_down = (prev_macd >= prev_signal) and (macd_val < signal_val)  # 死叉
    
    if not in_position:
        # === 空仓 ===
        
        # 做多：上升趋势 + MACD金叉 + MACD在零线之上
        if uptrend and macd_cross_up and macd_val > 0:
            entry_price = price
            in_position = True
            position_direction = "做多"
            last_signal = "做多"
            return "做多"
        
        # 做空：下降趋势 + MACD死叉 + MACD在零线之下
        elif downtrend and macd_cross_down and macd_val < 0:
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
        
        # MACD反向交叉平仓
        if position_direction == "做多" and macd_cross_down:
            in_position = False
            position_direction = None
            last_signal = "平多"
            return "平多"
        elif position_direction == "做空" and macd_cross_up:
            in_position = False
            position_direction = None
            last_signal = "平空"
            return "平空"
    
    return None
