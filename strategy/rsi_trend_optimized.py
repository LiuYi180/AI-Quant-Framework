"""
优化版RSI趋势策略 - 目标：夏普比率>2
中低频，风险可控
"""
import pandas as pd

# ==================== 参数配置 ====================
# RSI参数
rsi_period = 7           # RSI周期（缩短，更敏感）
rsi_low = 35             # RSI低位（超卖）
rsi_high = 65             # RSI高位（超买）

# 均线参数
ma_short_period = 20       # 短期均线
ma_long_period = 60        # 长期均线

# 止损止盈
stop_loss_pct = 0.05      # 止损5%
take_profit_pct = 0.15    # 止盈15%

# 波动率过滤器
volatility_window = 20     # 波动率窗口
volatility_threshold = 0.03  # 波动率阈值

# ==================== 全局变量 ====================
price_data = pd.Series()       # 价格数据
entry_price = None              # 入场价格
last_signal = None              # 上一个信号
in_position = False             # 是否持仓
position_direction = None       # 持仓方向："做多" | "做空"

# ==================== RSI计算 ====================
def calculate_rsi(prices, period=14):
    """计算RSI"""
    if len(prices) < period + 1:
        return 50.0
    
    deltas = prices.diff().dropna()
    gains = (deltas.where(deltas > 0, 0)).rolling(window=period).mean()
    losses = (-deltas.where(deltas < 0, 0)).rolling(window=period).mean()
    
    # 避免除零
    losses = losses.replace(0, 0.001)
    
    rs = gains / losses
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

# ==================== 波动率计算 ====================
def calculate_volatility(prices, window=20):
    """计算波动率（标准差）"""
    if len(prices) < window:
        return 0.0
    
    returns = prices.pct_change().dropna()
    return returns.rolling(window=window).std().iloc[-1]

# ==================== 核心交易信号函数 ====================
def trade_signal(time, price):
    """
    核心函数：老大的框架会调用这个函数
    
    参数:
        time: 当前时间戳
        price: 当前价格
    
    返回:
        "做多" | "做空" | "平多" | "平空" | "不操作" | None
    """
    global price_data, entry_price, last_signal, in_position, position_direction
    
    # 1. 存储价格数据
    price_data = pd.concat([price_data, pd.Series([price])])
    
    # 2. 数据量检查
    min_data_required = max(ma_long_period, volatility_window, rsi_period) + 10
    if len(price_data) < min_data_required:
        return None  # 数据不足
    
    # 3. 计算指标
    current_rsi = calculate_rsi(price_data, rsi_period)
    ma_short = price_data.rolling(window=ma_short_period).mean().iloc[-1]
    ma_long = price_data.rolling(window=ma_long_period).mean().iloc[-1]
    volatility = calculate_volatility(price_data, volatility_window)
    
    # 4. 趋势判断
    uptrend = ma_short > ma_long  # 短期均线上穿长期均线：上升趋势
    downtrend = ma_short < ma_long  # 短期均线下穿长期均线：下降趋势
    
    # 5. 波动率过滤器：波动率过高时不交易（规避震荡市）
    if volatility > volatility_threshold:
        if in_position:
            # 波动率过高，平仓避险
            if position_direction == "做多":
                in_position = False
                position_direction = None
                last_signal = "平多"
                return "平多"
            elif position_direction == "做空":
                in_position = False
                position_direction = None
                last_signal = "平空"
                return "平空"
        return None  # 不持仓时，波动率过高也不操作
    
    # 6. 交易逻辑
    if not in_position:
        # === 空仓阶段：寻找入场机会 ===
        
        # 做多信号：上升趋势 + RSI从低位回升
        if uptrend and current_rsi > rsi_low and current_rsi < 55:
            entry_price = price
            in_position = True
            position_direction = "做多"
            last_signal = "做多"
            return "做多"
        
        # 做空信号：下降趋势 + RSI从高位回落
        elif downtrend and current_rsi < rsi_high and current_rsi > 45:
            entry_price = price
            in_position = True
            position_direction = "做空"
            last_signal = "做空"
            return "做空"
    
    else:
        # === 持仓阶段：管理持仓 ===
        
        # 计算盈亏
        if position_direction == "做多":
            pnl_pct = (price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - price) / entry_price
        
        # === 止损：先风控 ===
        if pnl_pct < -stop_loss_pct:
            in_position = False
            position_direction = None
            if last_signal == "做多":
                last_signal = "平多"
                return "平多"
            else:
                last_signal = "平空"
                return "平空"
        
        # === 止盈：保护利润 ===
        if pnl_pct > take_profit_pct:
            in_position = False
            position_direction = None
            if last_signal == "做多":
                last_signal = "平多"
                return "平多"
            else:
                last_signal = "平空"
                return "平空"
        
        # === 趋势反转平仓 ===
        if position_direction == "做多":
            # 做多时：趋势反转 + RSI超买 → 平多
            if not uptrend and current_rsi > rsi_high:
                in_position = False
                position_direction = None
                last_signal = "平多"
                return "平多"
        elif position_direction == "做空":
            # 做空时：趋势反转 + RSI超卖 → 平空
            if not downtrend and current_rsi < rsi_low:
                in_position = False
                position_direction = None
                last_signal = "平空"
                return "平空"
    
    # 默认：不操作
    return None


# ==================== 策略说明 ====================
"""
策略名称：优化版RSI趋势策略
目标：夏普比率>2，中低频，风险可控

核心逻辑：
1. 趋势判断：双均线（20日+60日）
2. 入场信号：
   - 做多：上升趋势 + RSI从低位回升（35-55）
   - 做空：下降趋势 + RSI从高位回落（45-65）
3. 出场信号：
   - 止损：-5%（严格风控）
   - 止盈：+15%（保护利润）
   - 趋势反转：均线交叉 + RSI超买/超卖
4. 过滤器：波动率过高（>3%）时不交易（规避震荡市）

参数配置（可优化）：
- RSI周期：7
- RSI低位：35，高位：65
- 均线：20日 + 60日
- 止损：5%，止盈：15%
- 波动率阈值：3%

风险控制：
- 单仓位：可在框架中设置（建议20%）
- 止损：严格5%，避免大亏
- 波动率过滤：规避高波动震荡市

推荐标的：
- BTC/USDT（趋势明显，波动适中）
- ETH/USDT
- 其他主流币

推荐周期：
- 1小时（平衡频率和收益）
- 4小时（更低频，更稳定）
"""
