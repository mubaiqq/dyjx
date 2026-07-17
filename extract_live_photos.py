#!/usr/bin/env python3
"""Render a Douyin note and extract every slide's static image and Live Photo MP4."""

import json
import sys
from playwright.sync_api import sync_playwright


def collect(aweme_id):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 800, 'height': 600})
        page.goto(
            f'https://www.douyin.com/note/{aweme_id}',
            wait_until='domcontentloaded',
            timeout=30000,
        )
        page.wait_for_selector('.dySwiperSlide', timeout=20000)
        slides = page.locator('.dySwiperSlide')
        total = slides.count()
        if total == 0:
            browser.close()
            return []

        panel = page.locator('.focusPanel')
        if panel.count():
            panel.first.focus()

        result = {}
        for _ in range(total + 8):
            pairs = slides.evaluate_all("""els => els.map((el, index) => {
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
            for pair in pairs:
                previous = result.get(pair['index'], {})
                if pair.get('videoUrl') or not previous:
                    result[pair['index']] = pair
            if len(result) >= total and all(x.get('videoUrl') for x in result.values()):
                break
            page.keyboard.press('ArrowRight')
            page.wait_for_timeout(280)

        browser.close()
        return [result[index] for index in sorted(result) if result[index].get('imageUrl')]


if __name__ == '__main__':
    try:
        print(json.dumps(collect(sys.argv[1]), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
