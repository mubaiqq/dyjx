# 抖音视频与图集解析器

一个基于 Flask 的轻量抖音媒体解析服务，支持普通视频和图文作品（图集）。项目包含解析页面、API 文档页面和可直接调用的 JSON API。

## 功能

- 抖音分享短链解析
- 普通视频无水印地址提取
- 图文作品原图列表提取
- 视频与图集统一响应结构
- 图集图片代理，处理防盗链与跨域限制
- 在线解析页面
- 完整 API 文档及在线调试
- 移动端适配

## 在线演示

- 解析器：<https://video-bak.mubaiyun.xyz>
- API 文档：<https://video-bak.mubaiyun.xyz/api-docs>

## 快速启动

需要 Python 3.10 或更高版本。

```bash
git clone https://github.com/mubaiqq/douyin-media-parser.git
cd douyin-media-parser
chmod +x start.sh
./start.sh
```

默认监听：

```text
127.0.0.1:5802
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
  "http://127.0.0.1:5802/api/parse"
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
  "sourceUrl": "https://www.iesdouyin.com/share/note/766.../",
  "cached": false
}
```

详细字段和接入示例见运行后的 `/api-docs` 页面。

## 项目结构

```text
.
├── app.py               # Flask 后端与解析逻辑
├── public/
│   ├── index.html       # 在线解析页面
│   └── api.html         # API 文档页面
├── requirements.txt
├── start.sh
└── README.md
```

## 部署建议

生产环境建议使用 Gunicorn 或其他 WSGI Server，并通过 Nginx/Caddy 反向代理。媒体 CDN 地址可能包含有效期，不建议永久存储。

## 注意事项

- 本项目仅供学习和技术研究使用。
- 请遵守目标平台服务条款及所在地法律法规。
- 抖音页面结构可能调整，若上游字段变化，需要同步更新解析逻辑。
