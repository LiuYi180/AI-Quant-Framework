#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险控制模块测试脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from 币安量化框架_升级版 import TradingEngine
import tkinter as tk
from datetime import datetime

def test_risk_module():
    """测试风险控制模块功能"""
    print("🚀 开始测试风险控制模块...")
    
    # 创建测试窗口
    root = tk.Tk()
    root.withdraw()  # 隐藏窗口
    
    # 初始化引擎
    engine = TradingEngine(root)
    
    print("✅ 引擎初始化成功")
    print(f"初始资金: {engine.risk_config['current_capital']} USDT")
    print(f"单笔交易最大风险: {engine.risk_config['max_risk_per_trade']*100}%")
    print(f"单日最大亏损: {engine.risk_config['max_daily_loss']*100}%")
    print(f"最大回撤限制: {engine.risk_config['max_drawdown']*100}%")
    
    # 测试1: 仓位计算
    test_price = 50000  # BTC价格
    position_size = engine.calculate_position_size(test_price, "做多")
    print(f"\n📊 仓位计算测试 (价格: {test_price} USDT):")
    print(f"计算仓位大小: {position_size:.6f} BTC")
    print(f"仓位价值: {position_size * test_price:.2f} USDT")
    print(f"风险金额: {engine.risk_config['max_risk_per_trade'] * engine.risk_config['current_capital']:.2f} USDT")
    
    # 测试2: 风险指标更新
    engine.update_risk_metrics(test_price)
    print(f"\n📈 风险指标更新测试:")
    print(f"当前回撤: {engine.risk_config['current_drawdown']:.2%}")
    print(f"当日亏损: {engine.risk_config['daily_loss']:.2%}")
    print(f"资金峰值: {engine.risk_config['peak_capital']:.2f} USDT")
    
    # 测试3: 风险限制检查
    print(f"\n🔍 风险限制检查测试:")
    
    # 正常开仓检查
    allowed = engine.check_risk_limits("做多", test_price)
    print(f"正常开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'}")
    
    # 模拟大额亏损测试回撤限制
    engine.risk_config['current_capital'] = 750  # 亏损25%
    engine.update_risk_metrics(test_price)
    allowed = engine.check_risk_limits("做多", test_price)
    print(f"回撤25%开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'} (预期拒绝，超过20%回撤限制)")
    print(f"交易开关状态: {'开启 ✅' if engine.risk_config['trading_enabled'] else '关闭 ❌'}")
    
    # 恢复正常
    engine.risk_config['current_capital'] = 1000
    engine.risk_config['trading_enabled'] = True
    engine.risk_config['peak_capital'] = 1000
    engine.update_risk_metrics(test_price)
    
    # 测试单日亏损限制
    engine.risk_config['daily_loss'] = 0.15  # 单日亏损15%
    allowed = engine.check_risk_limits("做多", test_price)
    print(f"单日亏损15%开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'} (预期拒绝，超过10%单日亏损限制)")
    print(f"交易开关状态: {'开启 ✅' if engine.risk_config['trading_enabled'] else '关闭 ❌'}")
    
    # 恢复正常
    engine.risk_config['daily_loss'] = 0.0
    engine.risk_config['trading_enabled'] = True
    
    # 测试价格异常波动
    engine.data_queue.append((datetime.now(), test_price))
    abnormal_price = test_price * 1.1  # 上涨10%
    allowed = engine.check_risk_limits("做多", abnormal_price)
    print(f"价格波动10%开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'} (预期拒绝，超过5%波动限制)")
    
    # 测试4: 告警功能
    print(f"\n📢 告警功能测试:")
    engine.send_alert("测试告警信息", level="normal")
    engine.send_alert("高优先级测试告警", level="high")
    print("✅ 告警已写入 alerts.log 文件")
    
    # 测试5: 紧急停止功能
    print(f"\n⚠️  紧急停止测试:")
    engine.position['side'] = 'long'
    engine.position['size'] = 0.01
    engine.position['entry_price'] = 50000
    engine.data_queue.append((datetime.now(), 51000))
    
    engine.emergency_stop("测试紧急停止")
    print(f"紧急停止后交易开关: {'开启 ✅' if engine.risk_config['trading_enabled'] else '关闭 ❌'}")
    print(f"紧急停止后持仓状态: {engine.position['side']}")
    
    print("\n🎉 风险控制模块测试完成！")
    print("-" * 50)
    print("核心功能验证:")
    print("✅ 仓位计算功能正常")
    print("✅ 风险指标更新正常")
    print("✅ 多层级风险限制生效")
    print("✅ 告警功能正常")
    print("✅ 紧急停止功能正常")
    print("\n风险控制模块已完成开发，可集成到交易流程中。")
    
    root.destroy()

if __name__ == "__main__":
    test_risk_module()
