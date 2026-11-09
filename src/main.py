import base64
import io
import json
import os
from datetime import datetime

import flet as ft
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

# ─────────────────────────────────────────────
# ① 키트 색상표 데이터 (보내주신 색상표 이미지에서 추출한 값)
#    각 항목의 levels 첫 번째가 음성(기본) 색이에요.
#    실제 키트를 찍어 보고 어긋나면 RGB 값을 고쳐 쓰면 돼요.
# ─────────────────────────────────────────────
ITEMS = [
    {
        "name": "우로빌리노겐",
        "unit": "mg/dL",
        "digits": 1,
        "neg_count": 2,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("0.1 (정상)", (254, 255, 224), 0.1),
            ("1 (16)", (254, 247, 243), 1),
            ("2 (33)", (252, 223, 218), 2),
            ("4 (66)", (249, 188, 184), 4),
            ("8 (131)", (246, 143, 158), 8),
        ],
    },
    {
        "name": "포도당",
        "unit": "mg/dL",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (129, 215, 255), None),
            ("±100 (5.5)", (165, 217, 150), 100),
            ("+250 (14)", (171, 168, 65), 250),
            ("++500 (28)", (166, 135, 82), 500),
            ("+++1000 (55)", (136, 69, 44), 1000),
        ],
    },
    {
        "name": "빌리루빈",
        "unit": "",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (254, 249, 213), None),
            ("+", (252, 233, 202), None),
            ("++", (238, 208, 185), None),
            ("+++", (212, 166, 164), None),
        ],
    },
    {
        "name": "케톤체",
        "unit": "mg/dL",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (253, 246, 221), None),
            ("±5 (0.5)", (250, 222, 208), 5),
            ("+15 (1.5)", (243, 197, 197), 15),
            ("++40 (3.9)", (200, 137, 161), 40),
            ("+++100 (10)", (155, 85, 107), 100),
        ],
    },
    {
        "name": "비중",
        "unit": "",
        "digits": 3,
        "numeric": True,  # 음성/양성이 아니라 수치로 보는 항목
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("1.000", (33, 102, 115), 1.0),
            ("1.005", (57, 110, 99), 1.005),
            ("1.010", (109, 137, 102), 1.01),
            ("1.015", (140, 157, 72), 1.015),
            ("1.020", (171, 168, 65), 1.02),
            ("1.025", (205, 179, 55), 1.025),
            ("1.030", (236, 189, 53), 1.03),
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
            ("음성", (252, 251, 67), None),
            ("용혈 +10", (195, 224, 101), 10),
            ("용혈 ++50", (121, 189, 118), 50),
            ("용혈 +++250", (44, 121, 136), 250),
            ("비용혈 +10", (237, 239, 164), 10),
            ("비용혈 ++50", (205, 223, 149), 50),
        ],
    },
    {
        "name": "pH",
        "unit": "",
        "digits": 1,
        "numeric": True,  # 음성/양성이 아니라 수치로 보는 항목
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("5", (248, 191, 120), 5),
            ("6", (250, 217, 104), 6),
            ("6.5", (228, 203, 107), 6.5),
            ("7", (195, 209, 87), 7),
            ("8", (77, 160, 104), 8),
            ("9", (53, 136, 152), 9),
        ],
    },
    {
        "name": "단백질",
        "unit": "mg/dL",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (248, 247, 105), None),
            ("trace", (233, 238, 137), None),
            ("+30 (0.3)", (218, 233, 136), 30),
            ("++100 (1.0)", (181, 213, 136), 100),
            ("+++300 (3.0)", (164, 208, 156), 300),
            ("++++1000 (10)", (127, 184, 144), 1000),
        ],
    },
    {
        "name": "아질산염",
        "unit": "",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (254, 255, 224), None),
            ("trace", (253, 231, 237), None),
            ("양성", (213, 103, 174), None),
        ],
    },
    {
        "name": "백혈구",
        "unit": "WBC/μL",
        "digits": 0,
        "neg_count": 1,  # 앞에서부터 이 개수까지는 음성(정상)
        # (이름, 기준 색 RGB, 수치) - 수치가 None이면 차트에 숫자가 없는 칸
        "levels": [
            ("음성", (254, 248, 222), None),
            ("+25", (252, 226, 198), 25),
            ("++75", (250, 224, 231), 75),
            ("+++500", (190, 149, 193), 500),
        ],
    },
]

