#!/usr/bin/env python3
"""Render a Douyin note and extract every slide's static image and Live Photo MP4."""

import json
import sys
from playwright.sync_api import sync_playwright


def _find_detail(value, aweme_id):
    """Find the target aweme detail inside a decoded React Server Component payload."""
    if isinstance(value, dict):
        if str(value.get('awemeId', '')) == str(aweme_id) and isinstance(value.get('images'), list):
            return value
        for child in value.values():
            result = _find_detail(child, aweme_id)
            if result:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _find_detail(child, aweme_id)
            if result:
                return result
    return None


def _src(address):
    """Read the first URL from Douyin camelCase address structures."""
    if isinstance(address, str):
        return address
    if isinstance(address, dict):
        return address.get('src') or address.get('url') or ''
    if isinstance(address, list):
        for item in address:
            url = _src(item)
            if url:
                return url
    return ''


def _extract_render_data(page, aweme_id):
    """Extract all Live Photo pairs from the complete SSR/RSC payload."""
    scripts = page.locator('script').evaluate_all(
        "els => els.map(el => el.textContent || '').filter(text => text.includes('self.__pace_f.push'))"
    )
    marker = f'\\"awemeId\\":\\"{aweme_id}\\"'
    for script in scripts:
        if marker not in script:
            continue
        prefix = 'self.__pace_f.push([1,'
        start = script.find(prefix)
        if start < 0:
            continue
        try:
            decoder = json.JSONDecoder()
            chunk, _ = decoder.raw_decode(script[start + len(prefix):])
            payload = chunk.split(':', 1)[1]
            detail = _find_detail(json.loads(payload), aweme_id)
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
        if not detail:
            continue

        result = []
        for index, image in enumerate(detail.get('images') or []):
            image_url = _src(image.get('urlList'))
            if not image_url:
                continue
            video = image.get('video') or {}
            result.append({
                'index': index,
                'imageUrl': image_url,
                'videoUrl': _src(video.get('playAddr')),
                'duration': video.get('duration', 0),
                'videoWidth': video.get('width', 0),
                'videoHeight': video.get('height', 0),
            })
        if result:
            return result
    return []


def _extract_visible_dom(page):
    """Fallback for future page variants that omit the complete RSC payload."""
    slides = page.locator('.dySwiperSlide')
    return slides.evaluate_all("""els => els.map((el, index) => {
        const image = el.querySelector('img');
        const video = el.querySelector('video');
        if (!image) return null;
        const source = video ? (video.currentSrc || video.querySelector('source')?.src || '') : '';
        return {
            index,
            imageUrl: image.currentSrc || image.src || '',
            videoUrl: source,
            duration: video && Number.isFinite(video.duration) ? Math.round(video.duration * 1000) : 0,
            videoWidth: video ? video.videoWidth : 0,
            videoHeight: video ? video.videoHeight : 0
        };
    }).filter(Boolean)""")


def collect(aweme_id):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 800})
        page.goto(
            f'https://www.douyin.com/note/{aweme_id}',
            wait_until='domcontentloaded',
            timeout=30000,
        )
        page.wait_for_selector('.dySwiperSlide', timeout=30000)
        result = _extract_render_data(page, aweme_id)
        if not result:
            result = _extract_visible_dom(page)
        browser.close()
        return result


if __name__ == '__main__':
    try:
        print(json.dumps(collect(sys.argv[1]), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
