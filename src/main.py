import base64
import io
import json
import math
import os
from datetime import datetime

import flet as ft
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

try:  # 카메라 확장은 새 Flet 빌드(카메라 버전)에서만 들어 있어요
    import flet_camera as fc
except Exception:
    fc = None

# Flet 1.x 이상이면 True (예전 0.28 에는 ElevatedButton 이 있어요)
NEW_FLET = not hasattr(ft, "ElevatedButton")


def border_all(width, color):
    try:
        return ft.Border.all(width, color)
    except Exception:
        return ft.border.all(width, color)


def pad_sym(horizontal=0, vertical=0):
    try:
        return ft.Padding.symmetric(horizontal=horizontal, vertical=vertical)
    except Exception:
        return ft.padding.symmetric(horizontal=horizontal, vertical=vertical)


def make_btn(kind, text, **kw):
    """버튼 종류(elevated/outlined/text)를 Flet 버전에 맞게 만들어요."""
    if NEW_FLET:
        cls = ft.Button if kind == "elevated" else getattr(
            ft, "OutlinedButton" if kind == "outlined" else "TextButton")
        try:
            return cls(content=text, **kw)
        except TypeError:
            return cls(text, **kw)
    cls = getattr(ft, {"elevated": "ElevatedButton", "outlined": "OutlinedButton",
                       "text": "TextButton"}[kind])
    return cls(text, **kw)


def make_image(png_bytes, w, h):
    if NEW_FLET:
        return ft.Image(src=png_bytes, width=w, height=h)
    return ft.Image(src_base64=base64.b64encode(png_bytes).decode("ascii"), width=w, height=h)


def set_image(ctrl, png_bytes):
    if NEW_FLET:
        ctrl.src = png_bytes
    else:
        ctrl.src_base64 = base64.b64encode(png_bytes).decode("ascii")

# ─────────────────────────────────────────────
# ① 키트 색상표 데이터 (보내주신 색상표 이미지에서 추출한 값)
#    각 항목의 levels 첫 번째가 음성(기본) 색이에요.
#    실제 키트를 찍어 보고 어긋나면 RGB 값을 고쳐 쓰면 돼요.
# ─────────────────────────────────────────────
ITEMS_A = [
    {
        "name": "우로빌리노겐",
        "unit": "mg/dL",
        "digits": 1,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("0.1 (정상)", (252, 245, 215), 0.1),
            ("1 (16)", (253, 237, 233), 1),
            ("2 (33)", (248, 215, 209), 2),
            ("4 (66)", (243, 182, 176), 4),
            ("8 (131)", (235, 140, 153), 8),
        ],
    },
    {
        "name": "포도당",
        "unit": "mg/dL",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (126, 207, 247), None),
            ("±100 (5.5)", (159, 208, 145), 100),
            ("+250 (14)", (165, 162, 68), 250),
            ("++500 (28)", (163, 131, 79), 500),
            ("+++1000 (55)", (132, 70, 46), 1000),
        ],
    },
    {
        "name": "빌리루빈",
        "unit": "",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (252, 239, 207), None),
            ("+", (244, 223, 194), None),
            ("++", (227, 201, 178), None),
            ("+++", (204, 161, 159), None),
        ],
    },
    {
        "name": "케톤체",
        "unit": "mg/dL",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (251, 235, 212), None),
            ("±5 (0.5)", (238, 212, 197), 5),
            ("+15 (1.5)", (232, 189, 189), 15),
            ("++40 (3.9)", (193, 133, 156), 40),
            ("+++100 (10)", (150, 85, 105), 100),
        ],
    },
    {
        "name": "비중",
        "unit": "",
        "digits": 3,
        "numeric": True,  # 음성/양성이 아니라 수치로 보는 항목
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("1.000", (32, 99, 112), 1.0),
            ("1.005", (54, 107, 95), 1.005),
            ("1.010", (107, 133, 100), 1.01),
            ("1.015", (135, 153, 73), 1.015),
            ("1.020", (165, 162, 68), 1.02),
            ("1.025", (197, 173, 57), 1.025),
            ("1.030", (227, 183, 52), 1.03),
        ],
    },
    {
        "name": "잠혈",
        "unit": "RBC/μL",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        "chains": [[0, 1, 2, 3], [0, 4, 5]],  # 단계가 이어지는 순서(인덱스)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (244, 240, 67), None),
            ("용혈 +10", (188, 215, 99), 10),
            ("용혈 ++50", (117, 183, 115), 50),
            ("용혈 +++250", (43, 118, 131), 250),
            ("비용혈 +10", (240, 233, 163), 10),
            ("비용혈 ++50", (203, 214, 144), 50),
        ],
    },
    {
        "name": "pH",
        "unit": "",
        "digits": 1,
        "numeric": True,  # 음성/양성이 아니라 수치로 보는 항목
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("5", (244, 183, 117), 5),
            ("6", (249, 209, 103), 6),
            ("6.5", (220, 197, 106), 6.5),
            ("7", (188, 201, 84), 7),
            ("8", (76, 154, 103), 8),
            ("9", (51, 132, 149), 9),
        ],
    },
    {
        "name": "단백질",
        "unit": "mg/dL",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (237, 237, 102), None),
            ("trace", (225, 229, 134), None),
            ("+30 (0.3)", (212, 224, 129), 30),
            ("++100 (1.0)", (174, 204, 130), 100),
            ("+++300 (3.0)", (155, 198, 151), 300),
            ("++++1000 (10)", (123, 178, 139), 1000),
        ],
    },
    {
        "name": "아질산염",
        "unit": "",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (252, 245, 215), None),
            ("trace", (249, 223, 229), None),
            ("양성", (206, 101, 169), None),
        ],
    },
    {
        "name": "백혈구",
        "unit": "WBC/μL",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (252, 238, 214), None),
            ("+25", (243, 217, 192), 25),
            ("++75", (240, 215, 223), 75),
            ("+++500", (183, 145, 186), 500),
        ],
    },
]

# ─────────────────────────────────────────────
# 검사지 종류: 같은 회사 제품이지만 항목 순서와 색이 조금 달라요.
#   A형: 우로빌리노겐 → 포도당 → 빌리루빈 → 케톤체 → 비중 → 잠혈 → pH → 단백질 → 아질산염 → 백혈구
#   B형: 잠혈 → 빌리루빈 → 우로빌리노겐 → 케톤체 → 단백질 → 아질산염 → 포도당 → pH → 비중 → 백혈구
#   B형 색은 B형 색상표 이미지에서 추출한 값이에요.
# ─────────────────────────────────────────────
_B_COLORS = {
    "잠혈": [(246, 240, 35), (195, 217, 83), (117, 181, 105), (44, 121, 138), (244, 238, 168), (204, 214, 147)],
    "빌리루빈": [(252, 243, 212), (246, 231, 202), (231, 208, 182), (211, 170, 165)],
    "우로빌리노겐": [(253, 248, 221), (251, 241, 237), (248, 222, 218), (242, 188, 182), (232, 140, 152)],
    "케톤체": [(253, 240, 220), (242, 220, 207), (234, 197, 195), (196, 135, 154), (153, 78, 98)],
    "단백질": [(241, 239, 89), (230, 233, 125), (219, 226, 123), (181, 207, 124), (165, 202, 146), (125, 178, 132)],
    "아질산염": [(253, 248, 221), (249, 229, 234), (207, 95, 161)],
    "포도당": [(140, 206, 245), (167, 210, 141), (177, 175, 51), (165, 134, 66), (141, 68, 39)],
    "pH": [(242, 190, 114), (247, 215, 93), (224, 206, 93), (194, 205, 65), (66, 153, 93), (49, 135, 154)],
    "비중": [(33, 101, 120), (54, 113, 100), (119, 143, 105), (146, 163, 61), (177, 175, 51), (207, 186, 34), (232, 193, 20)],
    "백혈구": [(252, 242, 221), (245, 226, 201), (243, 223, 227), (191, 151, 189)],
}