# ─────────────────────────────────────────────
# ② 사진에서 시험지 칸 위치 설정 (필요하면 조절하세요)
#    시험지의 긴 방향 기준으로, 첫 칸~마지막 칸이 놓인 구간(0~1)
# ─────────────────────────────────────────────
PAD_START = 0.09   # 첫 번째 칸(우로빌리노겐) 중심 위치 (시험지 길이 기준 0~1)
PAD_END = 0.72     # 마지막 칸(백혈구) 중심 위치 (손잡이가 긴 시험지 기준)
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
        judge = "수치"
    else:
        judge = "음성" if idx < item.get("neg_count", 1) else "양성"
    value = estimate_value(item, rgb, idx)
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


def analyze_strip(img, flip=False):
    """시험지 사진에서 10개 칸의 색을 읽고 항목별 결과를 반환.

    사진이 가로든 세로든 상관없이, 시험지가 놓인 방향(긴 쪽)을 먼저 찾고
    그 방향을 따라 칸이 일정 간격으로 놓여 있다고 가정해요.
    세로로 놓였으면 위→아래, 가로로 놓였으면 왼쪽→오른쪽 순서예요.
    """
    w, h = img.size
    box = find_strip(img)
    if box is None:
        box = (0, 0, w, h)
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    vertical = bh >= bw
    length, width = (bh, bw) if vertical else (bw, bh)
    start = y0 if vertical else x0
    cross_center = (x0 + x1) / 2 if vertical else (y0 + y1) / 2
    n = len(ITEMS)
    spacing = (PAD_END - PAD_START) * length / (n - 1)
    along = max(2, int(spacing * ALONG_RATIO))
    across = max(2, int(width * ACROSS_RATIO / 2))

    boxes = []
    for i, item in enumerate(ITEMS):
        off = PAD_START * length + spacing * i
        pos = start + (length - off if flip else off)
        if vertical:
            b = (cross_center - across, pos - along, cross_center + across, pos + along)
        else:
            b = (pos - along, cross_center - across, pos + along, cross_center + across)
        boxes.append(clamp_box(b, w, h))
    return results_from_boxes(img, boxes), boxes


def clamp_box(b, w, h):
    """네모가 사진 밖으로 나가지 않게, 그리고 최소 2픽셀은 되게 맞춰요."""
    x0, y0 = max(0, int(b[0])), max(0, int(b[1]))
    x1 = min(w, max(int(b[2]), x0 + 2))
    y1 = min(h, max(int(b[3]), y0 + 2))
    return (x0, y0, x1, y1)


def results_from_boxes(img, boxes):
    """각 네모 안의 평균 색을 읽어서 항목별로 판정해요."""
    results = []
    for item, b in zip(ITEMS, boxes):
        avg = img.crop(tuple(b)).resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
        results.append(judge_item(item, avg))
    return results


DISPLAY_MAX = 380  # 위치 조정 화면에서 사진의 긴 쪽 길이(픽셀)


def make_clean_b64(img, scale):
    """위치 조정 화면에 깔 사진(네모 없이)을 base64로 만들어요."""
    small = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
    buf = io.BytesIO()
    small.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


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
        border=ft.border.all(1, "#cccccc"),
    )


JUDGE_COLORS = {"음성": "#2e7d32", "양성": "#c62828", "수치": "#546e7a"}


def judge_chip(judge):
    return ft.Container(
        content=ft.Text(judge, color="white", size=13),
        bgcolor=JUDGE_COLORS.get(judge, "#546e7a"),
        border_radius=10,
        padding=ft.padding.symmetric(horizontal=10, vertical=3),
    )


def overall_judge(results):
    """항목 중 하나라도 양성이면 전체 양성. (비중·pH는 수치 항목이라 제외)"""
    return "양성" if any(r.get("judge") == "양성" for r in results) else "음성"


