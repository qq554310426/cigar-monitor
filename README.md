# 古巴雪茄补货监控

自动监控 mrcigarshop.com 古巴雪茄库存，发现补货时推送企业微信通知。

## 功能

- 每 20 分钟检查一次库存
- 检测到补货时自动推送企业微信通知
- 部署到海外服务器，绕过 403 限制

## 部署

详见 `deploy_guide.md`

## 文件说明

- `cigar_monitor_render.py` - 主程序（云端版）
- `requirements.txt` - Python 依赖
- `cigar_stock_state.json` - 库存状态文件（自动生成）
