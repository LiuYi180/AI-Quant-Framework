import requests
import pandas as pd
from collections import deque
import time
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import importlib.util
import math
import threading
from binance.client import Client
from binance.enums import *
import logging
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import mplfinance as mpf
import numpy as np
import ccxt

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradingEngine:
    def __init__(self, root):
        self.root = root
        self.root.title("Athena Trading Engine - 升级版")
        self.root.geometry("1600x900")
        
        # 引擎模式：0-回测，1-实测，2-实盘
        self.engine_mode = 0
        
        # 交易所选择
        self.exchange_name = "binance"  # binance / okx
        self.exchange = None
        self.okx_api = None
        
        # ================== 风险控制模块 ==================
        self.risk_config = {
            # 基础风控参数
            'max_risk_per_trade': 0.02,      # 单笔交易最大风险 2%本金
            'max_daily_loss': 0.1,           # 单日最大亏损 10%本金
            'max_drawdown': 0.2,             # 最大回撤 20%
            'max_position_per_symbol': 0.3,  # 单一币种最大仓位 30%
            'price_fluctuation_limit': 0.05, # 价格波动限制 ±5%
            
            # 实盘配置
            'initial_capital': 1000.0,       # 初始资金
            'current_capital': 1000.0,       # 当前资金
            'peak_capital': 1000.0,          # 资金峰值
            'daily_start_capital': 1000.0,   # 当日初始资金
            'daily_loss': 0.0,               # 当日亏损
            'current_drawdown': 0.0,         # 当前回撤
            'trading_enabled': True,         # 交易开关
            'last_trade_date': None,         # 上一次交易日期
        }
        
        # 持仓信息
        self.position = {
            'symbol': '',
            'side': '',  # long/short/empty
            'size': 0.0,
            'entry_price': 0.0,
            'unrealized_pnl': 0.0,
            'leverage': 5
        }
        
        # 公共数据
        self.symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
        self.intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
        self.data_queue = deque(maxlen=10000)
        self.df = pd.DataFrame()
        self.kline_data = pd.DataFrame()  # K线数据用于图表
        self.strategy = None
        self.strategy_name = ""
        self.order_list = []
        self.trade_orders = []
        self.order_sequence = 1
        self.signal_markers = []  # 信号标记
        
        # 创建界面
        self.create_main_ui()
        
        # 初始化交易所
        self.init_exchange()

    def init_exchange(self):
        """初始化交易所API"""
        try:
            # 初始化币安
            self.binance_client = Client()
            
            # 初始化OKX
            self.okx_exchange = ccxt.okx({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot'
                }
            })
        except Exception as e:
            self.log(f"交易所初始化失败: {str(e)}")

    # ================== 风险控制核心方法 ==================
    def update_risk_metrics(self, current_price=None):
        """更新风险指标"""
        # 更新资金峰值和回撤
        if self.risk_config['current_capital'] > self.risk_config['peak_capital']:
            self.risk_config['peak_capital'] = self.risk_config['current_capital']
        
        if self.risk_config['peak_capital'] > 0:
            self.risk_config['current_drawdown'] = 1 - self.risk_config['current_capital'] / self.risk_config['peak_capital']
        
        # 更新当日亏损
        today = datetime.now().date()
        if self.risk_config['last_trade_date'] != today:
            self.risk_config['daily_start_capital'] = self.risk_config['current_capital']
            self.risk_config['daily_loss'] = 0.0
            self.risk_config['last_trade_date'] = today
        else:
            self.risk_config['daily_loss'] = 1 - self.risk_config['current_capital'] / self.risk_config['daily_start_capital']
        
        # 更新持仓浮盈
        if current_price and self.position['side'] != 'empty':
            if self.position['side'] == 'long':
                self.position['unrealized_pnl'] = (current_price - self.position['entry_price']) * self.position['size']
            else:  # short
                self.position['unrealized_pnl'] = (self.position['entry_price'] - current_price) * self.position['size']
    
    def check_risk_limits(self, signal=None, price=None):
        """检查风险限制，返回是否允许交易"""
        # 全局交易开关
        if not self.risk_config['trading_enabled']:
            self.log("❌ 交易已被禁用，拒绝执行信号")
            return False
        
        # 最大回撤检查
        if self.risk_config['current_drawdown'] >= self.risk_config['max_drawdown']:
            self.log(f"❌ 触发最大回撤限制: 当前回撤{self.risk_config['current_drawdown']:.2%} >= 限制{self.risk_config['max_drawdown']:.2%}")
            self.emergency_stop("最大回撤触发")
            return False
        
        # 单日最大亏损检查
        if self.risk_config['daily_loss'] >= self.risk_config['max_daily_loss']:
            self.log(f"❌ 触发单日最大亏损限制: 当日亏损{self.risk_config['daily_loss']:.2%} >= 限制{self.risk_config['max_daily_loss']:.2%}")
            self.emergency_stop("单日最大亏损触发")
            return False
        
        # 价格异常波动检查
        if price and len(self.data_queue) > 1:
            last_price = self.data_queue[-1][1]
            fluctuation = abs(price - last_price) / last_price
            if fluctuation >= self.risk_config['price_fluctuation_limit']:
                self.log(f"❌ 触发价格异常波动限制: 当前波动{fluctuation:.2%} >= 限制{self.risk_config['price_fluctuation_limit']:.2%}")
                return False
        
        # 开仓前检查
        if signal in ["做多", "做空"] and self.position['side'] == 'empty':
            # 单笔风险检查
            position_size = self.calculate_position_size(price, signal)
            max_allowed_size = self.risk_config['current_capital'] * self.risk_config['max_risk_per_trade'] / price
            if position_size > max_allowed_size:
                self.log(f"❌ 触发单笔风险限制: 计算仓位{position_size:.4f} > 最大允许{max_allowed_size:.4f}")
                return False
            
            # 单一币种仓位限制
            position_value = position_size * price
            max_allowed_value = self.risk_config['current_capital'] * self.risk_config['max_position_per_symbol']
            if position_value > max_allowed_value:
                self.log(f"❌ 触发单一币种仓位限制: 仓位价值{position_value:.2f} > 最大允许{max_allowed_value:.2f}")
                return False
        
        return True
    
    def calculate_position_size(self, price, signal):
        """计算合适的仓位大小"""
        # 基于风险的仓位计算
        risk_amount = self.risk_config['current_capital'] * self.risk_config['max_risk_per_trade']
        stop_loss_pct = 0.02  # 默认止损2%
        position_size = risk_amount / (price * stop_loss_pct)
        
        # 考虑杠杆
        position_size = position_size / self.position['leverage']
        
        return position_size
    
    def emergency_stop(self, reason=""):
        """紧急停止交易，平仓所有持仓"""
        self.log(f"⚠️ 执行紧急停止，原因: {reason}")
        self.risk_config['trading_enabled'] = False
        
        # 平仓所有持仓
        if self.position['side'] != 'empty':
            close_signal = "平多" if self.position['side'] == 'long' else "平空"
            self.log(f"⚠️ 自动平仓: {close_signal}")
            # 执行平仓逻辑
            self.execute_trade(close_signal, self.data_queue[-1][1] if self.data_queue else 0)
        
        # 发送告警
        self.send_alert(f"紧急停止触发: {reason}", "high")
    
    def send_alert(self, message, level="normal"):
        """发送告警通知"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_msg = f"[{timestamp}] {'⚠️' if level == 'high' else 'ℹ️'} {message}"
        self.log(alert_msg)
        
        # TODO: 集成OpenClaw消息推送，支持飞书/Telegram/邮件
        try:
            # 写入告警日志文件
            with open("alerts.log", "a", encoding="utf-8") as f:
                f.write(f"{alert_msg}\n")
        except Exception as e:
            self.log(f"告警写入失败: {str(e)}")

    def create_main_ui(self):
        # 主布局：左右分栏
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 左侧控制面板
        left_frame = ttk.Frame(main_paned, width=400)
        main_paned.add(left_frame)
        
        # 右侧图表和日志面板
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        # ================== 左侧控制面板 ==================
        # 顶部引擎切换按钮
        engine_frame = ttk.LabelFrame(left_frame, text="引擎模式")
        engine_frame.pack(fill="x", padx=5, pady=5)
        
        self.backtest_btn = ttk.Button(engine_frame, text="回测引擎", command=lambda: self.switch_engine(0))
        self.backtest_btn.pack(side="left", padx=5, pady=5)
        
        self.paper_btn = ttk.Button(engine_frame, text="实测引擎", command=lambda: self.switch_engine(1))
        self.paper_btn.pack(side="left", padx=5, pady=5)
        
        self.live_btn = ttk.Button(engine_frame, text="实盘引擎", command=lambda: self.switch_engine(2))
        self.live_btn.pack(side="left", padx=5, pady=5)
        
        # 交易所选择
        exchange_frame = ttk.LabelFrame(left_frame, text="交易所选择")
        exchange_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(exchange_frame, text="交易所:").pack(side="left", padx=5, pady=5)
        self.exchange_var = tk.StringVar(value="binance")
        exchange_combo = ttk.Combobox(exchange_frame, textvariable=self.exchange_var, values=["binance", "okx"], state="readonly")
        exchange_combo.pack(side="left", padx=5, pady=5)
        exchange_combo.bind("<<ComboboxSelected>>", self.on_exchange_change)
        
        # API配置
        api_frame = ttk.LabelFrame(left_frame, text="API配置")
        api_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(api_frame, text="API Key:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.api_key_entry = ttk.Entry(api_frame, width=30)
        self.api_key_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(api_frame, text="Secret Key:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.secret_key_entry = ttk.Entry(api_frame, width=30, show="*")
        self.secret_key_entry.grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Button(api_frame, text="保存配置", command=self.save_api_config).grid(row=2, column=0, columnspan=2, pady=5)
        
        # 交易对和时间周期
        symbol_frame = ttk.LabelFrame(left_frame, text="交易配置")
        symbol_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(symbol_frame, text="交易对:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.symbol_var = tk.StringVar(value="BTCUSDT")
        symbol_combo = ttk.Combobox(symbol_frame, textvariable=self.symbol_var, values=self.symbols, state="readonly")
        symbol_combo.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(symbol_frame, text="时间周期:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.interval_var = tk.StringVar(value="1m")
        interval_combo = ttk.Combobox(symbol_frame, textvariable=self.interval_var, values=self.intervals, state="readonly")
        interval_combo.grid(row=1, column=1, padx=5, pady=2)
        interval_combo.bind("<<ComboboxSelected>>", self.on_interval_change)
        
        ttk.Label(symbol_frame, text="初始资金:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.capital_entry = ttk.Entry(symbol_frame, width=15)
        self.capital_entry.insert(0, "10000")
        self.capital_entry.grid(row=2, column=1, padx=5, pady=2, sticky="w")
        
        ttk.Label(symbol_frame, text="杠杆倍数:").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.leverage_entry = ttk.Entry(symbol_frame, width=15)
        self.leverage_entry.insert(0, "1")
        self.leverage_entry.grid(row=3, column=1, padx=5, pady=2, sticky="w")
        
        # 策略选择
        strategy_frame = ttk.LabelFrame(left_frame, text="策略配置")
        strategy_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(strategy_frame, text="加载策略", command=self.load_strategy).pack(side="left", padx=5, pady=5)
        self.strategy_label = ttk.Label(strategy_frame, text="未选择策略")
        self.strategy_label.pack(side="left", padx=5, pady=5)
        
        # 控制按钮
        control_frame = ttk.LabelFrame(left_frame, text="运行控制")
        control_frame.pack(fill="x", padx=5, pady=5)
        
        self.start_btn = ttk.Button(control_frame, text="启动", command=self.start_engine)
        self.start_btn.pack(side="left", padx=5, pady=5)
        
        self.stop_btn = ttk.Button(control_frame, text="停止", command=self.stop_engine, state="disabled")
        self.stop_btn.pack(side="left", padx=5, pady=5)
        
        self.clear_btn = ttk.Button(control_frame, text="清空日志", command=self.clear_log)
        self.clear_btn.pack(side="left", padx=5, pady=5)
        
        # 账户信息
        account_frame = ttk.LabelFrame(left_frame, text="账户信息")
        account_frame.pack(fill="x", padx=5, pady=5)
        
        self.balance_label = ttk.Label(account_frame, text="账户余额: 0.0 USDT")
        self.balance_label.pack(anchor="w", padx=5, pady=2)
        
        self.position_label = ttk.Label(account_frame, text="当前持仓: 无")
        self.position_label.pack(anchor="w", padx=5, pady=2)
        
        self.pnl_label = ttk.Label(account_frame, text="累计盈亏: 0.0 USDT (0.0%)")
        self.pnl_label.pack(anchor="w", padx=5, pady=2)
        
        self.winrate_label = ttk.Label(account_frame, text="胜率: 0%")
        self.winrate_label.pack(anchor="w", padx=5, pady=2)
        
        # ================== 右侧面板 ==================
        # 顶部K线图表
        chart_frame = ttk.LabelFrame(right_frame, text="行情图表")
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建matplotlib图表
        self.fig = Figure(figsize=(12, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 底部日志面板
        log_frame = ttk.LabelFrame(right_frame, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 日志文本框
        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # 状态栏
        self.status_bar = ttk.Label(self.root, text="就绪", relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 运行状态
        self.running = False
        self.thread = None

    def on_exchange_change(self, event):
        """交易所切换事件"""
        self.exchange_name = self.exchange_var.get()
        self.log(f"切换到{self.exchange_name}交易所")
        self.init_exchange()

    def on_interval_change(self, event):
        """时间周期切换事件"""
        if len(self.df) > 0:
            self.update_chart()

    def log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_msg)
        self.log_text.see(tk.END)
        logger.info(message)

    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)

    def save_api_config(self):
        """保存API配置"""
        api_key = self.api_key_entry.get().strip()
        secret_key = self.secret_key_entry.get().strip()
        
        if not api_key or not secret_key:
            messagebox.showwarning("警告", "API Key和Secret Key不能为空")
            return
        
        try:
            if self.exchange_name == "binance":
                self.binance_client = Client(api_key, secret_key)
                # 测试连接
                account = self.binance_client.get_account()
                self.log("币安API连接成功")
            elif self.exchange_name == "okx":
                self.okx_exchange.apiKey = api_key
                self.okx_exchange.secret = secret_key
                # 测试连接
                balance = self.okx_exchange.fetch_balance()
                self.log("OKX API连接成功")
            
            messagebox.showinfo("成功", "API配置保存成功")
        except Exception as e:
            messagebox.showerror("错误", f"API连接失败: {str(e)}")

    def load_strategy(self):
        """加载策略文件"""
        file_path = filedialog.askopenfilename(filetypes=[("Python文件", "*.py")])
        if not file_path:
            return
        
        try:
            spec = importlib.util.spec_from_file_location("strategy", file_path)
            self.strategy = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.strategy)
            
            if not hasattr(self.strategy, 'trade_signal'):
                raise Exception("策略文件必须包含trade_signal函数")
            
            self.strategy_name = os.path.basename(file_path)
            self.strategy_label.config(text=self.strategy_name)
            self.log(f"策略加载成功: {self.strategy_name}")
            
        except Exception as e:
            messagebox.showerror("错误", f"策略加载失败: {str(e)}")

    def switch_engine(self, mode):
        """切换引擎模式"""
        self.engine_mode = mode
        self.backtest_btn.config(state="normal")
        self.paper_btn.config(state="normal")
        self.live_btn.config(state="normal")
        
        if mode == 0:
            self.backtest_btn.config(state="disabled")
            self.status_bar.config(text="当前模式: 回测引擎")
        elif mode == 1:
            self.paper_btn.config(state="disabled")
            self.status_bar.config(text="当前模式: 实测引擎")
        else:
            self.live_btn.config(state="disabled")
            self.status_bar.config(text="当前模式: 实盘引擎")
        
        self.log(f"切换到{['回测', '实测', '实盘'][mode]}引擎")

    def get_kline_data(self, symbol, interval, limit=100):
        """获取K线数据"""
        try:
            if self.exchange_name == "binance":
                klines = self.binance_client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=limit
                )
                # 转换为DataFrame
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base', 'taker_buy_quote', 'ignore'
                ])
            elif self.exchange_name == "okx":
                # 转换时间周期格式
                okx_interval = interval.replace('m', 'm').replace('h', 'H').replace('d', 'D').replace('w', 'W')
                ohlcv = self.okx_exchange.fetch_ohlcv(symbol, timeframe=okx_interval, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 转换数据类型
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            self.log(f"获取K线数据失败: {str(e)}")
            return None

    def update_chart(self):
        """更新K线图表"""
        if len(self.kline_data) < 1:
            return
        
        self.ax.clear()
        
        # 绘制K线
        mpf.plot(self.kline_data, type='candle', ax=self.ax, style='charles', warn_too_much_data=1000)
        
        # 绘制交易信号标记
        for marker in self.signal_markers:
            idx, signal_type, price = marker
            if signal_type == "long":
                # 开多：绿色向上箭头
                self.ax.scatter(idx, price * 0.995, marker='^', color='g', s=100, zorder=5)
            elif signal_type == "short":
                # 开空：红色向下箭头
                self.ax.scatter(idx, price * 1.005, marker='v', color='r', s=100, zorder=5)
            elif signal_type == "close":
                # 平仓：黄色圆点
                self.ax.scatter(idx, price, marker='o', color='y', s=80, zorder=5)
        
        self.ax.set_title(f"{self.symbol_var.get()} {self.interval_var.get()} K线图")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()

    def add_signal_marker(self, signal_type, price):
        """添加信号标记"""
        if len(self.kline_data) > 0:
            idx = self.kline_data.index[-1]
            self.signal_markers.append((idx, signal_type, price))
            self.update_chart()

    def execute_trade(self, signal, price):
        """执行交易"""
        timestamp = datetime.now()
        
        # 先检查风险控制
        if not self.check_risk_limits(signal, price):
            return
        
        # 更新风险指标
        self.update_risk_metrics(price)
        
        if signal == "做多":
            if self.position['side'] == 'empty':
                # 计算仓位
                position_size = self.calculate_position_size(price, signal)
                self.position['side'] = 'long'
                self.position['size'] = position_size
                self.position['entry_price'] = price
                self.position['symbol'] = self.symbol_var.get()
                
                self.log(f"✅ 开多执行，价格: {price}，仓位: {position_size:.4f}")
                self.add_signal_marker("long", price)
                self.send_alert(f"开多 {self.symbol_var.get()} 价格: {price} 仓位: {position_size:.4f}")
                
        elif signal == "做空":
            if self.position['side'] == 'empty':
                # 计算仓位
                position_size = self.calculate_position_size(price, signal)
                self.position['side'] = 'short'
                self.position['size'] = position_size
                self.position['entry_price'] = price
                self.position['symbol'] = self.symbol_var.get()
                
                self.log(f"✅ 开空执行，价格: {price}，仓位: {position_size:.4f}")
                self.add_signal_marker("short", price)
                self.send_alert(f"开空 {self.symbol_var.get()} 价格: {price} 仓位: {position_size:.4f}")
                
        elif signal in ["平多", "平空"]:
            if (signal == "平多" and self.position['side'] == 'long') or \
               (signal == "平空" and self.position['side'] == 'short'):
                
                # 计算盈亏
                if self.position['side'] == 'long':
                    pnl = (price - self.position['entry_price']) * self.position['size']
                else:
                    pnl = (self.position['entry_price'] - price) * self.position['size']
                
                # 更新资金
                self.risk_config['current_capital'] += pnl
                
                # 记录交易
                trade_record = {
                    'time': timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    'symbol': self.position['symbol'],
                    'side': self.position['side'],
                    'entry_price': self.position['entry_price'],
                    'exit_price': price,
                    'size': self.position['size'],
                    'pnl': pnl,
                    'pnl_pct': pnl / (self.position['entry_price'] * self.position['size']) * 100
                }
                self.trade_orders.append(trade_record)
                
                # 清空持仓
                self.position['side'] = 'empty'
                self.position['size'] = 0.0
                self.position['entry_price'] = 0.0
                self.position['unrealized_pnl'] = 0.0
                
                self.log(f"✅ {signal}执行，价格: {price}，盈亏: {pnl:.2f} USDT ({trade_record['pnl_pct']:.2f}%)")
                self.add_signal_marker("close", price)
                self.send_alert(f"{signal} {self.symbol_var.get()} 价格: {price} 盈亏: {pnl:.2f} USDT ({trade_record['pnl_pct']:.2f}%)")
                
                # 更新风险指标
                self.update_risk_metrics(price)

    def backtest_loop(self):
        """回测循环"""
        self.log("开始回测...")
        
        # 获取历史数据
        self.df = self.get_kline_data(self.symbol_var.get(), self.interval_var.get(), limit=500)
        if self.df is None or len(self.df) < 100:
            self.log("数据不足，无法回测")
            return
        
        self.kline_data = self.df.tail(100).copy()
        self.update_chart()
        
        initial_capital = float(self.capital_entry.get())
        capital = initial_capital
        position = 0
        avg_price = 0
        total_trades = 0
        win_trades = 0
        
        # 回测主循环
        for i in range(100, len(self.df)):
            if not self.running:
                break
                
            # 更新K线数据
            self.kline_data = self.df.iloc[i-100:i+1].copy()
            
            # 获取当前价格数据
            current_data = self.df.iloc[i]
            price = current_data['close']
            
            # 调用策略
            try:
                signal = self.strategy.trade_signal(current_data.name, price)
            except Exception as e:
                self.log(f"策略执行错误: {str(e)}")
                break
            
            # 处理信号
            if signal == "做多" and position <= 0:
                # 平空开多
                if position < 0:
                    pnl = (avg_price - price) * abs(position)
                    capital += pnl
                    if pnl > 0:
                        win_trades += 1
                    total_trades += 1
                    self.execute_trade("平空", price)
                
                # 开多
                position = capital / price * float(self.leverage_entry.get()) * 0.95
                avg_price = price
                self.execute_trade("做多", price)
                
            elif signal == "做空" and position >= 0:
                # 平多开空
                if position > 0:
                    pnl = (price - avg_price) * position
                    capital += pnl
                    if pnl > 0:
                        win_trades += 1
                    total_trades += 1
                    self.execute_trade("平多", price)
                
                # 开空
                position = -capital / price * float(self.leverage_entry.get()) * 0.95
                avg_price = price
                self.execute_trade("做空", price)
                
            elif signal == "平多" and position > 0:
                # 平多
                pnl = (price - avg_price) * position
                capital += pnl
                if pnl > 0:
                    win_trades += 1
                total_trades += 1
                position = 0
                self.execute_trade("平多", price)
                
            elif signal == "平空" and position < 0:
                # 平空
                pnl = (avg_price - price) * abs(position)
                capital += pnl
                if pnl > 0:
                    win_trades += 1
                total_trades += 1
                position = 0
                self.execute_trade("平空", price)
            
            # 更新UI
            pnl = capital - initial_capital
            pnl_percent = (pnl / initial_capital) * 100
            winrate = (win_trades / total_trades * 100) if total_trades > 0 else 0
            
            self.root.after(0, lambda c=capital, p=position, pnl=pnl, pp=pnl_percent, wr=winrate: 
                          self.update_account_info(c, p, pnl, pp, wr))
            
            self.update_chart()
            time.sleep(0.05)  # 控制回测速度
        
        # 回测结束
        if position != 0:
            # 平仓
            pnl = (price - avg_price) * position if position > 0 else (avg_price - price) * abs(position)
            capital += pnl
            if pnl > 0:
                win_trades += 1
            total_trades += 1
        
        pnl = capital - initial_capital
        pnl_percent = (pnl / initial_capital) * 100
        winrate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        
        self.log(f"回测结束，最终资金: {capital:.2f} USDT, 总收益: {pnl:.2f} USDT ({pnl_percent:.2f}%), 胜率: {winrate:.1f}%")
        self.update_account_info(capital, 0, pnl, pnl_percent, winrate)

    def update_account_info(self, balance, position, pnl, pnl_percent, winrate):
        """更新账户信息显示"""
        self.balance_label.config(text=f"账户余额: {balance:.2f} USDT")
        
        if position > 0:
            self.position_label.config(text=f"当前持仓: 多单 {abs(position):.4f}")
        elif position < 0:
            self.position_label.config(text=f"当前持仓: 空单 {abs(position):.4f}")
        else:
            self.position_label.config(text="当前持仓: 无")
        
        self.pnl_label.config(text=f"累计盈亏: {pnl:.2f} USDT ({pnl_percent:.2f}%)")
        self.winrate_label.config(text=f"胜率: {winrate:.1f}%")

    def start_engine(self):
        """启动引擎"""
        if self.strategy is None:
            messagebox.showwarning("警告", "请先加载策略")
            return
        
        if self.engine_mode == 2:  # 实盘模式
            if not self.api_key_entry.get() or not self.secret_key_entry.get():
                messagebox.showwarning("警告", "实盘模式需要配置API")
                return
                
            confirm = messagebox.askyesno("确认", "实盘模式将进行真实交易，确定要启动吗？")
            if not confirm:
                return
        
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.signal_markers = []  # 清空信号标记
        
        # 启动线程
        if self.engine_mode == 0:
            self.thread = threading.Thread(target=self.backtest_loop, daemon=True)
        else:
            # 实测和实盘模式后续开发
            self.thread = threading.Thread(target=self.live_loop, daemon=True)
        
        self.thread.start()

    def stop_engine(self):
        """停止引擎"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.log("引擎已停止")

    def live_loop(self):
        """实盘/实测循环（待完善）"""
        self.log("实盘/实测模式开发中...")
        # 后续实现

if __name__ == "__main__":
    root = tk.Tk()
    app = TradingEngine(root)
    root.mainloop()