def result_rows(results):
    """항목별 결과 한 줄씩. (측정 색 · 기준 색 · 항목 · 판정 · 단계 · 수치)"""
    rows = []
    for r in results:
        judge = r.get("judge", "")
        detail = f'{r["label"]} · 단계 {r.get("grade", 0)}/{r.get("grade_max", 0)}'
        if r.get("value") is not None:
            unit = f' {r["unit"]}' if r.get("unit") else ""
            shown = f'{r["value"]:.{r.get("digits", 0)}f}'
            detail += f' · 추정 {shown}{unit}'
        rows.append(
            ft.Row(
                [
                    swatch(r["rgb"]),
                    swatch(r["ref"]),
                    ft.Column(
                        [
                            ft.Text(r["item"], size=15, weight=ft.FontWeight.BOLD),
                            ft.Text(detail, size=12),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    judge_chip(judge),
                ],
                spacing=8,
            )
        )
    return rows


def main(page: ft.Page):
    page.title = "키트 기록"
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
    size_slider = ft.Slider(min=0.3, max=3, value=1, divisions=27, label="{value}배")
    space_slider = ft.Slider(min=0.5, max=2, value=1, divisions=30, label="{value}배")
    legend = ft.Text(
        "  ".join(f"{i + 1} {it['name']}" for i, it in enumerate(ITEMS)), size=11
    )
    editor_box = ft.Column(visible=False, spacing=8)

    def delete_record(index):
        records.pop(index)
        save_records(records)
        refresh_history()

    def make_record_view(i, r):
        """날짜 줄을 누르면 항목별 결과가 펼쳐지고 접히는 한 칸."""
        details = ft.Column(
            [
                ft.Text("색 칸: 왼쪽 측정 색, 오른쪽 기준 색", size=11),
                *result_rows(r["results"]),
                ft.TextButton(
                    "이 기록 삭제",
                    icon=ft.Icons.DELETE,
                    on_click=lambda e, idx=i: delete_record(idx),
                ),
            ],
            visible=False,
            spacing=6,
        )
        arrow = ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN)

        def toggle(e):
            details.visible = not details.visible
            arrow.name = (
                ft.Icons.KEYBOARD_ARROW_UP
                if details.visible
                else ft.Icons.KEYBOARD_ARROW_DOWN
            )
            page.update()

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text(r["date"], size=16),
                    judge_chip(overall_judge(r["results"])),
                    ft.Container(expand=True),
                    arrow,
                ],
                spacing=10,
            ),
            on_click=toggle,
            ink=True,
            padding=ft.padding.symmetric(vertical=12, horizontal=8),
            border_radius=8,
        )
        return ft.Column([header, details, ft.Divider(height=1)], spacing=0)

    def refresh_history():
        history.controls.clear()
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
        size_slider.value = 1
        space_slider.value = 1

        def make_gd(i, l, t, w, h):
            def on_pan(e):
                dx, dy = get_delta(e)
                bs = cur["boxes"]
                # 묶음이 사진 밖으로 나가지 않게 이동량을 제한
                dx = clamp(dx, -min(b[0] for b in bs), cur["dw"] - max(b[0] + b[2] for b in bs))
                dy = clamp(dy, -min(b[1] for b in bs), cur["dh"] - max(b[1] + b[3] for b in bs))
                cur["anchor"][0] += dx
                cur["anchor"][1] += dy
                apply_layout()

            return ft.GestureDetector(
                content=ft.Container(
                    width=w,
                    height=h,
                    border=ft.border.all(2, "#ff0000"),
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

        stack = ft.Stack(
            [ft.Image(src_base64=make_clean_b64(img, scale), width=dw, height=dh),
             *cur["gds"]],
            width=dw,
            height=dh,
        )
        stack_holder.controls = [stack]
        editor_title.value = (
            f"위치 조정 ({cur['done'] + 1}/{cur['total']}) · {item['taken']}"
        )
        editor_box.visible = True
        page.update()

    def apply_layout():
        """기준점 + 간격 배율 + 크기 배율로 모든 네모의 위치와 크기를 다시 계산."""
        sf, sp = size_slider.value, space_slider.value
        ax, ay = cur["anchor"]
        for j, bx in enumerate(cur["boxes"]):
            bw, bh = cur["base"][j]
            ox, oy = cur["offs"][j]
            nw = clamp(bw * sf, 8, cur["dw"])
            nh = clamp(bh * sf, 8, cur["dh"])
            bx[0] = clamp(ax + ox * sp - nw / 2, 0, cur["dw"] - nw)
            bx[1] = clamp(ay + oy * sp - nh / 2, 0, cur["dh"] - nh)
            bx[2], bx[3] = nw, nh
            g = cur["gds"][j]
            g.content.width, g.content.height = nw, nh
            g.left, g.top = bx[0], bx[1]
        stack_holder.controls[0].update()

    def on_layout_change(e):
        apply_layout()

    size_slider.on_change = on_layout_change
    space_slider.on_change = on_layout_change

    def show_next():
        if not queue:
            editor_box.visible = False
            stack_holder.controls = []
            page.update()
            return
        build_editor(queue.pop(0))

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
        results = results_from_boxes(item["img"], boxes)
        records.append({"date": item["taken"], "results": results})
        records.sort(key=lambda r: r["date"])
        save_records(records)
        result_title.value = (
            f"{item['taken']} 기록 저장 · 전체 {overall_judge(results)} "
            "(아래 기록에서 날짜를 누르면 항목별 결과가 나와요)"
        )
        cur["done"] += 1
        refresh_history()
        show_next()

    def skip_current(e):
        cur["done"] += 1
        show_next()

    def reset_boxes(e):
        item = cur["item"]
        if item is None:
            return
        item["boxes"] = analyze_strip(item["img"], flip.value)[1]
        build_editor(item)

    def on_picked(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        failed = 0
        added = []
        for f in e.files:
            try:
                img = load_image(f.path)
                _, boxes = analyze_strip(img, flip.value)
            except Exception:
                failed += 1
                continue
            taken = get_photo_datetime(f.path).strftime("%Y-%m-%d %H:%M")
            added.append({"img": img, "boxes": boxes, "taken": taken})
        if failed:
            result_title.value = f"{failed}장은 읽지 못했어요."
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
            )
            page.update()

    editor_box.controls = [
        ft.Divider(),
        editor_title,
        ft.Text(
            "빨간 네모 아무거나 손가락(마우스)으로 끌면 10개가 한꺼번에 움직여요. "
            "각 칸 위에 맞춰주세요. 번호는 아래 항목 순서예요.",
            size=12,
        ),
        ft.Text("네모 크기 (칸 안의 색만 읽히도록 조절하세요)", size=12),
        size_slider,
        ft.Text("네모 간격 (칸 사이가 넓으면 키우고, 좁으면 줄이세요)", size=12),
        space_slider,
        stack_holder,
        legend,
        ft.Row(
            [
                ft.ElevatedButton("이 위치로 저장", icon=ft.Icons.CHECK, on_click=save_current),
                ft.OutlinedButton("자동 위치로 되돌리기", on_click=reset_boxes),
                ft.TextButton("건너뛰기", on_click=skip_current),
            ],
            wrap=True,
        ),
        ft.Divider(),
    ]

    picker = ft.FilePicker(on_result=on_picked)
    page.overlay.append(picker)

    page.add(
        ft.Text("키트 기록", size=24, weight=ft.FontWeight.BOLD),
        ft.Text(
            "시험지를 흰 배경에 놓고, 사진 한가운데 크게 찍어주세요.\n"
            "첫 칸(우로빌리노겐)이 위쪽(가로면 왼쪽)에 오게 하세요."
        ),
        flip,
        ft.ElevatedButton(
            "기존 사진 불러오기",
            icon=ft.Icons.PHOTO_LIBRARY,
            on_click=lambda e: picker.pick_files(
                file_type=ft.FilePickerFileType.IMAGE,
                allow_multiple=True,
            ),
        ),
        editor_box,
        result_title,
        ft.Divider(),
        ft.Text("기록", size=20, weight=ft.FontWeight.BOLD),
        history,
    )
    refresh_history()


if __name__ == "__main__":
    ft.app(target=main)
