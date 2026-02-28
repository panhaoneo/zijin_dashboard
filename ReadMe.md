# zijin-dashboard

> 紫金矿业（601899.SH）市场指标仪表盘，每日自动抓取，部署在 GitHub Pages。

## 文件结构

```
zijin-dashboard/
├── index.html                        # 前端页面（终端风格，纯静态）
├── fetch_data.py                     # 数据抓取脚本
├── data.json                         # 当日快照（Actions 每天覆盖）
├── history.json                      # 历史累积（Actions 每天 append）
├── .github/workflows/update-data.yml # 定时任务配置
└── README.md
```

## 监控指标

| 分类 | 内容 |
|------|------|
| 股票 | 紫金矿业 A股 / H股 |
| 贵金属 | COMEX 黄金、白银期货、GDX ETF、金银比 |
| 铜市场 | COMEX 铜期货、铜/金比、BHP、FCX |
| 实物库存 | COMEX 白银注册仓单 / 合格库存 / 入出库（CME官方XLS）|
| 宏观 | 美元指数、美债10Y、标普500、VIX |
| 历史图表 | 30d / 90d / all 可切换，读取 history.json |

## 部署步骤

### 1. 推代码到 GitHub

新建一个 **public** 仓库，将本目录所有文件推上去：

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/你的用户名/zijin-dashboard.git
git push -u origin main
```

### 2. 开启 GitHub Pages

仓库 → **Settings → Pages**
- Source: `Deploy from a branch`
- Branch: `main`，目录: `/ (root)`
- Save

### 3. 给 Actions 写权限

仓库 → **Settings → Actions → General**
- Workflow permissions → **Read and write permissions**
- Save

### 4. 手动触发首次更新

仓库 → **Actions → 每日数据更新 → Run workflow**

之后每天北京时间 09:00（UTC 01:00）自动执行，`data.json` 和 `history.json` 自动提交更新。

## 本地测试

```bash
pip install yfinance xlrd pytz
python fetch_data.py
# 用浏览器直接打开 index.html 即可预览
```

## 数据说明

- `data.json`：每天覆盖，只保留当日最新报价和 COMEX 库存
- `history.json`：每天 append 一条，按日期排序，最多保留 365 条
- 所有数据来自 Yahoo Finance + CME Group 官网，**完全免费，无需 API Key**

---

> 仅供参考，不构成投资建议。
