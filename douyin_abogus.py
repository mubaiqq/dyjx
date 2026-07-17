"""Generate Douyin web API a_bogus parameters.

Adapted from Evil0ctal/Douyin_TikTok_Download_API (Apache-2.0), whose
implementation credits JoeanAmier/TikTokDownloader. Kept local so the parser
can fetch full note details, including per-image Live Photo MP4 resources.
"""

from random import choice, randint, random
from re import compile
from time import time
from urllib.parse import urlencode

from gmssl import func, sm3


class ABogus:
    __filter = compile(r'%([0-9A-F]{2})')
    __arguments = [0, 1, 14]
    __end_string = "cus"
    __browser = "1536|742|1536|864|0|0|0|0|1536|864|1536|864|1536|742|24|24|MacIntel"
    __reg = [1937774191, 1226093241, 388252375, 3666478592,
             2842636476, 372324522, 3817729613, 2969243214]
    __str = {
        "s4": "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe",
    }

    def __init__(self, platform=None):
        self.chunk = []
        self.size = 0
        self.reg = self.__reg[:]
        self.ua_code = [76, 98, 15, 131, 97, 245, 224, 133, 122, 199, 241,
                        166, 79, 34, 90, 191, 128, 126, 122, 98, 66, 11, 14,
                        40, 49, 110, 110, 173, 67, 96, 138, 252]
        self.browser = self.generate_browser_info(platform) if platform else self.__browser
        self.browser_len = len(self.browser)
        self.browser_code = self.char_code_at(self.browser)

    @classmethod
    def random_list(cls, a=None, b=170, c=85, d=0, e=0, f=0, g=0):
        r = a or random() * 10000
        v = [r, int(r) & 255, int(r) >> 8]
        return [v[1] & b | d, v[1] & c | e, v[2] & b | f, v[2] & c | g]

    @classmethod
    def generate_string_1(cls, a=None, b=None, c=None):
        return (cls.from_char_code(*cls.random_list(a, 170, 85, 1, 2, 5, 40)) +
                cls.from_char_code(*cls.random_list(b, 170, 85, 1, 0, 0, 0)) +
                cls.from_char_code(*cls.random_list(c, 170, 85, 1, 0, 5, 0)))

    def generate_string_2(self, params, method="GET", start_time=0, end_time=0):
        values = self.generate_string_2_list(params, method, start_time, end_time)
        check = self.end_check_num(values)
        values.extend(self.browser_code)
        values.append(check)
        return self.rc4_encrypt(self.from_char_code(*values), "y")

    def generate_string_2_list(self, params, method="GET", start_time=0, end_time=0):
        start_time = start_time or int(time() * 1000)
        end_time = end_time or start_time + randint(4, 8)
        p = self.sm3_to_array(self.sm3_to_array(params + self.__end_string))
        m = self.sm3_to_array(self.sm3_to_array(method + self.__end_string))
        a = self.ua_code
        return [44, (end_time >> 24) & 255, 0, 0, 0, 0, 24, p[21], m[21], 0,
                a[23], (end_time >> 16) & 255, 0, 0, 0, 1, 0, 239, p[22], m[22],
                a[24], (end_time >> 8) & 255, 0, 0, 0, 0, end_time & 255, 0, 0, 14,
                (start_time >> 24) & 255, (start_time >> 16) & 255, 0,
                (start_time >> 8) & 255, start_time & 255, 3,
                int(end_time / 256**4) >> 0, 1, int(start_time / 256**4) >> 0,
                1, self.browser_len, 0, 0, 0]

    @staticmethod
    def from_char_code(*args):
        return "".join(chr(code) for code in args)

    @staticmethod
    def end_check_num(values):
        result = 0
        for value in values:
            result ^= value
        return result

    @classmethod
    def decode_string(cls, value):
        return cls.__filter.sub(lambda m: chr(int(m.group(1), 16)), value)

    @staticmethod
    def rotate(value, bits):
        bits %= 32
        return ((value << bits) & 0xFFFFFFFF) | (value >> (32 - bits))

    @staticmethod
    def permutation(index):
        return 2043430169 if index < 16 else 2055708042

    @classmethod
    def compress(cls, block, registers):
        words = [0] * 132
        for i in range(16):
            words[i] = ((block[4*i] << 24) | (block[4*i+1] << 16) |
                        (block[4*i+2] << 8) | block[4*i+3]) & 0xFFFFFFFF
        for i in range(16, 68):
            value = words[i-16] ^ words[i-9] ^ cls.rotate(words[i-3], 15)
            value ^= cls.rotate(value, 15) ^ cls.rotate(value, 23)
            words[i] = (value ^ cls.rotate(words[i-13], 7) ^ words[i-6]) & 0xFFFFFFFF
        for i in range(68, 132):
            words[i] = (words[i-68] ^ words[i-64]) & 0xFFFFFFFF
        state = registers[:]
        for i in range(64):
            c = cls.rotate((cls.rotate(state[0], 12) + state[4] +
                            cls.rotate(cls.permutation(i), i)) & 0xFFFFFFFF, 7)
            s = (c ^ cls.rotate(state[0], 12)) & 0xFFFFFFFF
            h = ((state[0] ^ state[1] ^ state[2]) if i < 16 else
                 (state[0] & state[1] | state[0] & state[2] | state[1] & state[2]))
            u = (h + state[3] + s + words[i+68]) & 0xFFFFFFFF
            v = ((state[4] ^ state[5] ^ state[6]) if i < 16 else
                 (state[4] & state[5] | ~state[4] & state[6]))
            b = (v + state[7] + c + words[i]) & 0xFFFFFFFF
            state[3], state[2], state[1], state[0] = state[2], cls.rotate(state[1], 9), state[0], u
            state[7], state[6], state[5], state[4] = state[6], cls.rotate(state[5], 19), state[4], (b ^ cls.rotate(b, 9) ^ cls.rotate(b, 17)) & 0xFFFFFFFF
        for i in range(8):
            registers[i] = (registers[i] ^ state[i]) & 0xFFFFFFFF

    @classmethod
    def sm3_to_array(cls, data):
        raw = data.encode() if isinstance(data, str) else bytes(data)
        digest = sm3.sm3_hash(func.bytes_to_list(raw))
        return [int(digest[i:i+2], 16) for i in range(0, len(digest), 2)]

    @staticmethod
    def generate_browser_info(platform="Win32"):
        iw, ih = randint(1280, 1920), randint(720, 1080)
        ow, oh = randint(iw, 1920), randint(ih, 1080)
        return "|".join(map(str, [iw, ih, ow, oh, 0, choice((0, 30)), 0, 0,
                                  ow, oh, ow, oh, iw, ih, 24, 24, platform]))

    @staticmethod
    def char_code_at(value):
        return [ord(char) for char in value]

    @staticmethod
    def rc4_encrypt(plaintext, key):
        state = list(range(256)); j = 0
        for i in range(256):
            j = (j + state[i] + ord(key[i % len(key)])) % 256
            state[i], state[j] = state[j], state[i]
        i = j = 0; output = []
        for char in plaintext:
            i = (i + 1) % 256; j = (j + state[i]) % 256
            state[i], state[j] = state[j], state[i]
            output.append(chr(state[(state[i] + state[j]) % 256] ^ ord(char)))
        return ''.join(output)

    @classmethod
    def generate_result(cls, value):
        result = []
        alphabet = cls.__str['s4']
        for i in range(0, len(value), 3):
            chunk = value[i:i+3]
            number = ord(chunk[0]) << 16
            if len(chunk) > 1: number |= ord(chunk[1]) << 8
            if len(chunk) > 2: number |= ord(chunk[2])
            for shift, mask in zip(range(18, -1, -6), (0xFC0000, 0x03F000, 0x0FC0, 0x3F)):
                if shift == 6 and len(chunk) < 2: break
                if shift == 0 and len(chunk) < 3: break
                result.append(alphabet[(number & mask) >> shift])
        result.append("=" * ((4 - len(result) % 4) % 4))
        return "".join(result)

    def get_value(self, params, method="GET"):
        first = self.generate_string_1()
        second = self.generate_string_2(urlencode(params) if isinstance(params, dict) else params, method)
        return self.generate_result(first + second)
