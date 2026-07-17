# 抖音视频、图集与实况解析器

一个基于 Flask 的轻量抖音媒体解析服务，支持普通视频、图文作品（图集）和 Live Photo 实况照片。项目包含解析页面、API 文档页面和可直接调用的 JSON API。

## 最新更新

### 2026-07-17：支持抖音实况照片解析

- 自动识别包含 Live Photo 的抖音图文作品
- 从抖音完整 SSR/RSC 数据提取全部实况 MP4，不再依赖本机临时缓存
- 同时保留每张实况照片的静态原图与有声 MP4
- 返回实况视频地址、时长和分辨率
- 在线解析页面支持实况预览，并可分别下载原图和实况视频
- 媒体代理支持 MP4 Range 请求，可拖动播放进度
- 一键部署脚本下载 GitHub 失败时自动重试，并切换国内可用的加速源
- 一键部署会自动安装实况解析所需的 Chromium 及系统依赖
- API 使用 `mediaType: live_photo` 标识实况作品，使用 `images[].videoUrl` 返回实况视频

## 功能

- 抖音分享短链解析
- 普通视频无水印地址提取
- 图文作品原图列表提取
- Live Photo 实况照片及对应有声 MP4 提取
- 视频、图集与实况统一响应结构
- 图片与视频媒体代理，处理防盗链、跨域和 Range 请求
- 在线解析页面
- 完整 API 文档及在线调试
- 移动端适配

## 在线演示

- 解析器：<https://video-bak.mubaiyun.xyz>
- API 文档：<https://video-bak.mubaiyun.xyz/api-docs>

## 一键安装 / 更新

适用于 Ubuntu / Debian。脚本会自动安装必要依赖、拉取最新源码、创建 Python 虚拟环境、注册 systemd 服务、启用开机自启，并在启动后执行健康检查。以下命令使用 `main` 分支的最新版本；你也可以先下载并审阅 `deploy.sh` 后再执行。

```bash
curl -fsSL "https://raw.githubusercontent.com/mubaiqq/dyjx/main/deploy-v1.1.1.sh?$(date +%s)" | sudo bash
```

> 同一条命令可重复执行。首次运行会安装到 `/opt/dyjx`；再次运行会自动拉取 GitHub 最新版本并覆盖更新。更新失败或健康检查不通过时，会自动恢复旧版本。项目不保存业务数据，因此更新无需迁移数据。

默认配置：

| 项目 | 默认值 |
|---|---|
| 安装目录 | `/opt/dyjx` |
| systemd 服务 | `dyjx.service` |
| 监听地址 | `127.0.0.1:5800` |
| 开机自启 | 自动启用 |

常用命令：

```bash
sudo systemctl status dyjx
sudo systemctl restart dyjx
sudo journalctl -u dyjx -f
```

### 自定义安装参数

可通过环境变量覆盖默认配置：

```bash
curl -fsSL https://raw.githubusercontent.com/mubaiqq/dyjx/main/deploy.sh \
  | sudo INSTALL_DIR=/opt/dyjx PORT=5800 SERVICE_NAME=dyjx RUN_USER=www-data bash
```

支持的变量：`INSTALL_DIR`、`PORT`、`SERVICE_NAME`、`RUN_USER`、`RUN_GROUP`、`BRANCH`、`REPO_URL`。

脚本只部署后端并监听本机端口，不会自动修改 Nginx、域名或 SSL 配置。你可以自行将域名反向代理到 `http://127.0.0.1:5800`。

## 手动启动

需要 Python 3.10 或更高版本。

```bash
git clone https://github.com/mubaiqq/dyjx.git
cd dyjx
chmod +x start.sh
./start.sh
```

默认监听：

```text
127.0.0.1:5800
```

也可以手动启动：

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python app.py
```

## API

```http
GET /api/parse?url={抖音链接}
```

请求示例：

```bash
curl --get \
  --data-urlencode "url=https://v.douyin.com/xxxx/" \
  "http://127.0.0.1:5800/api/parse"
```

### 视频响应

```json
{
  "code": 200,
  "type": "video",
  "videoId": "7520000000000000000",
  "title": "作品标题",
  "author": "作者昵称",
  "url": "https://example.com/video.mp4",
  "cover": "",
  "images": [],
  "imageCount": 0,
  "sourceUrl": "https://www.iesdouyin.com/share/video/752.../",
  "cached": false
}
```

### 图集响应

```json
{
  "code": 200,
  "type": "gallery",
  "mediaType": "image",
  "videoId": "7662259898261030499",
  "title": "作品标题",
  "author": "作者昵称",
  "url": "",
  "cover": "https://example.com/cover.webp",
  "images": [
    {
      "url": "https://example.com/image.webp",
      "width": 880,
      "height": 1168
    }
  ],
  "imageCount": 1,
  "livePhotoCount": 0,
  "sourceUrl": "https://www.iesdouyin.com/share/note/766.../",
  "cached": false
}
```

### 实况照片响应

实况作品仍使用 `type: gallery`，通过 `mediaType: live_photo` 区分。每个 `images[]` 项始终保留静态原图；存在实况视频时，会额外返回 `videoUrl`、`duration`、`videoWidth` 和 `videoHeight`。

```json
{
  "code": 200,
  "type": "gallery",
  "mediaType": "live_photo",
  "videoId": "7519121325147933952",
  "title": "实况照片作品",
  "author": "作者昵称",
  "url": "",
  "cover": "https://example.com/live-cover.webp",
  "images": [
    {
      "url": "https://example.com/live-cover.webp",
      "width": 1080,
      "height": 1440,
      "videoUrl": "https://example.com/live-photo.mp4",
      "duration": 2485,
      "videoWidth": 720,
      "videoHeight": 960
    }
  ],
  "imageCount": 1,
  "livePhotoCount": 1,
  "sourceUrl": "https://www.iesdouyin.com/share/note/751.../",
  "cached": false
}
```

详细字段和接入示例见运行后的 `/api-docs` 页面。

## 项目结构

```text
.
├── app.py                 # Flask 后端与解析逻辑
├── douyin_abogus.py       # 抖音 Web API 请求参数生成
├── extract_live_photos.py # Playwright 实况媒体提取
├── deploy.sh            # 首次安装/后续更新脚本
├── public/
│   ├── index.html       # 在线解析页面
│   └── api.html         # API 文档页面
├── requirements.txt
├── start.sh
├── tests/                 # 实况解析单元测试
└── README.md
```

## 部署建议

生产环境建议使用 Gunicorn 或其他 WSGI Server，并通过 Nginx/Caddy 反向代理。媒体 CDN 地址可能包含有效期，不建议永久存储。

## 注意事项

- 本项目仅供学习和技术研究使用。
- 请遵守目标平台服务条款及所在地法律法规。
- 抖音页面结构可能调整，若上游字段变化，需要同步更新解析逻辑。