# Dashboard API - Stock Market Dashboard

一个实时股票盯盘仪表盘，支持 A股、港股、美股、商品期货。

## 功能

- 📊 实时行情：A股/港股/美股/商品
- 🎯 交易建议：AI 自动分析
- 🔥 热门板块：实时涨跌排行
- 📰 市场快讯：行情资讯
- 🌐 云部署：支持 Railway、Render、Heroku

## 快速部署

### Railway
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new?template=https://github.com/YOUR_USERNAME/dashboard-api)

### Render
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/YOUR_USERNAME/dashboard-api)

## 本地运行

```bash
pip install -r requirements.txt
python3 app.py
```

访问 http://localhost:8000

## API 端点

- `GET /api/stocks` - 获取股票行情
- `GET /api/sectors` - 获取板块数据
- `GET /api/news` - 获取市场快讯
- `GET /api/advice` - 获取交易建议

## 配置

编辑 `index.html` 中的 API 地址：

```javascript
const API='https://YOUR_RENDER_URL/api';
```

## 股票池

- A股：上证、深证、创业板、沪深300
- 港股：恒生、恒生国企、腾讯、中海油、MINIMAX、德适-B
- 美股：英伟达、苹果、特斯拉、谷歌、标普500、纳斯达克、道琼斯
- 商品：黄金、白银、原油、铜
