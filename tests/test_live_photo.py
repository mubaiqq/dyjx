import unittest

from app import build_gallery_result, extract_live_photo_video


class LivePhotoParsingTests(unittest.TestCase):
    def test_extracts_h264_live_photo_video(self):
        image = {
            'url_list': ['https://img.example/cover.webp'],
            'width': 1080,
            'height': 1440,
            'clip_type': 3,
            'video': {
                'duration': 2967,
                'play_addr_h264': {
                    'url_list': ['https://video.example/live.mp4'],
                    'width': 720,
                    'height': 960,
                },
            },
        }
        video = extract_live_photo_video(image)
        self.assertEqual(video['url'], 'https://video.example/live.mp4')
        self.assertEqual(video['duration'], 2967)

    def test_gallery_result_preserves_static_and_motion_media(self):
        item = {
            'aweme_id': '7519121325147933952',
            'desc': '30张高清风景live实况素材',
            'author': {'nickname': '桃桃原创素材'},
            'images': [
                {
                    'url_list': ['https://img.example/1.webp'],
                    'width': 1080,
                    'height': 1440,
                    'video': {
                        'duration': 2485,
                        'play_addr': {'url_list': ['https://video.example/1.mp4']},
                    },
                },
                {
                    'url_list': ['https://img.example/2.webp'],
                    'width': 1080,
                    'height': 1440,
                },
            ],
        }
        result = build_gallery_result(item, 'https://v.douyin.com/example/')
        self.assertEqual(result['type'], 'gallery')
        self.assertEqual(result['mediaType'], 'live_photo')
        self.assertEqual(result['livePhotoCount'], 1)
        self.assertEqual(result['images'][0]['videoUrl'], 'https://video.example/1.mp4')
        self.assertEqual(result['images'][0]['duration'], 2485)
        self.assertNotIn('videoUrl', result['images'][1])


if __name__ == '__main__':
    unittest.main()
