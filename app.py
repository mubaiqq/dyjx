import re
import json
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, jsonify, send_from_directory, Response

app = Flask(__name__, static_folder='public')

HEADERS_MOBILE = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 3600


def extract_video_id(url):
    for p in [r'/video/(\d+)', r'/note/(\d+)', r'modal_id=(\d+)']:
        m = re.search(p, url)
        if m: return m.group(1)
    return None


def extract_vid_from_api(url):
    m = re.search(r'video_id=([^&]+)', url)
    return m.group(1) if m else None


def cache_get(vid):
    with _cache_lock:
        item = _cache.get(vid)
        if item and time.time() - item['ts'] < CACHE_TTL:
            return item
    return None


def cache_set(vid, data):
    with _cache_lock:
        _cache[vid] = {**data, 'ts': time.time()}
        if len(_cache) > 500:
            now = time.time()
            for k in [k for k, v in _cache.items() if now - v['ts'] > CACHE_TTL]:
                del _cache[k]


def task_resolve_redirect(url):
    """跟踪短链重定向"""
    try:
        resp = requests.get(url, headers=HEADERS_MOBILE, allow_redirects=True, timeout=10)
        return resp.url, extract_video_id(resp.url)
    except Exception:
        return url, None


def task_parse_share(url):
    """解析分享页提取信息和API URL"""
    try:
        resp = requests.get(url, headers=HEADERS_MOBILE, allow_redirects=True, timeout=12)
        html = resp.text
        final_url = resp.url

        vid = extract_video_id(final_url)
        api_urls = []
        title = ''
        author = ''

        # playApi
        for m in re.findall(r'"playApi"\s*:\s*"([^"]+)"', html):
            u = m.replace('\\u002F', '/').replace('\\/', '/')
            if u.startswith('//'): u = 'https:' + u
            api_urls.append(u)

        # play_addr url_list
        for m in re.findall(r'"play_addr".*?"url_list"\s*:\s*\["([^"]+)"', html, re.S):
            u = m.replace('\\u002F', '/').replace('\\/', '/')
            if u.startswith('//'): u = 'https:' + u
            api_urls.append(u)

        # RENDER_DATA
        rd = re.search(r'id="RENDER_DATA"[^>]*>(.*?)</script>', html, re.S)
        if rd:
            try:
                decoded = requests.utils.unquote(rd.group(1))
                data = json.loads(decoded)
                for u in deep_find_urls(data):
                    u = u.replace('\\u002F', '/').replace('\\/', '/')
                    if u.startswith('//'): u = 'https:' + u
                    api_urls.append(u)
            except Exception: pass

        tm = re.search(r'"desc"\s*:\s*"([^"]*?)"', html)
        if tm: title = tm.group(1)
        am = re.search(r'"nickname"\s*:\s*"([^"]*?)"', html)
        if am: author = am.group(1)

        return vid, api_urls, title, author
    except Exception:
        return None, [], '', ''


def task_parse_gallery(url):
    """从图文分享页的 _ROUTER_DATA 提取无水印图片。"""
    try:
        resp = requests.get(url, headers=HEADERS_MOBILE, allow_redirects=True, timeout=12)
        match = re.search(r'window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>', resp.text, re.S)
        if not match:
            return None
        router_data = json.loads(match.group(1))
        item = None
        for page_data in router_data.get('loaderData', {}).values():
            if not isinstance(page_data, dict):
                continue
            items = page_data.get('videoInfoRes', {}).get('item_list', [])
            if items:
                item = items[0]
                break
        if not item or not item.get('images'):
            return None

        images = []
        for image in item['images']:
            # url_list 是原始无水印图；download_url_list 通常带抖音水印。
            urls = image.get('url_list') or []
            if urls:
                images.append({
                    'url': urls[0],
                    'width': image.get('width', 0),
                    'height': image.get('height', 0),
                })
        if not images:
            return None

        author = item.get('author') or {}
        return {
            'code': 200,
            'type': 'gallery',
            'videoId': item.get('aweme_id') or extract_video_id(resp.url) or 'unknown',
            'title': item.get('desc') or '抖音图集',
            'author': author.get('nickname') or '未知作者',
            'images': images,
            'imageCount': len(images),
            'url': '',
            'cover': images[0]['url'],
            'sourceUrl': resp.url,
            'cached': False,
        }
    except Exception:
        return None


def task_get_video_url(video_id):
    """快速获取视频直链（多 line 并行）"""
    def fetch_line(line):
        api = f'https://www.iesdouyin.com/aweme/v1/play/?video_id={video_id}&ratio=720p&line={line}'
        try:
            resp = requests.get(api, headers=HEADERS_MOBILE, allow_redirects=False, timeout=8)
            loc = resp.headers.get('Location', '')
            return loc if loc else None
        except Exception:
            return None

    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch_line, l): l for l in [1, 2, 0]}
        for f in as_completed(futures):
            line = futures[f]
            try:
                url = f.result()
                if url: results[line] = url
            except Exception: pass

    # 优先 line=1（最快），其次 2，最后 0
    for l in [1, 2, 0]:
        if l in results:
            return results[l]
    return None


