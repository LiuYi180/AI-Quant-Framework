import pandas as pd

# 初始化参数
fast_window = 5  # 快线窗口
slow_window = 20  # 慢线窗口

# 存储价格数据
price_data = pd.Series()
# 存储上一个信号
last_signal = None


def trade_signal(time, price):
    """
    双均线交叉策略
    参数:
        time: 当前时间
        price: 当前价格
    返回:
        "做多": 买入信号
        "做空": 卖出信号
        "平多": 平多仓信号
        "平空": 平空仓信号
        None: 不操作信号
    """
    global price_data, last_signal

    # 添加新的价格数据
    price_data = pd.concat([price_data, pd.Series([price])])

    # 计算均线
    if len(price_data) >= slow_window:
        fast_ma = price_data.rolling(window=fast_window).mean().iloc[-1]
        slow_ma = price_data.rolling(window=slow_window).mean().iloc[-1]
        prev_fast_ma = price_data.rolling(window=fast_window).mean().iloc[-2]
        prev_slow_ma = price_data.rolling(window=slow_window).mean().iloc[-2]

        # 金叉：快线上穿慢线 -> 做多
        if fast_ma > slow_ma and prev_fast_ma <= prev_slow_ma:
            signal = "做多"
            last_signal = signal
            return signal
        
        # 死叉：快线下穿慢线 -> 平多+做空
        elif fast_ma < slow_ma and prev_fast_ma >= prev_slow_ma:
            signal = "平多" if last_signal == "做多" else "做空"
            last_signal = signal
            return signal

    return None