def _recolor(item, colors):
    it = dict(item)
    it["levels"] = [(lv[0], tuple(c), lv[2]) for lv, c in zip(item["levels"], colors)]
    return it


_A_BY_NAME = {it["name"]: it for it in ITEMS_A}
_B_BY_NAME = {n: _recolor(_A_BY_NAME[n], c) for n, c in _B_COLORS.items()}
B_ORDER = ["잠혈", "빌리루빈", "우로빌리노겐", "케톤체", "단백질",
           "아질산염", "포도당", "pH", "비중", "백혈구"]

# 영동제약 Uriscan (10종): 항목 순서는 B형과 같고 색상표는 따로예요(첨부 비색표에서 추출).
def _it(name, unit, digits, levels, **kw):
    d = {"name": name, "unit": unit, "digits": digits, "neg_count": 1, "levels": levels}
    d.update(kw)
    return d


ITEMS_Y = [
    _it("잠혈", "RBC/μL", 0, [
        ("음성", (251, 241, 47), None),
        ("용혈 +10", (194, 216, 84), 10),
        ("용혈 ++50", (118, 180, 105), 50),
        ("용혈 +++250", (41, 121, 138), 250),
        ("비용혈 +10", (204, 224, 147), 10),
        ("비용혈 ++50", (113, 178, 159), 50),
    ], chains=[[0, 1, 2, 3], [0, 4, 5]]),
    _it("빌리루빈", "mg/dL", 1, [
        ("음성", (253, 243, 212), None),
        ("+ (0.5)", (247, 232, 205), 0.5),
        ("++ (1.0)", (233, 208, 185), 1.0),
        ("+++ (3.0)", (212, 170, 163), 3.0),
    ]),
    _it("우로빌리노겐", "mg/dL", 1, [
        ("0.1 (±)", (254, 247, 223), 0.1),
        ("+ (1)", (251, 241, 237), 1),
        ("++ (4)", (247, 223, 217), 4),
        ("+++ (8)", (239, 188, 183), 8),
        ("++++ (12)", (231, 141, 154), 12),
    ]),
    _it("케톤체", "mg/dL", 0, [
        ("음성", (252, 238, 221), None),
        ("± (5)", (243, 220, 206), 5),
        ("+ (10)", (236, 198, 196), 10),
        ("++ (50)", (196, 135, 154), 50),
        ("+++ (100)", (150, 78, 97), 100),
    ]),
    _it("단백질", "mg/dL", 0, [
        ("음성", (242, 238, 88), None),
        ("± (10)", (206, 226, 123), 10),
        ("+ (30)", (176, 204, 133), 30),
        ("++ (100)", (149, 193, 82), 100),
        ("+++ (300)", (72, 165, 97), 300),
        ("++++ (1000)", (67, 167, 181), 1000),
    ]),
    _it("아질산염", "", 0, [
        ("음성", (255, 255, 255), None),
        ("양성", (249, 169, 224), None),
    ]),
    _it("포도당", "mg/dL", 0, [
        ("음성", (138, 204, 245), None),
        ("± (100)", (167, 208, 138), 100),
        ("+ (250)", (141, 177, 58), 250),
        ("++ (500)", (106, 135, 18), 500),
        ("+++ (1000)", (124, 87, 76), 1000),
        ("++++ (2000)", (64, 43, 38), 2000),
    ]),
    _it("pH", "", 1, [
        ("5", (240, 191, 114), 5),
        ("6", (246, 214, 94), 6),
        ("7", (195, 206, 67), 7),
        ("8", (65, 153, 95), 8),
        ("9", (47, 134, 155), 9),
    ], numeric=True),
    _it("비중", "", 3, [
        ("1.000", (33, 101, 120), 1.0),
        ("1.005", (59, 113, 100), 1.005),
        ("1.010", (120, 144, 104), 1.01),
        ("1.020", (177, 174, 57), 1.02),
        ("1.025", (206, 186, 40), 1.025),
        ("1.030", (233, 193, 24), 1.03),
    ], numeric=True),
    _it("백혈구", "WBC/μL", 0, [
        ("음성", (251, 242, 221), None),
        ("+ (25)", (247, 225, 201), 25),
        ("++ (75)", (243, 223, 228), 75),
        ("+++ (500)", (151, 86, 151), 500),
    ]),
]

KITS = [
    {"id": "A", "group": "DFI (10종)", "short": "DFI A형",
     "name": "A형 (우로빌리노겐이 첫 칸)", "items": ITEMS_A},
    {"id": "B", "group": "DFI (10종)", "short": "DFI B형",
     "name": "B형 (잠혈이 첫 칸)", "items": [_B_BY_NAME[n] for n in B_ORDER]},
    {"id": "Y", "group": "영동제약 Uriscan (10종)", "short": "Uriscan",
     "name": "Uriscan (잠혈이 첫 칸)", "items": ITEMS_Y},
]
KIT_BY_ID = {k["id"]: k for k in KITS}
ITEMS = ITEMS_A  # 이전 버전 호환용(기본값)


# ─────────────────────────────────────────────
# ② 사진에서 시험지 칸 위치 설정 (필요하면 조절하세요)
#    시험지의 긴 방향 기준으로, 첫 칸~마지막 칸이 놓인 구간(0~1)
# ─────────────────────────────────────────────
# 시험지 실제 크기(mm). 자로 재서 고치면 가이드 틀과 자동 위치가 그대로 맞춰져요.
STRIP_MM = {
    "length": 120.0,  # 시험지 전체 길이 (끝에서 끝까지)
    "width": 5.5,     # 시험지 폭
    "first": 11.0,    # 시험지 끝(첫 칸 쪽)에서 첫 번째 칸 중심까지
    "pitch": 7.6,     # 칸 중심에서 다음 칸 중심까지 간격
    "pad": 5.0,       # 색 칸 하나의 한 변 길이
}
PAD_START = STRIP_MM["first"] / STRIP_MM["length"]   # 첫 칸 중심 위치 (길이 기준 0~1)
PAD_END = (STRIP_MM["first"] + 9 * STRIP_MM["pitch"]) / STRIP_MM["length"]  # 마지막(10번째) 칸
ALONG_RATIO = 0.30  # 칸 간격 대비 측정 영역 길이
ACROSS_RATIO = 0.50  # 시험지 폭 대비 측정 영역 폭(가운데 기준)

# 기록 저장 위치 (모바일에서는 앱 전용 저장소, PC에서는 현재 폴더)
DATA_DIR = os.getenv("FLET_APP_STORAGE_DATA", ".")
DATA_FILE = os.path.join(DATA_DIR, "records_v3.json")


