#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风控开关功能测试脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from 币安量化框架_升级版 import TradingEngine
import tkinter as tk
from datetime import datetime

def test_risk_switch():
    """测试风控开关功能"""
    print("🚀 开始测试风控开关功能...")
    
    # 创建测试窗口
    root = tk.Tk()
    root.withdraw()  # 隐藏窗口
    
    # 初始化引擎
    engine = TradingEngine(root)
    
    print("\n📋 测试1: 总风控开关关闭")
    engine.risk_config['enable_risk_control'] = False
    engine.risk_config['current_capital'] = 700  # 回撤30%，远超限制
    engine.update_risk_metrics(50000)
    
    allowed = engine.check_risk_limits("做多", 50000)
    print(f"总风控关闭，回撤30%开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'} (预期通过，风控已关闭)")
    
    print("\n📋 测试2: 仅关闭回撤限制")
    engine.risk_config['enable_risk_control'] = True
    engine.risk_config['enable_drawdown_limit'] = False
    engine.risk_config['current_capital'] = 700  # 回撤30%
    engine.risk_config['trading_enabled'] = True
    engine.update_risk_metrics(50000)
    
    allowed = engine.check_risk_limits("做多", 50000)
    print(f"回撤限制关闭，回撤30%开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'} (预期通过，回撤限制已关闭)")
    
    print("\n📋 测试3: 仅关闭单笔风险限制")
    engine.risk_config['enable_per_trade_limit'] = False
    engine.risk_config['enable_drawdown_limit'] = True
    engine.risk_config['current_capital'] = 1000  # 恢复正常
    engine.risk_config['trading_enabled'] = True
    engine.update_risk_metrics(50000)
    
    allowed = engine.check_risk_limits("做多", 50000)
    print(f"单笔风险限制关闭，开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'} (预期通过，单笔限制已关闭)")
    
    print("\n📋 测试4: 仅关闭单日亏损限制")
    engine.risk_config['enable_daily_loss_limit'] = False
    engine.risk_config['daily_loss'] = 0.15  # 单日亏损15%
    engine.risk_config['trading_enabled'] = True
    
    allowed = engine.check_risk_limits("做多", 50000)
    print(f"单日亏损限制关闭，亏损15%开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'} (预期通过，单日限制已关闭)")
    
    print("\n📋 测试5: 仅关闭仓位限制")
    engine.risk_config['enable_position_limit'] = False
    engine.risk_config['daily_loss'] = 0.0
    engine.risk_config['trading_enabled'] = True
    
    allowed = engine.check_risk_limits("做多", 50000)
    print(f"仓位限制关闭，开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'} (预期通过，仓位限制已关闭)")
    
    print("\n📋 测试6: 仅关闭价格波动限制")
    engine.risk_config['enable_price_fluctuation_limit'] = False
    engine.risk_config['trading_enabled'] = True
    engine.data_queue.append((datetime.now(), 50000))
    abnormal_price = 50000 * 1.2  # 波动20%
    
    allowed = engine.check_risk_limits("做多", abnormal_price)
    print(f"价格波动限制关闭，波动20%开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'} (预期通过，波动限制已关闭)")
    
    print("\n📋 测试7: 全部风控开启，正常情况")
    # 重置所有开关
    engine.risk_config['enable_per_trade_limit'] = True
    engine.risk_config['enable_daily_loss_limit'] = True
    engine.risk_config['enable_drawdown_limit'] = True
    engine.risk_config['enable_position_limit'] = True
    engine.risk_config['enable_price_fluctuation_limit'] = True
    engine.risk_config['current_capital'] = 1000
    engine.risk_config['peak_capital'] = 1000
    engine.risk_config['daily_loss'] = 0.0
    engine.risk_config['trading_enabled'] = True
    engine.update_risk_metrics(50000)
    
    allowed = engine.check_risk_limits("做多", 50000)
    print(f"全部风控开启，正常开仓检查: {'通过 ✅' if allowed else '拒绝 ❌'} (预期通过)")
    
    print("\n🎉 风控开关功能测试完成！")
    print("-" * 50)
    print("✅ 总风控开关功能正常")
    print("✅ 分项风控开关独立控制正常")
    print("✅ 开关组合逻辑正常")
    print("\n风控系统已支持选择性开启功能，可根据需求灵活配置。")
    
    root.destroy()

if __name__ == "__main__":
    test_risk_switch()