def deep_find_urls(obj, depth=0, results=None):
    if results is None: results = []
    if depth > 10 or not isinstance(obj, (dict, list)): return results
    if isinstance(obj, dict):
        for key in ['playApi', 'play_url', 'play_addr_h264', 'play_addr', 'download_addr']:
            val = obj.get(key)
            if isinstance(val, str) and ('http' in val or '//' in val):
                results.append(val)
            elif isinstance(val, dict):
                for u in val.get('url_list', []):
                    if isinstance(u, str): results.append(u)
        for k, v in obj.items():
            if isinstance(v, (dict, list)): deep_find_urls(v, depth + 1, results)
    elif isinstance(obj, list):
        for item in obj: deep_find_urls(item, depth + 1, results)
    return results


@app.route('/api/parse')
def api_parse():
    url = request.args.get('url', '').strip()
    if not url:
        return jsonify({'code': 400, 'type': 'error', 'error': '请提供 url 参数'})
    if not re.search(r'douyin\.com|iesdouyin\.com', url):
        return jsonify({'code': 400, 'type': 'error', 'error': '请输入有效的抖音分享链接'})

    # 并行执行：重定向解析 + 分享页解析
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_redirect = pool.submit(task_resolve_redirect, url)
        f_share = pool.submit(task_parse_share, url)

    real_url, vid_from_redirect = f_redirect.result()
    vid_from_page, api_urls, title, author = f_share.result()

    # 图文作品没有视频播放地址，改为读取分享页内的图片列表。
    if '/share/note/' in real_url or '/note/' in real_url:
        gallery = task_parse_gallery(real_url)
        if gallery:
            return jsonify(gallery)

    # 统一用数字视频ID做缓存key
    cache_key = vid_from_redirect or vid_from_page or extract_video_id(url) or 'unknown'
    video_id = cache_key
    title = title or '未知标题'
    author = author or '未知作者'

    # 检查缓存
    cached = cache_get(cache_key)
    if cached:
        return jsonify({
            'code': 200, 'type': 'video', 'videoId': cache_key,
            'url': cached['url'], 'title': cached.get('title', title),
            'author': cached.get('author', author),
            'cover': '', 'images': [], 'imageCount': 0,
            'sourceUrl': real_url, 'cached': True,
        })

    # 获取视频直链
    final_url = None

    # 从 api_urls 提取 video_id 并行获取
    api_vids = set()
    for api in api_urls:
        vid = extract_vid_from_api(api)
        if vid: api_vids.add(vid)
    if video_id: api_vids.add(video_id)

    if api_vids:
        with ThreadPoolExecutor(max_workers=len(api_vids)) as pool:
            futures = {pool.submit(task_get_video_url, v): v for v in api_vids}
            for f in as_completed(futures):
                try:
                    url_result = f.result()
                    if url_result:
                        final_url = url_result
                        video_id = futures[f]
                        break
                except Exception: pass

    # 兜底：跟踪 api_urls 重定向
    if not final_url and api_urls:
        for api in api_urls:
            clean = api.replace('/playwm/', '/play/')
            try:
                resp = requests.get(clean, headers=HEADERS_MOBILE, allow_redirects=False, timeout=8)
                loc = resp.headers.get('Location', '')
                if loc:
                    final_url = loc
                    break
            except Exception: continue

    if final_url:
        if final_url.startswith('//'): final_url = 'https:' + final_url
        cache_set(cache_key, {'url': final_url, 'title': title, 'author': author})
        return jsonify({
            'code': 200, 'type': 'video', 'videoId': cache_key,
            'url': final_url, 'title': title, 'author': author,
            'cover': '', 'images': [], 'imageCount': 0,
            'sourceUrl': real_url, 'cached': False,
        })

    return jsonify({
        'code': 500, 'type': 'error', 'error': '解析失败，未获取到媒体地址。',
        'videoId': video_id or 'unknown', 'sourceUrl': real_url,
    })


@app.route('/api/proxy')
def api_proxy():
    """代理抖音图片，避免浏览器端防盗链和跨域限制。"""
    url = request.args.get('url', '').strip()
    if not url or not re.match(r'^https://[^/]+(?:douyinpic\.com|byteimg\.com)/', url, re.I):
        return 'Invalid image url', 400
    try:
        upstream = requests.get(url, headers={
            **HEADERS_MOBILE,
            'Referer': 'https://www.douyin.com/',
        }, stream=True, timeout=20, allow_redirects=True)
        excluded = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}
        headers = {k: v for k, v in upstream.headers.items() if k.lower() not in excluded}
        headers['Cache-Control'] = 'public, max-age=3600'
        headers['Access-Control-Allow-Origin'] = '*'

        def generate():
            for chunk in upstream.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk

        return Response(generate(), status=upstream.status_code, headers=headers,
                        content_type=upstream.headers.get('Content-Type', 'image/webp'))
    except Exception:
        return 'Image proxy error', 502


@app.route('/')
def index():
    return send_from_directory('public', 'index.html')


@app.route('/api-docs')
@app.route('/api-docs/')
def api_docs():
    return send_from_directory('public', 'api.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5802)
