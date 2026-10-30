# -*- coding: utf-8 -*-
"""
样式 02 · 上下压边 / Edge Anchor
================================================================
顶部一行大标签，底部两行大字，中间整块留给人脸。
每行独立撑满目标宽度，字号由字数决定；无描边，极淡投影。
底图 100% 保真（不重绘、不磨皮），文字像素级精准，无水印，零 credits。

设计常量（相对画布 W / H 的比例，换画布也成立）
  顶行目标宽   0.875 W       ← 硬约束：顶行墨迹宽度，与文案长短无关
  底行目标宽   0.905 W       ← 硬约束：底部每行墨迹宽度
  顶行顶边距   0.056 H       ← 墨迹顶边到画布顶（不贴边）
  底行底边距   0.045 H       ← 末行墨迹底边到画布底（不贴边）
  底行行间空隙 0.034 H       ← 上一行墨迹底 → 下一行墨迹顶
  投影         双层：扩散影（膨胀 0.0035 W + 模糊 0.004 W，黑 125/255）+ 厚度影（下移 0.0042 H，模糊 0.0035 W，黑 170/255）
  遮罩         --scrim auto：按上下带亮度自动压 0-120 的黑渐变，浅底必压、深底不压

字体分工（照抄参考图）
  顶行：宋体（思源宋体 700）—— 标签感、有质感
  底行：超粗黑体（思源黑体 900）—— 数字与卖点的冲击力

用法
  python style02_edge_anchor.py --base 底图.png --out 封面.png \
      --split "写给普通人|如何让别人觉得|你的前途一片光明"
  python style02_edge_anchor.py --base 底图.png --out 封面.png \
      --top "写给普通人" --bottom "如何让别人觉得你的前途一片光明"   # 底部自动断两行
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# 顶行 / 底行各自一套字体：参考图就是「宋体标签 + 黑体卖点」的搭配
TOP_FONTS = {
    'serif': (r'C:\Windows\Fonts\NotoSerifSC-VF.ttf', 900),   # 思源宋体（默认）
    'song':  (r'C:\Windows\Fonts\simsun.ttc', None),
    'sans':  (r'C:\Windows\Fonts\NotoSansSC-VF.ttf', 900),
}
BOT_FONTS = {
    'noto':  (r'C:\Windows\Fonts\NotoSansSC-VF.ttf', 900),    # 思源黑体 Heavy（默认）
    'yahei': (r'C:\Windows\Fonts\msyhbd.ttc', None),
    'heiti': (r'C:\Windows\Fonts\simhei.ttf', None),
    'serif': (r'C:\Windows\Fonts\NotoSerifSC-VF.ttf', 900),
}

TOP_W = 0.875          # 顶行墨迹宽 / 画布宽
BOT_W = 0.905          # 底行墨迹宽 / 画布宽
TOP_INSET = 0.0560     # 顶行墨迹顶边距 / 画布高（留够呼吸，不贴边）
BOT_INSET = 0.0450     # 末行墨迹底边距 / 画布高（留够呼吸，不贴边）
BOT_GAP = 0.034        # 底行行间空隙 / 画布高

MIN_SIZE = 0.055       # 字号下限 / 画布宽
MAX_SIZE = 0.300       # 字号上限 / 画布宽

ACCENT = '#FFD400'     # 与样式01 同色：黄做钩子
INK = '#FFFFFF'        # 白做结论

SHADOW_ALPHA = 185     # 厚度影：向下偏的实影
SHADOW_DY = 0.0050     # 偏移 / 画布高
SHADOW_BLUR = 0.0030   # 模糊 / 画布宽
HALO_ALPHA = 100       # 扩散影：无偏移的柔和暗晕，任何底图上都能把字托出来
HALO_BLUR = 0.0040     # 模糊 / 画布宽（必须小于笔画间隙，否则字内缝会被糊死）
HALO_DILATE = 0.0035   # 先膨胀再模糊：光晕贴着笔画外沿走，不外溢


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
    """按视觉宽度尽量均分的 n 行断行（底部默认两行）"""
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
                # 并列时取更靠前的断点：第一行短、第二行长，读起来更顺
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

def draw_line(text, presets, preset, size, color, canvas_w):
    """按字号画一行，返回按墨迹裁切的图层（无描边）"""
    f = make_font(presets, preset, size)
    pad = int(size * 0.6) + 40
    tmp = Image.new('RGBA', (int(size * len(text) * 1.4) + pad * 2,
                             int(size * 2.4)), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((pad, int(size * 1.7)), text, font=f, fill=color, anchor='ls',
           stroke_width=0)
    bb = tmp.getbbox()
    if not bb:
        return None
    return tmp.crop(bb)


def fit_line(text, presets, preset, target_w, color, canvas_w):
    """二分反解字号，让这一行的墨迹宽度 = target_w"""
    lo, hi = canvas_w * MIN_SIZE, canvas_w * MAX_SIZE
    best = None
    for _ in range(24):
        mid = (lo + hi) / 2
        layer = draw_line(text, presets, preset, mid, color, canvas_w)
        if layer is None:
            break
        best = (layer, mid)
        if layer.width <= target_w:
            lo = mid
        else:
            hi = mid
    if best is None:
        layer = draw_line(text, presets, preset, lo, color, canvas_w)
        best = (layer, lo)
    # 实绘宽度回修（估算与绘制有 1-2% 偏差）
    layer, size = best
    for _ in range(3):
        if layer.width == 0:
            break
        ratio = target_w / layer.width
        if abs(1 - ratio) < 0.004:
            break
        size = min(max(size * ratio, canvas_w * MIN_SIZE), canvas_w * MAX_SIZE)
        layer = draw_line(text, presets, preset, size, color, canvas_w)
        if layer is None:
            break
    return layer, size


# ------------------------------------------------------------ 主渲染

def render(base, out, split=None, top=None, bottom=None,
           top_font='serif', bot_font='noto',
           accent=ACCENT, ink=INK, accent_line='top',
           width=1080, height=1440, offset_y=0,
           shadow=True, scrim=0, demo_grid=False):
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
        raise SystemExit('需要 --split "顶行|底1|底2" 或 --top + --bottom')
    if not bot_lines:
        raise SystemExit('底部至少要有一行')

    acc, wht = hex2rgba(accent), hex2rgba(ink)
    color_top = acc if accent_line == 'top' else wht
    color_bot = wht if accent_line == 'top' else acc

    # 逐行反解字号（每行独立撑满目标宽度）
    top_layers = [fit_line(t, TOP_FONTS, top_font, W * TOP_W, color_top, W)
                  for t in top_lines]
    bot_layers = [fit_line(t, BOT_FONTS, bot_font, W * BOT_W, color_bot, W)
                  for t in bot_lines]

    # 排布：顶行贴顶，底行自下而上堆叠
    stage = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    records = []

    y = round(H * TOP_INSET) + offset_y
    for (layer, size), txt in zip(top_layers, top_lines):
        x = round((W - layer.width) / 2)
        stage.alpha_composite(layer, (x, y))
        records.append({'text': txt, 'kind': 'top', 'size': round(size),
                        'box': (x, y, x + layer.width, y + layer.height),
                        'w_pct': layer.width / W})
        y += layer.height

    y = round(H * (1 - BOT_INSET)) + offset_y
    for (layer, size), txt in reversed(list(zip(bot_layers, bot_lines))):
        y -= layer.height
        x = round((W - layer.width) / 2)
        stage.alpha_composite(layer, (x, y))
        records.insert(len(top_lines), {'text': txt, 'kind': 'bottom',
                                        'size': round(size),
                                        'box': (x, y, x + layer.width,
                                                y + layer.height),
                                        'w_pct': layer.width / W})
        y -= round(H * BOT_GAP)

    # 浅色底图兜底：上下各压一层极淡黑渐变，避免浅底白字糊成一片
    if scrim == 'auto':
        import numpy as np
        arr = __import__('numpy').asarray(
            img.convert('RGB'), dtype=float)
        top_band = arr[:int(H * 0.20)].mean()
        bot_band = arr[int(H * 0.76):].mean()
        bright = max(top_band, bot_band)
        # 120 以下不用压（深底图），230 以上压满
        scrim = int(max(0, min(120, (bright - 120) * 0.85)))
    if scrim:
        grad = Image.new('L', (1, H), 0)
        span = int(H * 0.26)
        for i in range(span):
            v = int(scrim * (1 - i / span) ** 1.5)
            grad.putpixel((0, i), v)
            grad.putpixel((0, H - 1 - i), v)
        mask = grad.resize((W, H))
        veil = Image.new('RGBA', (W, H), (0, 0, 0, 255))
        veil.putalpha(mask)
        img = Image.alpha_composite(img, veil)

    if shadow:
        alpha = stage.getchannel('A')
        # ① 扩散影：按字形轮廓向外糊一圈柔和暗晕，浅底/花底都能把字托出来
        halo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        halo.paste((0, 0, 0, HALO_ALPHA), (0, 0), alpha)
        # 先小膨胀再模糊：光晕紧贴笔画外沿，不会往字内的笔画缝里灌
        dil = max(3, int(round(W * HALO_DILATE)) | 1)
        halo = halo.filter(ImageFilter.MaxFilter(min(dil, 9)))
        halo = halo.filter(ImageFilter.GaussianBlur(max(1.5, W * HALO_BLUR)))
        img = Image.alpha_composite(img, halo)
        # ② 厚度影：向下偏移的实影，给字一点压出来的重量
        sil = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        sil.paste((0, 0, 0, SHADOW_ALPHA), (0, 0), alpha)
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dy = max(2, round(H * SHADOW_DY))
        sh.alpha_composite(sil, (0, dy))
        sh = sh.filter(ImageFilter.GaussianBlur(max(1, round(W * SHADOW_BLUR))))
        img = Image.alpha_composite(img, sh)

    img = Image.alpha_composite(img, stage)

    if demo_grid:
        g = ImageDraw.Draw(img)
        for gx in range(0, W, max(1, W // 10)):
            g.line([(gx, 0), (gx, H)], fill=(255, 0, 0, 70))
        for gy in range(0, H, max(1, H // 10)):
            g.line([(0, gy), (W, gy)], fill=(255, 0, 0, 70))

    img.convert('RGB').save(out, quality=96)
    return {'size': (W, H), 'records': records, 'scrim': scrim}


def main():
    ap = argparse.ArgumentParser(description='样式02 · 上下压边')
    ap.add_argument('--base', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--split', help='手动分行：顶行|底1|底2，第一段是顶行')
    ap.add_argument('--top', help='顶部标签行')
    ap.add_argument('--bottom', help='底部文案，不带 | 时自动断两行')
    ap.add_argument('--top-font', default='serif', choices=list(TOP_FONTS))
    ap.add_argument('--bot-font', default='noto', choices=list(BOT_FONTS))
    ap.add_argument('--accent', default=ACCENT, help='强调色，默认样式01 的黄 #FFD400')
    ap.add_argument('--ink', default=INK, help='结论色，默认白')
    ap.add_argument('--accent-line', default='top', choices=['top', 'bottom'],
                    help='强调色给顶行还是底行，默认顶行（黄做钩子）')
    ap.add_argument('--width', type=int, default=1080,
                    help='画布宽，高度自动按 3:4 计算（全库统一 3:4）')
    ap.add_argument('--offset-y', type=int, default=0, help='整块上下微调')
    ap.add_argument('--no-shadow', action='store_true')
    ap.add_argument('--scrim', default='auto',
                    help="上下渐变遮罩强度：0-140，或 auto（按底图明暗自动定，默认）")
    ap.add_argument('--demo-grid', action='store_true')
    a = ap.parse_args()

    p = render(a.base, a.out, a.split, a.top, a.bottom, a.top_font, a.bot_font,
               a.accent, a.ink, a.accent_line, a.width,
               round(a.width * 4 / 3), offset_y=a.offset_y,
               shadow=not a.no_shadow,
               scrim=(a.scrim if a.scrim == 'auto' else int(a.scrim)),
               demo_grid=a.demo_grid)
    W, H = p['size']
    print(f"saved: {a.out}  {W}x{H}  scrim={p['scrim']}")
    for r in p['records']:
        x0, y0, x1, y1 = r['box']
        print(f"  [{r['kind']:6}] {r['text']}  字号{r['size']}  "
              f"墨迹 {x1-x0}x{y1-y0}  宽占比 {r['w_pct']:.1%}  "
              f"y {y0}-{y1} ({y1/H:.1%}H)")


if __name__ == '__main__':
    main()
