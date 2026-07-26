# Kindle 展示中心（Render 部署版）

零越狱 Kindle 展示工具：信息面板、个人看板、电子相框、阅读进度、番茄钟、单词卡片，共 6 种模式，刷新策略自由选。

## 部署到 Render（推荐）

1. Fork 本仓库（或直接使用本仓库）
2. 登录 [render.com](https://render.com) → **New +** → **Web Service**
3. 连接你的 GitHub 仓库 `kindle-display-render`
4. 环境选 **Python 3**，或使用仓库内 `render.yaml` 自动配置
5. Build Command：`pip install -r requirements.txt`
6. Start Command：`gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4`（**必须单 worker**，配置存在内存里，多 worker 会导致展示链接随机 404）
7. 点击 **Deploy**，等待 2-3 分钟
8. 获得 `https://xxx.onrender.com` 公网地址

> Render 免费版 15 分钟无访问会休眠，Kindle 持续刷新会保持唤醒；休眠后首次访问约有 30 秒冷启动。

## 本地运行

```bash
pip install -r requirements.txt
python app.py
# 访问 http://localhost:5000
```

## Kindle 使用

1. 连接 WiFi → 打开「体验版浏览器」
2. 输入生成的展示链接（建议加入书签）
3. 搜索框输入 `~ds` 回车（禁止锁屏）
4. 插上电源，长期展示

## 说明

- Render 免费版不支持持久磁盘，上传的照片和配置都存于实例本地，服务重启/重新部署后需重新生成展示链接（升级到付费版可挂载磁盘持久化）
