# AI量化交易框架 - OpenClaw Skill 配置说明

**Skill ID:** quant-framework  
**版本:** v1.1.0  
**描述:** AI驱动的量化交易全栈框架，支持回测、实测、实盘一体化，集成币安/OKX双交易所，内置可视化K线和风险控制模块。

---

## 🔧 OpenClaw 集成配置

### 1. 安装步骤
将本项目放置到 OpenClaw 技能目录：
```bash
# 默认技能目录
/Users/liuyi/openclaw/workspace/skills/quant-framework/

# 软链接方式（推荐）
ln -s /path/to/AI-Quant-Framework /Users/liuyi/openclaw/workspace/skills/quant-framework
```

### 2. 技能配置
在 OpenClaw 配置文件 `config.yml` 中添加：
```yaml
skills:
  quant-framework:
    enabled: true
    path: ./skills/quant-framework
    entry: 币安量化框架_升级版.py
    permissions:
      - network
      - file_write
      - process_exec
      - message_send
    env:
      # 交易所API配置（可选，实盘需要）
      BINANCE_API_KEY: ""
      BINANCE_API_SECRET: ""
      OKX_API_KEY: ""
      OKX_API_SECRET: ""
      OKX_PASSPHRASE: ""
      # 数据存储路径
      DATA_PATH: "./data"
      # 日志路径
      LOG_PATH: "./logs"
```

### 3. 依赖安装
```bash
cd /Users/liuyi/openclaw/workspace/skills/quant-framework
pip install -r requirements.txt
```

---

## 🎯 调用方式

### 自然语言调用示例
```
# 回测相关
"帮我用布林带策略回测BNBUSDT最近30天1小时周期表现"
"优化一下双均线策略的参数，回测周期1年"
"生成回测报告，重点看最大回撤和胜率"

# 实盘相关
"启动BTCUSDT 5分钟周期马丁格尔策略实盘，初始资金1000U"
"暂停当前实盘交易，平掉所有持仓"
"查看今日实盘收益情况"

# 系统相关
"查看所有可用策略列表"
"添加新的策略文件到策略库"
"设置每日收益提醒，阈值10%"
```

### 命令行调用
```bash
# 回测模式
openclaw quant backtest --symbol BNBUSDT --period 1h --days 30 --strategy 策略示范.py

# 实测模式
openclaw quant paper-trade --symbol BTCUSDT --period 5m --strategy 马丁格尔.py

# 实盘模式
openclaw quant live-trade --symbol ETHUSDT --period 15m --strategy 双均线.py --leverage 10

# 查看状态
openclaw quant status
openclaw quant logs
openclaw quant reports
```

---

## 📊 输出格式

### 回测结果示例
```json
{
  "strategy": "布林带策略",
  "symbol": "BNBUSDT",
  "period": "1h",
  "days": 30,
  "initial_capital": 1000,
  "final_capital": 1456.78,
  "total_return": "45.68%",
  "win_rate": "68.3%",
  "max_drawdown": "12.4%",
  "total_trades": 47,
  "profit_factor": 1.89,
  "sharpe_ratio": 2.34
}
```

### 实盘告警示例
```
⚠️ 实盘交易告警
时间：2026-03-09 14:30:00
交易对：BTCUSDT
信号：平多
价格：68500 USDT
收益：+125.6 USDT (+3.2%)
当前持仓：空仓
累计收益：+245.8 USDT (+24.58%)
```

---

## 🔒 权限说明

| 权限 | 用途 |
|------|------|
| network | 连接交易所API获取行情、执行交易 |
| file_write | 存储历史数据、交易日志、回测报告 |
| process_exec | 启动回测/实盘进程，加载策略文件 |
| message_send | 发送交易告警、收益报表、异常通知 |

---

## ⚙️ 配置参数

### 全局配置
| 参数 | 默认值 | 说明 |
|------|--------|------|
| default_symbol | BNBUSDT | 默认交易对 |
| default_period | 1h | 默认K线周期 |
| default_initial_capital | 1000 | 默认初始资金（USDT） |
| default_leverage | 5 | 默认杠杆倍数 |
| fee_rate | 0.0005 | 手续费率（0.05%） |
| risk_limit_per_trade | 0.02 | 单笔交易最大风险（2%本金） |
| max_drawdown_limit | 0.2 | 最大回撤限制（20%，触发自动停止） |

### 告警配置
| 参数 | 默认值 | 说明 |
|------|--------|------|
| enable_alerts | true | 启用告警通知 |
| alert_channel | feishu | 告警渠道（feishu/telegram/email） |
| daily_report_time | "21:00" | 每日收益报表发送时间 |
| alert_on_profit | 0.05 | 单笔盈利超过5%告警 |
| alert_on_loss | 0.03 | 单笔亏损超过3%告警 |

---

## 📁 目录结构（OpenClaw适配后）
```
quant-framework/
├── SKILL.md                    # 本配置文件
├── README.md                   # 项目说明
├── DEVELOPMENT_LOG.md          # 开发日志
├── requirements.txt            # 依赖清单
├── 币安量化框架_升级版.py       # 主程序入口
├── strategy/                   # 策略库目录
│   ├── 策略示范.py             # 布林带策略示例
│   ├── 马丁格尔.py             # 马丁格尔策略
│   ├── 双均线.py               # 双均线策略
│   └── 自定义策略/             # 用户自定义策略目录
├── data/                       # 历史数据存储
├── logs/                       # 交易日志存储
├── reports/                    # 回测报告存储
└── config/                     # 配置文件目录
    └── config.yml              # 用户自定义配置
```

---

## 🚀 版本提交信息

**版本号:** v1.1.0-openclaw  
**发布时间:** 2026-03-09  
**更新内容:**
1. ✅ 完成OpenClaw Skill适配，支持自然语言调用
2. ✅ 新增SKILL.md配置说明文档
3. ✅ 优化目录结构，适配OpenClaw技能规范
4. ✅ 新增权限配置和参数说明
5. ✅ 支持消息推送、告警通知、定时任务等OpenClaw原生能力
6. ✅ 修复策略热加载兼容性问题

**提交信息:** "feat: 完成OpenClaw集成，发布v1.1.0-openclaw版本"