def load_records():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_records(records):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def rgb_to_lab(rgb):
    """RGB → Lab (사람 눈 기준으로 색 차이를 재기 위한 변환)."""

    def lin(c):
        c = c / 255
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92

    r, g, b = (lin(c) for c in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (b * 0.9505 + g * 0.1192 + r * 0.0193) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def color_distance(c1, c2):
    l1, l2 = rgb_to_lab(c1), rgb_to_lab(c2)
    return sum((a - b) ** 2 for a, b in zip(l1, l2)) ** 0.5


def match_level(item, rgb):
    """항목의 기준 색들 중 가장 가까운 것의 번호를 반환."""
    dists = [color_distance(rgb, lv[1]) for lv in item["levels"]]
    return dists.index(min(dists))


def get_chain(item, idx):
    """idx 칸이 속한 단계 순서(예: 잠혈은 용혈/비용혈 두 줄)."""
    for chain in item.get("chains", [list(range(len(item["levels"])))]):
        if idx in chain:
            return chain
    return [idx]


def estimate_value(item, rgb, idx):
    """가장 가까운 칸과 이웃 칸 사이에서 측정 색의 위치를 보고 수치를 추정."""
    levels = item["levels"]
    v0 = levels[idx][2]
    if v0 is None:
        return None
    chain = get_chain(item, idx)
    pos = chain.index(idx)
    m = rgb_to_lab(rgb)
    p0 = rgb_to_lab(levels[idx][1])
    best = None  # (측정 색과 선분 사이 거리, 추정값)
    for npos in (pos - 1, pos + 1):
        if not 0 <= npos < len(chain):
            continue
        j = chain[npos]
        v1 = levels[j][2]
        if v1 is None:
            continue
        p1 = rgb_to_lab(levels[j][1])
        seg = [b - a for a, b in zip(p0, p1)]
        denom = sum(s * s for s in seg)
        if denom == 0:
            continue
        t = sum((mm - a) * s for mm, a, s in zip(m, p0, seg)) / denom
        if t <= 0:
            continue
        t = min(t, 1.0)
        point = [a + t * s for a, s in zip(p0, seg)]
        resid = sum((mm - pp) ** 2 for mm, pp in zip(m, point)) ** 0.5
        if best is None or resid < best[0]:
            best = (resid, v0 + t * (v1 - v0))
    return best[1] if best else v0


def judge_item(item, rgb):
    """한 항목의 판정(음성/양성/수치), 단계, 추정 수치를 계산."""
    idx = match_level(item, rgb)
    label, ref, _ = item["levels"][idx]
    chain = get_chain(item, idx)
    grade = chain.index(idx)
    grade_max = len(chain) - 1
    if item.get("numeric"):
        judge = "단계"
    else:
        judge = "음성" if idx < item.get("neg_count", 1) else "양성"
    value = None if item.get("numeric") else estimate_value(item, rgb, idx)
    return {
        "item": item["name"],
        "judge": judge,
        "label": label,
        "grade": grade,
        "grade_max": grade_max,
        "value": None if value is None else round(value, item.get("digits", 0)),
        "unit": item.get("unit", ""),
        "digits": item.get("digits", 0),
        "rgb": list(rgb),
        "ref": list(ref),
    }


def load_image(path):
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def find_strip(img):
    """사진에서 시험지가 차지하는 영역(x0, y0, x1, y1)을 찾아요. 못 찾으면 None."""
    small = img.copy()
    small.thumbnail((300, 300))
    sw, sh = small.size
    px = small.load()
    edge = []
    for x in range(sw):
        for y in (0, 1, sh - 2, sh - 1):
            edge.append(px[x, y])
    for y in range(sh):
        for x in (0, 1, sw - 2, sw - 1):
            edge.append(px[x, y])
    bg = tuple(sorted(c[k] for c in edge)[len(edge) // 2] for k in range(3))
    diff = ImageChops.difference(small, Image.new("RGB", small.size, bg)).convert("L")
    mask = diff.point(lambda v: 255 if v > 28 else 0).filter(ImageFilter.MedianFilter(5))
    box = mask.getbbox()
    if not box:
        return None
    x0, y0, x1, y1 = box
    if (x1 - x0) * (y1 - y0) < 0.01 * sw * sh:
        return None
    k = img.width / sw
    return (int(x0 * k), int(y0 * k), int(x1 * k), int(y1 * k))


def analyze_strip(img, flip=False, items=None):
    """시험지 사진에서 10개 칸의 색을 읽고 항목별 결과를 반환.

    사진이 가로든 세로든 상관없이, 시험지가 놓인 방향(긴 쪽)을 먼저 찾고
    그 방향을 따라 칸이 일정 간격으로 놓여 있다고 가정해요.
    세로로 놓였으면 위→아래, 가로로 놓였으면 왼쪽→오른쪽 순서예요.
    """
    w, h = img.size
    items = items or ITEMS
    box = find_strip(img)
    if box is None:
        box = (0, 0, w, h)
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    vertical = bh >= bw
    length, width = (bh, bw) if vertical else (bw, bh)
    start = y0 if vertical else x0
    cross_center = (x0 + x1) / 2 if vertical else (y0 + y1) / 2
    n = len(items)
    spacing = (PAD_END - PAD_START) * length / (n - 1)
    along = max(2, int(spacing * ALONG_RATIO))
    across = max(2, int(width * ACROSS_RATIO / 2))
    along = across = min(along, across)  # 정사각형

    boxes = []
    for i, item in enumerate(items):
        off = PAD_START * length + spacing * i
        pos = start + (length - off if flip else off)
        if vertical:
            b = (cross_center - across, pos - along, cross_center + across, pos + along)
        else:
            b = (pos - along, cross_center - across, pos + along, cross_center + across)
        boxes.append(clamp_box(b, w, h))
    return results_from_boxes(img, boxes, items), boxes


def clamp_box(b, w, h):
    """네모가 사진 밖으로 나가지 않게, 그리고 최소 2픽셀은 되게 맞춰요."""
    x0, y0 = max(0, int(b[0])), max(0, int(b[1]))
    x1 = min(w, max(int(b[2]), x0 + 2))
    y1 = min(h, max(int(b[3]), y0 + 2))
    return (x0, y0, x1, y1)


def white_gains(img, target=245):
    """사진에서 가장 밝은 부분(흰 시험지/종이)을 흰색으로 보고, 밝기·색 보정 배율(R,G,B)을 구해요."""
    small = img.copy()
    small.thumbnail((300, 300))
    px = list(small.convert("RGB").getdata())
    px.sort(key=lambda p: p[0] * 299 + p[1] * 587 + p[2] * 114)
    top = px[-max(1, len(px) // 25):]  # 가장 밝은 4%
    gains = []
    for c in range(3):
        w = sum(p[c] for p in top) / len(top)
        gains.append(min(1.8, max(0.9, target / max(w, 1))))
    return tuple(gains)


def results_from_boxes(img, boxes, items=None, gain=(1.0, 1.0, 1.0)):
    """각 네모 안의 평균 색을 읽어서 항목별로 판정해요. gain은 밝기 보정 배율(R,G,B)."""
    results = []
    for item, b in zip(items or ITEMS, boxes):
        avg = img.crop(tuple(b)).resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
        avg = tuple(min(255, int(round(v * g))) for v, g in zip(avg[:3], gain))
        results.append(judge_item(item, avg))
    return results


DISPLAY_MAX = 380  # 위치 조정 화면에서 사진의 긴 쪽 길이(픽셀)


def make_clean_b64(img, scale, gain=(1.0, 1.0, 1.0)):
    return base64.b64encode(make_clean_png(img, scale, gain)).decode("ascii")


def make_clean_png(img, scale, gain=(1.0, 1.0, 1.0)):
    """위치 조정 화면에 깔 사진(네모 없이)을 PNG 바이트로 만들어요. 밝기 보정도 반영."""
    small = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
    if any(abs(g - 1.0) > 0.005 for g in gain):
        chans = [ch.point([min(255, int(round(v * g))) for v in range(256)])
                 for ch, g in zip(small.convert("RGB").split(), gain)]
        small = Image.merge("RGB", chans)
    buf = io.BytesIO()
    small.save(buf, format="PNG")
    return buf.getvalue()


def get_delta(e):
    """드래그 이벤트에서 이동량(dx, dy)을 꺼내요. flet 버전 차이를 흡수."""
    if hasattr(e, "delta_x") and e.delta_x is not None:
        return e.delta_x, e.delta_y
    d = getattr(e, "local_delta", None) or getattr(e, "global_delta", None)
    return (d.x, d.y) if d else (0, 0)


def get_photo_datetime(path):
    """사진 촬영 시각(EXIF) → 없으면 파일 수정 시각 → 없으면 지금 시각."""
    try:
        exif = Image.open(path).getexif()
        raw = exif.get_ifd(0x8769).get(0x9003) or exif.get(0x0132)
        if raw:
            return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    try:
        return datetime.fromtimestamp(os.path.getmtime(path))
    except OSError:
        return datetime.now()


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def swatch(rgb):
    return ft.Container(
        width=22, height=22, bgcolor=rgb_to_hex(rgb), border_radius=4,
        border=border_all(1, "#cccccc"),
    )


JUDGE_COLORS = {"음성": "#2e7d32", "양성": "#c62828", "수치": "#546e7a", "단계": "#546e7a"}


def is_stage(r):
    """비중·pH처럼 음성/양성이 아니라 단계(n/N)로 보는 항목인지."""
    return r.get("judge") in ("단계", "수치")


def stage_text(r):
    """'3/7' 처럼 몇 번째 칸인지 (표준 색상표 왼쪽부터 1단계)."""
    return f'{r.get("grade", 0) + 1}/{r.get("grade_max", 0) + 1}'


def judge_chip(judge, text=None):
    return ft.Container(
        content=ft.Text(text or judge, color="white", size=13),
        bgcolor=JUDGE_COLORS.get(judge, "#546e7a"),
        border_radius=10,
        padding=pad_sym(horizontal=10, vertical=3),
    )


def overall_judge(results):
    """항목 중 하나라도 양성이면 전체 양성. (비중·pH는 수치 항목이라 제외)"""
    return "양성" if any(r.get("judge") == "양성" for r in results) else "음성"


def find_item(name, kit_id="A"):
    for it in KIT_BY_ID.get(kit_id, KITS[0])["items"]:
        if it["name"] == name:
            return it
    return None


def big_swatch(rgb, caption):
    """큰 색 칸 + 설명 글자."""
    return ft.Column(
        [
            ft.Container(
                width=70, height=50, bgcolor=rgb_to_hex(rgb), border_radius=8,
                border=border_all(1, "#999999"),
            ),
            ft.Text(caption, size=11),
            ft.Text(f"RGB {rgb[0]}, {rgb[1]}, {rgb[2]}", size=10),
        ],
        spacing=3,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def item_detail(r, kit_id="A"):
    """한 항목을 눌렀을 때 펼쳐지는 상세: 표준색, 내 결과지 색, 점수, 판정."""
    item = find_item(r["item"], kit_id)
    grade, gmax = r.get("grade", 0), r.get("grade_max", 0)
    judge = r.get("judge", "")
    diff = color_distance(r["rgb"], r["ref"])

    lines = [
        ft.Row(
            [
                big_swatch(r["rgb"], "내 결과지 색"),
                ft.Text("vs", size=13),
                big_swatch(r["ref"], "표준색 (가장 가까운 칸)"),
            ],
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        ),
        (ft.Row([ft.Text("판정", size=13, width=60),
                 judge_chip("단계", f"{stage_text(r)} 단계")], spacing=8)
         if is_stage(r) else
         ft.Row([ft.Text("판정", size=13, width=60), judge_chip(judge),
                 ft.Text(r["label"], size=13)], spacing=8)),
        (ft.Row(
            [
                ft.Text("단계", size=13, width=60),
                ft.Text(stage_text(r), size=15, weight=ft.FontWeight.BOLD),
                ft.Text("(색상표 왼쪽 첫 칸이 1단계)", size=10),
            ],
            spacing=8,
        ) if is_stage(r) else ft.Row(
            [
                ft.Text("점수", size=13, width=60),
                ft.Text(f"{grade} / {gmax}", size=15, weight=ft.FontWeight.BOLD),
                ft.Text("(0은 가장 연한 칸, 클수록 진한 칸)", size=10),
            ],
            spacing=8,
        )),
        ft.ProgressBar(
            value=((grade + 1) / (gmax + 1)) if is_stage(r) else ((grade / gmax) if gmax else 0),
            height=8),
    ]
    if r.get("value") is not None:
        unit = f' {r["unit"]}' if r.get("unit") else ""
        shown = f'{r["value"]:.{r.get("digits", 0)}f}'
        lines.append(ft.Row([ft.Text("추정 수치", size=13, width=60),
                             ft.Text(f"{shown}{unit}", size=15, weight=ft.FontWeight.BOLD)],
                            spacing=8))
    lines.append(
        ft.Text(f"색 차이 {diff:.1f} (작을수록 표준색과 비슷해요)", size=11)
    )

    if item:
        chain = get_chain(item, next(
            (i for i, lv in enumerate(item["levels"]) if lv[0] == r["label"]), 0))
        neg_n = 0 if item.get("numeric") else item.get("neg_count", 1)
        chips, neg_chips = [], []
        for i, (label, ref, _) in enumerate(item["levels"]):
            mine = label == r["label"]
            (neg_chips if i < neg_n else chips).append(
                ft.Column(
                    [
                        ft.Container(
                            width=40, height=28, bgcolor=rgb_to_hex(ref), border_radius=5,
                            border=border_all(3 if mine else 1,
                                                 "#1e88e5" if mine else "#aaaaaa"),
                        ),
                        ft.Text(label, size=9, width=52, text_align=ft.TextAlign.CENTER),
                    ],
                    spacing=2,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        lines.append(ft.Text("판독표 (파란 테두리 칸이 내 결과)", size=11))

        def group(title, color, cs):
            return ft.Container(
                content=ft.Column(
                    [ft.Text(title, size=11, color=color, weight=ft.FontWeight.BOLD),
                     ft.Row(cs, wrap=True, spacing=6, run_spacing=6)],
                    spacing=4,
                ),
                padding=6,
                border_radius=6,
                border=border_all(2, color),
            )

        groups = []
        if neg_chips:
            groups.append(group("음성", "#1e88e5", neg_chips))
        if chips:
            groups.append(group("양성" if neg_chips else "단계", "#e64a19", chips))
        lines.append(ft.Row(groups, wrap=True, spacing=8, run_spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.START))

    return ft.Container(
        content=ft.Column(lines, spacing=8),
        padding=pad_sym(horizontal=10, vertical=10),
        border_radius=10,
        border=border_all(1, "#555555"),
    )


def app_header():
    """시험지 모양 로고(10칸 색 패드) + 앱 이름."""
    pads = [
        ft.Container(width=15, height=15, border_radius=3,
                     bgcolor=rgb_to_hex(it["levels"][min(2, len(it["levels"]) - 1)][1]))
        for it in ITEMS_A
    ]
    strip = ft.Container(
        content=ft.Row(pads, spacing=3, tight=True),
        padding=pad_sym(horizontal=8, vertical=6),
        bgcolor="#f4f1ea",
        border_radius=8,
    )
    return ft.Container(
        content=ft.Column(
            [
                ft.Text("SB-kit", size=28, weight=ft.FontWeight.BOLD, color="#ffffff"),
                ft.Text("소변 시험지 판독 기록", size=12, color="#b0c4cc"),
                strip,
            ],
            spacing=6,
        ),
        bgcolor="#12303a",
        border_radius=12,
        padding=14,
    )


def chart_view(kit_id):
    """선택한 검사지 종류의 판독지(표준 색상표 전체)를 보여줘요."""
    kit = KIT_BY_ID.get(kit_id, KITS[0])
    rows = [ft.Text(f'{kit["name"]} 판독지', size=14, weight=ft.FontWeight.BOLD)]

    def chip(label, ref):
        return ft.Column(
            [
                ft.Container(width=40, height=28, bgcolor=rgb_to_hex(ref), border_radius=5,
                             border=border_all(1, "#aaaaaa")),
                ft.Text(label, size=9, width=52, text_align=ft.TextAlign.CENTER),
            ],
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def group(title, color, cs):
        return ft.Container(
            content=ft.Column(
                [ft.Text(title, size=11, color=color, weight=ft.FontWeight.BOLD),
                 ft.Row(cs, wrap=True, spacing=6, run_spacing=6)],
                spacing=4,
            ),
            padding=6,
            border_radius=6,
            border=border_all(2, color),
        )

    for item in kit["items"]:
        neg_n = 0 if item.get("numeric") else item.get("neg_count", 1)
        neg = [chip(lv[0], lv[1]) for lv in item["levels"][:neg_n]]
        pos = [chip(lv[0], lv[1]) for lv in item["levels"][neg_n:]]
        groups = []
        if neg:
            groups.append(group("음성", "#1e88e5", neg))
        if pos:
            groups.append(group("양성" if neg else "단계", "#e64a19", pos))
        unit = f' ({item["unit"]})' if item.get("unit") else ""
        rows.append(ft.Text(item["name"] + unit, size=13, weight=ft.FontWeight.BOLD))
        rows.append(ft.Row(groups, wrap=True, spacing=8, run_spacing=8,
                           vertical_alignment=ft.CrossAxisAlignment.START))
    return ft.Container(
        content=ft.Column(rows, spacing=8),
        padding=10,
        border_radius=10,
        border=border_all(1, "#555555"),
    )


def result_rows(results, kit_id="A"):
    """항목별 결과 한 줄씩. 줄을 누르면 표준색/내 색 비교 상세가 펼쳐져요."""
    rows = [ft.Text("항목을 누르면 표준색과 내 결과지 색 비교가 나와요", size=11)]
    group = []  # (detail, arrow) 목록: 하나를 펼치면 나머지는 접어요
    for r in results:
        judge = r.get("judge", "")
        if is_stage(r):
            summary = f'단계 {stage_text(r)}'
        else:
            summary = f'{r["label"]} · 단계 {r.get("grade", 0)}/{r.get("grade_max", 0)}'
        if r.get("value") is not None and not is_stage(r):
            unit = f' {r["unit"]}' if r.get("unit") else ""
            shown = f'{r["value"]:.{r.get("digits", 0)}f}'
            summary += f' · 추정 {shown}{unit}'
        detail = item_detail(r, kit_id)
        detail.visible = False
        arrow = ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN, size=20)

        group.append((detail, arrow))

        def toggle(e, detail=detail, arrow=arrow):
            opening = not detail.visible
            for d, a in group:  # 먼저 모두 접기
                d.visible = False
                a.name = ft.Icons.KEYBOARD_ARROW_DOWN
            if opening:
                detail.visible = True
                arrow.name = ft.Icons.KEYBOARD_ARROW_UP
            pg = getattr(e, "page", None)
            if pg is not None:
                pg.update()
            else:
                for d, a in group:
                    d.update()
                    a.update()

        header = ft.Container(
            content=ft.Row(
                [
                    swatch(r["rgb"]),
                    swatch(r["ref"]),
                    ft.Column(
                        [
                            ft.Text(r["item"], size=15, weight=ft.FontWeight.BOLD),
                            ft.Text(summary, size=12),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    judge_chip(judge, f"{stage_text(r)} 단계" if is_stage(r) else None),
                    arrow,
                ],
                spacing=8,
            ),
            on_click=toggle,
            ink=True,
            border_radius=8,
            padding=pad_sym(vertical=4, horizontal=2),
        )
        rows.append(ft.Column([header, detail], spacing=4))
    return rows


def main(page: ft.Page):
    page.title = "SB-kit"
    page.scroll = ft.ScrollMode.AUTO
    page.padding = 20

    records = load_records()

    result_title = ft.Text("", size=16, weight=ft.FontWeight.BOLD)
    history = ft.Column()
    flip = ft.Switch(label="시험지를 거꾸로 찍었어요 (첫 칸이 아래/오른쪽)", value=False)

    # ── 위치 조정 화면 ─────────────────────────────
    queue = []  # 아직 확인하지 않은 사진들
    cur = {"item": None, "scale": 1.0, "boxes": [], "gds": [], "dw": 0, "dh": 0,
           "done": 0, "total": 0}
    editor_title = ft.Text("", size=15, weight=ft.FontWeight.BOLD)
    stack_holder = ft.Column()
    # 1% / 1° 단위로 세밀하게 (양옆 -/+ 버튼으로 한 칸씩도 조절)
    size_slider = ft.Slider(min=30, max=300, value=100, divisions=270, label="{value}%", expand=True)
    space_slider = ft.Slider(min=50, max=200, value=100, divisions=150, label="{value}%", expand=True)
    auto_light = ft.Switch(label="자동 밝기 보정 (사진이 어둡게 찍혔을 때)", value=True)
    bright_slider = ft.Slider(min=70, max=200, value=100, divisions=130, label="{value}%", expand=True)
    angle_slider = ft.Slider(min=-45, max=45, value=0, divisions=90, label="{value}°", expand=True)
    legend = ft.Text("", size=11)
    sel = {"kit": "A"}  # 지금 선택된 검사지 종류
    chart_holder = ft.Column(visible=False)

    def refresh_chart():
        chart_holder.controls = [chart_view(sel["kit"])] if chart_holder.visible else []

    def toggle_chart(e):
        chart_holder.visible = not chart_holder.visible
        refresh_chart()
        page.update()
    kit_buttons = {}

    def kit_items(kit_id):
        return KIT_BY_ID[kit_id]["items"]

    def legend_text(kit_id):
        return "  ".join(f"{i + 1} {it['name']}" for i, it in enumerate(kit_items(kit_id)))

    def style_kit_buttons():
        for kid, b in kit_buttons.items():
            on = kid == sel["kit"]
            b.bgcolor = "#1e88e5" if on else "#37474f"
            b.color = "#ffffff"
            if NEW_FLET:  # 새 Flet에선 색이 안 먹을 수 있어 글자로도 표시
                nm = KIT_BY_ID[kid]["name"]
                b.content = ("✓ " + nm) if on else nm

    def select_kit(kit_id):
        sel["kit"] = kit_id
        style_kit_buttons()
        refresh_chart()
        # 조정 화면이 열려 있으면 그 사진(과 대기 중인 사진)에도 적용
        for it in queue:
            it["kit"] = kit_id
        if cur["item"] is not None and editor_box.visible:
            cur["item"]["kit"] = kit_id
            legend.value = legend_text(kit_id)
            editor_title.value = (
                f"위치 조정 ({cur['done'] + 1}/{cur['total']}) · {cur['item']['taken']}"
                f" · {KIT_BY_ID[kit_id]['short']}"
            )
        page.update()

    for _k in KITS:
        kit_buttons[_k["id"]] = make_btn(
            "elevated",
            _k["name"],
            expand=True,
            on_click=lambda e, kid=_k["id"]: select_kit(kid),
        )
    style_kit_buttons()
    kit_panel = ft.Column(spacing=4)
    for _g in dict.fromkeys(k["group"] for k in KITS):
        kit_panel.controls.append(ft.Text(_g, size=13, weight=ft.FontWeight.BOLD))
        kit_panel.controls.append(
            ft.Row([kit_buttons[k["id"]] for k in KITS if k["group"] == _g], spacing=8))
    editor_box = ft.Column(visible=False, spacing=8)

    def delete_record(index):
        records.pop(index)
        save_records(records)
        refresh_history()

    open_views = []  # 날짜별 (펼침 영역, 화살표)

    def make_record_view(i, r):
        """날짜 줄을 누르면 항목별 결과가 펼쳐지고 접히는 한 칸."""
        details = ft.Column(
            [
                ft.Text("색 칸: 왼쪽 측정 색, 오른쪽 기준 색", size=11),
                *result_rows(r["results"], r.get("kit", "A")),
                make_btn(
                    "text",
                    "이 기록 삭제",
                    icon=ft.Icons.DELETE,
                    on_click=lambda e, idx=i: delete_record(idx),
                ),
            ],
            visible=False,
            spacing=6,
        )
        arrow = ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN)

        open_views.append((details, arrow))

        def toggle(e):
            opening = not details.visible
            for d, a in open_views:  # 다른 날짜는 모두 접기
                d.visible = False
                a.name = ft.Icons.KEYBOARD_ARROW_DOWN
            if opening:
                details.visible = True
                arrow.name = ft.Icons.KEYBOARD_ARROW_UP
            page.update()

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text(r["date"], size=16),
                    judge_chip(overall_judge(r["results"])),
                    ft.Text(KIT_BY_ID.get(r.get("kit", "A"), KITS[0])["short"], size=12),
                    ft.Container(expand=True),
                    arrow,
                ],
                spacing=10,
            ),
            on_click=toggle,
            ink=True,
            padding=pad_sym(vertical=12, horizontal=8),
            border_radius=8,
        )
        return ft.Column([header, details, ft.Divider(height=1)], spacing=0)

    def refresh_history():
        history.controls.clear()
        open_views.clear()
        for i in reversed(range(len(records))):
            history.controls.append(make_record_view(i, records[i]))
        page.update()

    def clamp(v, lo, hi):
        return max(lo, min(hi, v))

    def build_editor(item):
        """한 장의 사진을 빨간 네모와 함께 보여주는 조정 화면을 만들어요."""
        img = item["img"]
        # 화면 폭(폰은 좁음)에 맞춰 사진 표시 크기를 정해요
        avail_w = min((page.width or 460) - 40, DISPLAY_MAX)
        scale = min(avail_w / img.width, 520 / img.height)
        dw, dh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        cur["centers"] = []
        cur.update(item=item, scale=scale, dw=dw, dh=dh, boxes=[], gds=[], base=[])
        size_slider.value = 100
        space_slider.value = 100
        angle_slider.value = 0
        bright_slider.value = 100

        def on_pan(e):
            dx, dy = get_delta(e)
            bs = cur["boxes"]
            # 묶음이 사진 밖으로 나가지 않게 이동량을 제한
            dx = clamp(dx, -min(b[0] for b in bs), cur["dw"] - max(b[0] + b[2] for b in bs))
            dy = clamp(dy, -min(b[1] for b in bs), cur["dh"] - max(b[1] + b[3] for b in bs))
            cur["anchor"][0] += dx
            cur["anchor"][1] += dy
            apply_layout()

        def make_gd(i, l, t, w, h):
            return ft.GestureDetector(
                content=ft.Container(
                    width=w,
                    height=h,
                    border=border_all(2, "#ff0000"),
                    content=ft.Text(str(i + 1), size=9, color="#ff0000"),
                ),
                on_pan_update=on_pan,
                drag_interval=15,
                left=l,
                top=t,
            )

        for i, (x0, y0, x1, y1) in enumerate(item["boxes"]):
            w = max(18.0, (x1 - x0) * scale)
            h = max(18.0, (y1 - y0) * scale)
            l = clamp(x0 * scale, 0, dw - w)
            t = clamp(y0 * scale, 0, dh - h)
            cur["boxes"].append([l, t, w, h])
            cur["base"].append((w, h))
            cur.setdefault("centers", []).append((l + w / 2, t + h / 2))
            cur["gds"].append(make_gd(i, l, t, w, h))

        cs = cur["centers"]
        cur["anchor"] = [sum(c[0] for c in cs) / len(cs), sum(c[1] for c in cs) / len(cs)]
        cur["offs"] = [(c[0] - cur["anchor"][0], c[1] - cur["anchor"][1]) for c in cs]

        handle = ft.GestureDetector(
            content=ft.Container(
                width=HANDLE, height=HANDLE, bgcolor="#1e88e5", border_radius=HANDLE / 2,
                border=border_all(2, "#ffffff"),
                content=ft.Icon(ft.Icons.OPEN_WITH, color="#ffffff", size=26),
            ),
            on_pan_update=on_pan,
            drag_interval=15,
            left=0,
            top=0,
        )
        cur["handle"] = handle
        place_handle()

        stack = ft.Stack(
            [make_image(make_clean_png(img, scale, gain_for(item)), dw, dh),
             *cur["gds"], handle],
            width=dw,
            height=dh,
        )
        stack_holder.controls = [stack]
        kid = item.get("kit", sel["kit"])
        legend.value = legend_text(kid)
        editor_title.value = (
            f"위치 조정 ({cur['done'] + 1}/{cur['total']}) · {item['taken']}"
            f" · {KIT_BY_ID[kid]['short']}"
        )
        editor_box.visible = True
        page.update()

    HANDLE = 46  # 잡는 버튼 크기

    def place_handle():
        """파란 잡는 버튼을 네모 묶음 옆(공간 없으면 반대편)에 놓아요."""
        bs, h = cur["boxes"], cur.get("handle")
        if not bs or h is None:
            return
        minl = min(b[0] for b in bs)
        maxr = max(b[0] + b[2] for b in bs)
        mint = min(b[1] for b in bs)
        maxb = max(b[1] + b[3] for b in bs)
        gap = 8
        if (maxb - mint) >= (maxr - minl):  # 세로로 긴 묶음 → 옆에
            x = maxr + gap
            if x + HANDLE > cur["dw"]:
                x = minl - gap - HANDLE
            y = (mint + maxb) / 2 - HANDLE / 2
        else:  # 가로로 긴 묶음 → 아래(없으면 위)에
            y = maxb + gap
            if y + HANDLE > cur["dh"]:
                y = mint - gap - HANDLE
            x = (minl + maxr) / 2 - HANDLE / 2
        h.left = clamp(x, 0, cur["dw"] - HANDLE)
        h.top = clamp(y, 0, cur["dh"] - HANDLE)

    def apply_layout():
        """기준점 + 간격 배율 + 크기 배율로 모든 네모의 위치와 크기를 다시 계산."""
        sf, sp = size_slider.value / 100, space_slider.value / 100
        ax, ay = cur["anchor"]
        rad = math.radians(angle_slider.value)
        ca, sa = math.cos(rad), math.sin(rad)
        for j, bx in enumerate(cur["boxes"]):
            bw, bh = cur["base"][j]
            ox, oy = cur["offs"][j]
            rx, ry = ox * ca - oy * sa, ox * sa + oy * ca  # 묶음 전체를 기준점 둘레로 회전
            nw = clamp(bw * sf, 8, cur["dw"])
            nh = clamp(bh * sf, 8, cur["dh"])
            bx[0] = clamp(ax + rx * sp - nw / 2, 0, cur["dw"] - nw)
            bx[1] = clamp(ay + ry * sp - nh / 2, 0, cur["dh"] - nh)
            bx[2], bx[3] = nw, nh
            g = cur["gds"][j]
            g.content.width, g.content.height = nw, nh
            g.left, g.top = bx[0], bx[1]
        place_handle()
        stack_holder.controls[0].update()

    def on_layout_change(e):
        apply_layout()

    def gain_for(item):
        """자동 보정 배율(사진마다 한 번만 계산) × 수동 밝기."""
        if auto_light.value:
            if item.get("gains") is None:
                item["gains"] = white_gains(item["img"])
            base = item["gains"]
        else:
            base = (1.0, 1.0, 1.0)
        b = bright_slider.value / 100
        return tuple(g * b for g in base)

    def refresh_preview(e=None):
        item = cur.get("item")
        if item is None or not stack_holder.controls:
            return
        set_image(stack_holder.controls[0].controls[0],
                  make_clean_png(item["img"], cur["scale"], gain_for(item)))
        stack_holder.controls[0].update()

    size_slider.on_change = on_layout_change
    space_slider.on_change = on_layout_change
    angle_slider.on_change = on_layout_change
    auto_light.on_change = refresh_preview
    bright_slider.on_change = refresh_preview

    def slider_row(sl, step):
        """슬라이더 양옆에 -/+ 버튼을 붙여 한 칸씩 미세 조절."""
        def nudge(d):
            sl.value = clamp(round(sl.value + d * step), sl.min, sl.max)
            if cur.get("item") is not None and stack_holder.controls:
                (refresh_preview if sl is bright_slider else lambda: apply_layout())()
            page.update()
        return ft.Row(
            [
                ft.IconButton(icon=ft.Icons.REMOVE, on_click=lambda e: nudge(-1)),
                sl,
                ft.IconButton(icon=ft.Icons.ADD, on_click=lambda e: nudge(1)),
            ],
            spacing=0,
        )

    def show_next():
        if not queue:
            editor_box.visible = False
            stack_holder.controls = []
            page.update()
            return
        build_editor(queue.pop(0))

    def finish_record(item, boxes):
        """네모 위치(사진 좌표)로 색을 읽어 판정하고 기록으로 저장해요."""
        kid = item.get("kit", sel["kit"])
        results = results_from_boxes(item["img"], boxes, kit_items(kid), gain_for(item))
        records.append({"date": item["taken"], "kit": kid, "results": results})
        records.sort(key=lambda r: r["date"])
        save_records(records)
        result_title.value = (
            f"{item['taken']} 기록 저장 · 전체 {overall_judge(results)} "
            "(아래 기록에서 날짜를 누르면 항목별 결과가 나와요)"
        )
        refresh_history()
        return results

    def save_current(e):
        item = cur["item"]
        if item is None:
            return
        s_ = cur["scale"]
        boxes = [
            clamp_box((l / s_, t / s_, (l + w) / s_, (t + h) / s_),
                      item["img"].width, item["img"].height)
            for l, t, w, h in cur["boxes"]
        ]
        finish_record(item, boxes)
        cur["done"] += 1
        show_next()

    def skip_current(e):
        cur["done"] += 1
        show_next()

    def reset_boxes(e):
        item = cur["item"]
        if item is None:
            return
        item["boxes"] = analyze_strip(
            item["img"], flip.value, kit_items(item.get("kit", sel["kit"]))
        )[1]
        build_editor(item)

    def handle_paths(paths):
        """고른 사진 파일들을 읽어서 위치 조정 대기열에 넣어요."""
        failed = 0
        pairs = []
        for p in paths:
            try:
                img = load_image(p)
            except Exception:
                failed += 1
                continue
            pairs.append((img, get_photo_datetime(p).strftime("%Y-%m-%d %H:%M")))
        if failed:
            result_title.value = f"{failed}장은 읽지 못했어요."
        add_images(pairs)

    def on_picked(e):
        if e.files:
            handle_paths([f.path for f in e.files])

    def add_images(pairs):
        added = []
        for entry in pairs:
            img, taken = entry[0], entry[1]
            try:
                if len(entry) > 2 and entry[2]:
                    boxes = entry[2]  # 카메라 가이드 위치 그대로
                else:
                    _, boxes = analyze_strip(img, flip.value, kit_items(sel["kit"]))
            except Exception:
                continue
            added.append({"img": img, "boxes": boxes, "taken": taken, "kit": sel["kit"]})
        if not added:
            page.update()
            return
        was_empty = not editor_box.visible
        queue.extend(added)
        if was_empty:
            cur["done"], cur["total"] = 0, len(added)
            show_next()
        else:
            cur["total"] += len(added)
            editor_title.value = (
                f"위치 조정 ({cur['done'] + 1}/{cur['total']}) · {cur['item']['taken']}"
                f" · {KIT_BY_ID[cur['item'].get('kit', sel['kit'])]['short']}"
            )
            page.update()

    editor_box.controls = [
        ft.Divider(),
        editor_title,
        ft.Text(
            "파란 ✥ 버튼(또는 빨간 네모)을 끌면 10개가 한꺼번에 움직여요. "
            "각 칸 위에 맞춰주세요. 번호는 아래 항목 순서예요.",
            size=12,
        ),
        ft.Text("네모 크기 (칸 안의 색만 읽히도록 조절하세요)", size=12),
        slider_row(size_slider, 1),
        ft.Text("네모 간격 (칸 사이가 넓으면 키우고, 좁으면 줄이세요)", size=12),
        slider_row(space_slider, 1),
        ft.Text("각도 (시험지가 기울어 찍혔으면 맞춰 돌리세요)", size=12),
        slider_row(angle_slider, 1),
        ft.Text("사진 밝기 (실제보다 어둡게 읽히면 올리세요. 자동 보정 위에 더해져요)", size=12),
        auto_light,
        slider_row(bright_slider, 1),
        stack_holder,
        legend,
        ft.Row(
            [
                make_btn("elevated", "이 위치로 저장", icon=ft.Icons.CHECK, on_click=save_current),
                make_btn("outlined", "자동 위치로 되돌리기", on_click=reset_boxes),
                make_btn("text", "건너뛰기", on_click=skip_current),
            ],
            wrap=True,
        ),
        ft.Divider(),
    ]

    if NEW_FLET:
        picker = ft.FilePicker()
        page.services.append(picker)
    else:
        picker = ft.FilePicker(on_result=on_picked)
        page.overlay.append(picker)

    async def pick_new(e):
        files = await picker.pick_files(file_type=ft.FilePickerFileType.IMAGE,
                                        allow_multiple=True)
        if files:
            handle_paths([f.path for f in files])

    def pick_old(e):
        picker.pick_files(file_type=ft.FilePickerFileType.IMAGE, allow_multiple=True)

    # ── 앱 안 카메라 (카메라 버전 빌드에서만 보여요) ─────────────
    camera = fc.Camera(expand=True, preview_enabled=True) if (fc and NEW_FLET) else None
    cam = {"ready": False, "cams": [], "idx": 0}
    cam_status = ft.Text("", size=12)
    cam_box = ft.Column(visible=False, spacing=8)

    async def start_cam():
        await camera.initialize(
            description=cam["cams"][cam["idx"]],
            resolution_preset=getattr(fc.ResolutionPreset, "HIGH", fc.ResolutionPreset.MEDIUM),
            enable_audio=False,
            image_format_group=fc.ImageFormatGroup.JPEG,
        )
        cam["ready"] = True
        cam_status.value = "준비 완료: 시험지가 화면에 크게 들어오게 하고 촬영 버튼을 누르세요."

    async def open_camera(e):
        cam_box.visible = True
        cam_status.value = "카메라 준비 중..."
        page.update()
        try:
            if not cam["ready"]:
                cam["cams"] = await camera.get_available_cameras()
                if not cam["cams"]:
                    cam_status.value = "카메라를 찾지 못했어요."
                else:
                    await start_cam()
        except Exception as ex:
            cam_status.value = f"카메라 오류: {ex}"
        page.update()

    async def switch_cam(e):
        if not cam["cams"]:
            return
        cam["idx"] = (cam["idx"] + 1) % len(cam["cams"])
        try:
            await start_cam()
        except Exception as ex:
            cam_status.value = f"카메라 오류: {ex}"
        page.update()

    async def snap_cam(e):
        try:
            data = await camera.take_picture()
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        except Exception as ex:
            cam_status.value = f"촬영 오류: {ex}"
            page.update()
            return
        if img.width > img.height:  # 가로로 저장됐으면 세로로 돌려요
            img = img.rotate(-90, expand=True)
        taken = datetime.now().strftime("%Y-%m-%d %H:%M")
        boxes = guide_boxes_for(img)
        cam_box.visible = False
        if auto_read.value:
            item = {"img": img, "kit": sel["kit"], "taken": taken}
            res = finish_record(item, boxes)
            result_title.value += f" (카메라 바로 판독: {overall_judge(res)})"
            page.update()
            return
        add_images([(img, taken, boxes)])

    async def close_cam(e):
        cam_box.visible = False
        page.update()

    # 카메라 화면 위에 올리는 가이드: 시험지를 맞출 흰 선 + 10칸 빨간 네모
    cam_w = int(min((page.width or 400) - 40, 380))
    cam_h = int(cam_w * 4 / 3)
    STRIP_TOP, STRIP_LEN = 0.06, 0.88  # 화면 높이 대비 시험지 위치/길이
    n_pad = 10
    mm = cam_h * STRIP_LEN / STRIP_MM["length"]   # 화면에서 1mm가 차지하는 픽셀
    SIDE_PX = STRIP_MM["pad"] * mm                # 실제 칸 크기와 같은 한 변
    STRIP_W_PX = STRIP_MM["width"] * mm           # 실제 시험지 폭
    guide_y = [STRIP_TOP + (STRIP_MM["first"] + i * STRIP_MM["pitch"]) * mm / cam_h
               for i in range(n_pad)]              # 각 칸 중심 (화면 높이 대비)

    def guide_boxes_for(img):
        """가이드의 네모 위치를 찍힌 사진 좌표로 바꿔요. 읽는 영역은 칸 안쪽 70%."""
        w, h = img.size
        half = SIDE_PX * 0.7 / cam_w * w / 2
        return [clamp_box((w / 2 - half, y * h - half, w / 2 + half, y * h + half), w, h)
                for y in guide_y]

    auto_read = ft.Switch(label="찍은 뒤 위치 확인 없이 바로 판독·저장", value=False)

    def make_guide():
        items_ = [
            ft.Container(width=cam_w, height=cam_h, content=camera),
            ft.Container(
                left=cam_w / 2 - STRIP_W_PX / 2, top=cam_h * STRIP_TOP,
                width=STRIP_W_PX, height=cam_h * STRIP_LEN,
                border=border_all(1, "#ccffffff"), border_radius=3,
            ),
        ]
        for i, y in enumerate(guide_y):
            items_.append(ft.Container(
                left=cam_w / 2 - SIDE_PX / 2, top=y * cam_h - SIDE_PX / 2,
                width=SIDE_PX, height=SIDE_PX, border=border_all(1, "#ff0000"),
                content=ft.Text(str(i + 1), size=8, color="#ff0000"),
            ))
        return ft.Container(
            content=ft.Stack(items_, width=cam_w, height=cam_h),
            width=cam_w, height=cam_h, bgcolor="#000000", border_radius=8,
        )

    if camera is not None:
        cam_box.controls = [
            ft.Text("흰 선 안에 시험지를 세로로 놓고, 첫 칸이 빨간 1번에 오게 맞춘 뒤 촬영하세요.",
                    size=12),
            make_guide(),
            auto_read,
            cam_status,
            ft.Row(
                [
                    make_btn("elevated", "촬영", icon=ft.Icons.PHOTO_CAMERA, on_click=snap_cam),
                    make_btn("outlined", "카메라 전환", on_click=switch_cam),
                    make_btn("text", "닫기", on_click=close_cam),
                ],
                wrap=True,
            ),
        ]

    page.add(
        app_header(),
        ft.Text("검사지 종류를 고르세요 (색상표의 항목 순서를 보고 맞는 것을 선택)", size=12),
        kit_panel,
        ft.Text(
            "시험지를 흰 배경에 놓고, 사진 한가운데 크게 찍어주세요.\n"
            "선택한 종류의 첫 칸이 위쪽(가로면 왼쪽)에 오게 하세요."
        ),
        ft.Text(
            "💡 사진에 흰색이 보여야 밝기 보정이 잘돼요. 시험지의 흰 부분이나 "
            "흰 종이가 함께 찍히게 하세요. 어두운 배경에 시험지만 크게 찍으면 "
            "보정 기준이 흐려질 수 있어요.",
            size=12,
            color="#ffb300",
        ),
        flip,
        make_btn("elevated", "기존 사진 불러오기", icon=ft.Icons.PHOTO_LIBRARY,
                 on_click=pick_new if NEW_FLET else pick_old),
        *([make_btn("elevated", "카메라로 바로 찍기", icon=ft.Icons.PHOTO_CAMERA,
                    on_click=open_camera), cam_box] if camera is not None else []),
        make_btn("outlined", "판독지 보기 / 닫기", icon=ft.Icons.PALETTE, on_click=toggle_chart),
        chart_holder,
        editor_box,
        result_title,
        ft.Divider(),
        ft.Text("기록", size=20, weight=ft.FontWeight.BOLD),
        history,
    )
    refresh_history()


if __name__ == "__main__":
    if NEW_FLET:
        ft.run(main)
    else:
        ft.app(target=main)
