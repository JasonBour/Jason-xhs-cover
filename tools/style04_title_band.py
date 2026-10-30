# -*- coding: utf-8 -*-
"""
样式 04 · 斜字压顶 / Italic Title Band
================================================================
顶部一行超大斜切标题（蓝字），底部两行白字，中间留人。
文字下面压一条「蓝调暗化底带」（backdrop），让白字从任何底图上浮出来。
参考图里的「上集」角标、订阅按钮、姓名条**一律不做** —— 只留上下两行 + 底带。

和样式02 的区别
  02：顶行小（宋体标签）+ 底部大字，无底带，只靠阴影托字
  04：顶行超大（黑体斜切）+ 底部两行，有蓝调暗化底带（这版的核心）

设计常量（相对画布 W / H，换画布也成立）
  标题墨迹宽   0.860 W   ← 硬约束：与字数无关，字号是变量
  标题斜切     28°       ← 向右倾，模拟斜体；宽度反解时按剪切后的实际墨迹算
  标题顶边距   0.050 H   ← 墨迹顶边到画布顶（不贴边）
  底行末行宽   0.905 W   ← 落点行，最大
  底行引导宽   0.700 W   ← 前面几行，明显小一档（一行大一行小）
  末行底边距   0.045 H   ← 不贴底
  底行行隙     0.018 H   ← 参考图两行贴得紧
  底带         --veil auto：从 0.46H 起向上渐隐，向下加深到 peak（深蓝黑）
  对齐         标题居中 / 底行左对齐（参考图特征），--align center 可切

用法
  python style04_title_band.py --base 底图.png --out 封面.png \
      --split "隐藏天赋|如何用 AI 找到|属于自己的天赋"
  python style04_title_band.py --base 底图.png --out 封面.png \
      --top "隐藏天赋" --bottom "如何用 AI 找到属于自己的天赋"
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

TITLE_FONTS = {
    'noto':  (r'C:\Windows\Fonts\NotoSansSC-VF.ttf', 900),    # 思源黑 Heavy（默认，最接近参考图）
    'yahei': (r'C:\Windows\Fonts\msyhbd.ttc', None),
    'heiti': (r'C:\Windows\Fonts\simhei.ttf', None),
    'serif': (r'C:\Windows\Fonts\NotoSerifSC-VF.ttf', 900),
}
BOT_FONTS = {
    'noto':  (r'C:\Windows\Fonts\NotoSansSC-VF.ttf', 900),
    'yahei': (r'C:\Windows\Fonts\msyhbd.ttc', None),
    'heiti': (r'C:\Windows\Fonts\simhei.ttf', None),
    'serif': (r'C:\Windows\Fonts\NotoSerifSC-VF.ttf', 900),
}

TITLE_W = 0.860        # 标题墨迹宽 / 画布宽
TITLE_INSET = 0.050    # 标题墨迹顶边距 / 画布高
ITALIC = 22.0          # 斜切角度（度），向右倾
TITLE_STROKE = 0.030   # 描边 / 字号（参考图有一圈很薄的浅边）
TITLE_STROKE_COLOR = '#EAF4FF'

BOT_W = 0.905          # 末行墨迹宽 / 画布宽（落点）
BOT_W_LEAD = 0.800     # 前几行墨迹宽 / 画布宽（引导）
BOT_INSET = 0.045      # 末行墨迹底边距 / 画布高
BOT_GAP = 0.018        # 底行行间空隙 / 画布高
BOT_LEFT = 0.038       # 底行左边距 / 画布宽（左对齐时）

MIN_SIZE = 0.055
MAX_SIZE = 0.420       # 顶行 2-4 字时会放得很大

TITLE_COLOR = '#4490DC'   # 参考图实测：标题蓝 (68,144,220)
INK = '#FFFFFF'

VEIL_COLOR = '#0E2352'    # 底带：深蓝黑（不是纯黑，底图会保持蓝调）
VEIL_PEAK = 185           # 底带最浓处 alpha
VEIL_TOP = 0.46           # 底带从这一行开始向上渐隐

SHADOW_ALPHA = 210
SHADOW_DY = 0.0055
SHADOW_DX = 0.0016
SHADOW_BLUR = 0.0030
TITLE_SHADOW_ALPHA = 175


def hex2rgba(h, alpha=255):
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def crop_to_ratio(img, ratio, focus=0.35):
    w, h = img.size
    if w / h > ratio:
        nw = int(h * ratio)
        x0 = (w - nw) // 2
        return img.crop((x0, 0, x0 + nw, h))
    if w / h < ratio:
        nh = int(w / ratio)
        y0 = max(0, int((h - nh) * focus))
        return img.crop((0, y0, w, y0 + nh))
    return img


def make_font(presets, preset, size):
    path, weight = presets.get(preset, list(presets.values())[0])
    if not os.path.exists(path):
        for p, w in presets.values():
            if os.path.exists(p):
                path, weight = p, w
                break
    f = ImageFont.truetype(path, max(8, int(size)))
    if weight:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


# ------------------------------------------------------------ 断行

def _units(text):
    buf, out = '', []
    for ch in text:
        if ch.isascii() and not ch.isspace():
            buf += ch
        else:
            if buf:
                out.append(buf)
                buf = ''
            out.append(ch)
    if buf:
        out.append(buf)
    return out


NO_START = '的了着地得吗呢吧啊呀！？。，、；：）」』】…—'
NO_END = '（「『【《'


def _fix(units):
    out = []
    for u in units:
        if out and (u[0] in NO_START or out[-1][-1] in NO_END):
            out[-1] += u
        else:
            out.append(u)
    return out


def auto_split(text, n=2):
    """按视觉宽度尽量均分的 n 行断行"""
    units = _fix(_units(text.strip()))
    if n >= len(units):
        return units
    w = [1.0 if not (u[0].isascii() and not u[0].isspace()) else 0.55 * len(u)
         for u in units]
    m = len(units)
    INF = float('inf')
    dp = [[(INF, -1)] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = (0.0, -1)
    for k in range(1, n + 1):
        for i in range(1, m + 1):
            best, acc = (INF, -1), 0.0
            for j in range(i - 1, -1, -1):
                acc += w[j]
                if dp[k - 1][j][0] == INF:
                    continue
                val = max(dp[k - 1][j][0], acc)
                if val <= best[0]:
                    best = (val, j)
            dp[k][i] = best
    if dp[n][m][1] < 0:
        return [text]
    cuts, i = [], m
    for k in range(n, 0, -1):
        j = dp[k][i][1]
        cuts.append((j, i))
        i = j
    cuts.reverse()
    return [''.join(units[a:b]).strip() for a, b in cuts if ''.join(units[a:b]).strip()]


# ------------------------------------------------------------ 单行渲染

def draw_line(text, presets, preset, size, color, italic=0.0,
              stroke_w=0.0, stroke_color=None):
    """画一行字（可选描边 + 斜切），返回按墨迹裁切的图层"""
    f = make_font(presets, preset, size)
    pad = int(size * 0.8) + 50
    st = int(round(stroke_w))
    tmp = Image.new('RGBA', (int(size * len(text) * 1.6) + pad * 2,
                             int(size * 2.6) + pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((pad, int(size * 1.9)), text, font=f, fill=color, anchor='ls',
           stroke_width=st, stroke_fill=stroke_color)
    bb = tmp.getbbox()
    if not bb:
        return None
    layer = tmp.crop(bb)
    if italic:
        layer = shear(layer, italic)
    return layer


def shear(layer, deg):
    """向右倾的斜切（斜体感）。保持高度不变，向右扩展画布
    注意：transform 的输出尺寸必须包含扩展区，否则右移的部分会被直接切掉
    """
    w, h = layer.size
    k = math.tan(math.radians(deg))
    extra = int(math.ceil(h * k))
    # x' = x - k*y + extra  → 顶端右移 extra、底端不动，整体是向右倾的斜体
    out = layer.transform((w + extra, h), Image.AFFINE,
                          (1, -k, extra, 0, 1, 0), resample=Image.BICUBIC)
    bb = out.getbbox()
    return out.crop(bb) if bb else out


def fit_line(text, presets, preset, target_w, color, canvas_w,
             italic=0.0, stroke_w=0.0, stroke_color=None):
    """二分反解字号，让这一行【剪切后】的墨迹宽度 = target_w"""
    lo, hi = canvas_w * MIN_SIZE, canvas_w * MAX_SIZE
    best = None
    for _ in range(24):
        mid = (lo + hi) / 2
        layer = draw_line(text, presets, preset, mid, color, italic,
                          stroke_w, stroke_color)
        if layer is None:
            break
        best = (layer, mid)
        if layer.width <= target_w:
            lo = mid
        else:
            hi = mid
    if best is None:
        layer = draw_line(text, presets, preset, lo, color, italic,
                          stroke_w, stroke_color)
        best = (layer, lo)
    # 实绘宽度回修（斜切后宽度没有解析式，只能反复实绘逼近）
    layer, size = best
    for _ in range(4):
        if not layer or layer.width == 0:
            break
        ratio = target_w / layer.width
        if abs(1 - ratio) < 0.004:
            break
        size = min(max(size * ratio, canvas_w * MIN_SIZE), canvas_w * MAX_SIZE)
        layer = draw_line(text, presets, preset, size, color, italic,
                          stroke_w, stroke_color)
    return layer, size


def add_shadow(img, layer, pos, alpha, dx, dy, blur):
    """把单层文字按「偏移+模糊」投影到 img 上（只投这一层的形）"""
    W, H = img.size
    alpha_ch = layer.getchannel('A')
    sil = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sil.paste((0, 0, 0, alpha), (pos[0] + dx, pos[1] + dy), alpha_ch)
    sil = sil.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(img, sil)


# ------------------------------------------------------------ 底带

def build_veil(W, H, color, peak, top_ratio):
    """从 top_ratio 向上渐隐、向下加深的底带（深蓝黑，不是纯黑）"""
    grad = Image.new('L', (1, H), peak)
    start = int(H * top_ratio)
    span = max(1, H - start)
    for y in range(start):
        # 上半段：从 0 快速升到 ~55% 峰值
        grad.putpixel((0, y), int(peak * 0.55 * (y / start) ** 2.1))
    for y in range(start, H):
        t = (y - start) / span
        grad.putpixel((0, y), int(peak * (0.55 + 0.45 * min(1.0, t * 2.2))))
    mask = grad.resize((W, H))
    veil = Image.new('RGBA', (W, H), hex2rgba(color))
    veil.putalpha(mask)
    return veil


# ------------------------------------------------------------ 主渲染

def render(base, out, split=None, top=None, bottom=None,
           title_font='noto', bot_font='noto',
           title_color=TITLE_COLOR, ink=INK,
           italic=ITALIC, title_stroke=TITLE_STROKE,
           width=1080, height=1440, offset_y=0,
           shadow=True, veil='auto', veil_color=VEIL_COLOR, veil_peak=VEIL_PEAK,
           align='left', demo_grid=False):
    W, H = width, height

    img = crop_to_ratio(Image.open(base).convert('RGB'), W / H).resize(
        (W, H), Image.LANCZOS).convert('RGBA')

    if split:
        parts = [x.strip() for x in split.split('|') if x.strip()]
        top_lines, bot_lines = parts[:1], parts[1:]
    elif top and bottom:
        top_lines = [top.strip()]
        bot_lines = ([x.strip() for x in bottom.split('|') if x.strip()]
                     if '|' in bottom else auto_split(bottom, 2))
    else:
        raise SystemExit('需要 --split "标题|底1|底2" 或 --top + --bottom')
    if not bot_lines:
        raise SystemExit('底部至少要有一行')

    tc, wht = hex2rgba(title_color), hex2rgba(ink)

    # ---- 底带（先压底，再上字）
    if veil == 'auto':
        import numpy as np
        arr = np.asarray(img.convert('RGB'), dtype=float)
        band = arr[int(H * 0.62):].mean()
        # 深底不用压，浅底压满；底图越亮压得越重（参考图那种「下半身压出一块暗蓝」）
        veil_a = int(max(60, min(veil_peak, (band - 70) * 1.25)))
    elif veil in (0, '0', None):
        veil_a = 0
    else:
        veil_a = int(veil)
    if veil_a > 0:
        img = Image.alpha_composite(
            img, build_veil(W, H, veil_color, veil_a, VEIL_TOP))

    # ---- 逐行反解字号
    title_layers = [fit_line(t, TITLE_FONTS, title_font, W * TITLE_W, tc, W,
                             italic=italic, stroke_w=0,
                             stroke_color=None)
                    for t in top_lines]
    bot_layers = []
    for i, t in enumerate(bot_lines):
        tw = BOT_W if i == len(bot_lines) - 1 else BOT_W_LEAD
        bot_layers.append(fit_line(t, BOT_FONTS, bot_font, W * tw, wht, W))

    title_stage = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    bot_stage = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    records = []

    # 标题：贴顶，居中
    y = round(H * TITLE_INSET) + offset_y
    for (layer, size), txt in zip(title_layers, top_lines):
        x = round((W - layer.width) / 2)
        title_stage.alpha_composite(layer, (x, y))
        records.append({'text': txt, 'kind': 'title', 'size': round(size),
                        'box': (x, y, x + layer.width, y + layer.height),
                        'w_pct': layer.width / W})
        y += layer.height

    # 底行：自下而上堆叠，左对齐
    y = round(H * (1 - BOT_INSET)) + offset_y
    for (layer, size), txt in reversed(list(zip(bot_layers, bot_lines))):
        y -= layer.height
        if align == 'center':
            x = round((W - layer.width) / 2)
        else:
            x = round(W * BOT_LEFT)
            x = min(x, W - layer.width - round(W * 0.02))
        bot_stage.alpha_composite(layer, (x, y))
        records.insert(len(top_lines),
                       {'text': txt, 'kind': 'bottom', 'size': round(size),
                        'box': (x, y, x + layer.width, y + layer.height),
                        'w_pct': layer.width / W})
        y -= round(H * BOT_GAP)

    # ---- 阴影
    if shadow:
        # 标题：轻度右下投影（参考图是柔和影，不加暗晕，免得糊掉蓝字薄边）
        ta = title_stage.getchannel('A')
        tsil = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        tsil.paste((0, 0, 0, TITLE_SHADOW_ALPHA), (0, 0), ta)
        tsh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        tsh.alpha_composite(tsil, (round(W * SHADOW_DX * 1.4),
                                   round(H * SHADOW_DY * 1.6)))
        tsh = tsh.filter(ImageFilter.GaussianBlur(max(1.5, W * SHADOW_BLUR * 1.3)))
        img = Image.alpha_composite(img, tsh)

        # 底行：暗晕 + 实影（白字必须够狠，压在人物身上也要看清）
        alpha = bot_stage.getchannel('A')
        halo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        halo.paste((0, 0, 0, 145), (0, 0), alpha)
        halo = halo.filter(ImageFilter.GaussianBlur(max(1.5, W * 0.0036)))
        img = Image.alpha_composite(img, halo)
        sil = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        sil.paste((0, 0, 0, SHADOW_ALPHA), (0, 0), alpha)
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        sh.alpha_composite(sil, (round(W * SHADOW_DX), max(2, round(H * SHADOW_DY))))
        sh = sh.filter(ImageFilter.GaussianBlur(max(1, round(W * SHADOW_BLUR))))
        img = Image.alpha_composite(img, sh)

    img = Image.alpha_composite(img, title_stage)
    img = Image.alpha_composite(img, bot_stage)

    if demo_grid:
        g = ImageDraw.Draw(img)
        for gx in range(0, W, max(1, W // 10)):
            g.line([(gx, 0), (gx, H)], fill=(255, 0, 0, 70))
        for gy in range(0, H, max(1, H // 10)):
            g.line([(0, gy), (W, gy)], fill=(255, 0, 0, 70))

    img.convert('RGB').save(out, quality=96)
    return {'size': (W, H), 'records': records, 'veil': veil_a}


def main():
    ap = argparse.ArgumentParser(description='样式04 · 斜字压顶')
    ap.add_argument('--base', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--split', help='手动分行：标题|底1|底2，第一段是顶部大标题')
    ap.add_argument('--top', help='顶部大标题')
    ap.add_argument('--bottom', help='底部文案，不带 | 时自动断两行')
    ap.add_argument('--title-font', default='noto', choices=list(TITLE_FONTS))
    ap.add_argument('--bot-font', default='noto', choices=list(BOT_FONTS))
    ap.add_argument('--title-color', default=TITLE_COLOR,
                    help='标题色，默认参考图蓝 #4490DC')
    ap.add_argument('--ink', default=INK, help='底行色，默认白')
    ap.add_argument('--italic', type=float, default=ITALIC,
                    help='标题斜切角度，默认 28 度；0 = 不斜')
    ap.add_argument('--align', default='left', choices=['left', 'center'],
                    help='底行对齐，默认左对齐（参考图特征）')
    ap.add_argument('--width', type=int, default=1080,
                    help='画布宽，高度自动按 3:4 计算（全库统一 3:4）')
    ap.add_argument('--offset-y', type=int, default=0, help='整块上下微调')
    ap.add_argument('--no-shadow', action='store_true')
    ap.add_argument('--veil', default='auto',
                    help='底带强度：0-220，或 auto（按底图明暗自动定，默认）')
    ap.add_argument('--veil-color', default=VEIL_COLOR,
                    help='底带颜色，默认深蓝黑 #0C1A3A')
    ap.add_argument('--demo-grid', action='store_true')
    a = ap.parse_args()

    p = render(a.base, a.out, a.split, a.top, a.bottom,
               a.title_font, a.bot_font, a.title_color, a.ink,
               a.italic, TITLE_STROKE, a.width, round(a.width * 4 / 3),
               offset_y=a.offset_y, shadow=not a.no_shadow,
               veil=(a.veil if a.veil == 'auto' else int(a.veil)),
               veil_color=a.veil_color,
               align=a.align, demo_grid=a.demo_grid)
    W, H = p['size']
    print(f"saved: {a.out}  {W}x{H}  veil={p['veil']}")
    for r in p['records']:
        x0, y0, x1, y1 = r['box']
        print(f"  [{r['kind']:6}] {r['text']}  字号{r['size']}  "
              f"墨迹 {x1-x0}x{y1-y0}  宽占比 {r['w_pct']:.1%}  "
              f"y {y0}-{y1} ({y1/H:.1%}H)")


if __name__ == '__main__':
    main()
