# -*- coding: utf-8 -*-
"""
样式 05 · 黄条压字 / Yellow Bar
================================================================
底部三件套，从上到下：

  ① 白字身份行（黑描边）——「某某专家：」
  ② 柠檬黄实色横条 + 黑字主标题（字比黄条宽，咬边）
  ③ 白字副标题（黑描边），其中关键词换成和横条同一个黄

参考图的播放键、进度条一律不做 —— 只留三行文字 + 一条黄条。

设计常量（相对画布 W / H，换画布也成立）
  id_w        0.860 W   ← 身份行墨迹宽，硬约束
  ink_w       0.920 W   ← 主标题墨迹宽，硬约束（故意比黄条宽）
  bot_w       0.930 W   ← 底行墨迹宽，硬约束
  bar_scale   0.95      ← 黄条宽 / 主标题墨迹宽（<1 = 字咬边）
  bar_h       1.42      ← 黄条高 / 主标题墨迹高
  bar_cy      0.620 H   ← 黄条中心 y，整块文字绕它上下排
  gap_id      0.024 W   ← 身份行墨迹底 → 黄条顶
  gap_bot     0.024 W   ← 黄条底 → 底行墨迹顶
  stroke      0.065     ← 黑描边宽度 / 字号

用法
  python style05_yellow_bar.py --base 底图.png --out 封面.png \
      --id "斯坦福神经科学家：" --ink "早晨去晒太阳" --bot "一个最被低估的习惯" --hl "低估"
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = {
    'noto':  (r'C:\Windows\Fonts\NotoSansSC-VF.ttf', 900),
    'yahei': (r'C:\Windows\Fonts\msyhbd.ttc', None),
    'heiti': (r'C:\Windows\Fonts\simhei.ttf', None),
    'serif': (r'C:\Windows\Fonts\NotoSerifSC-VF.ttf', 900),
}

YELLOW = '#FAE04B'     # 参考图实测 (250,224,75)，黄条与高亮字同色
WHITE = '#FFFFFF'
BLACK = '#000000'

ID_W = 0.860           # 身份行墨迹宽 / 画布宽
INK_W = 0.920          # 主标题墨迹宽 / 画布宽（故意比黄条宽，字咬出条外）
BOT_W = 0.900          # 底行墨迹宽 / 画布宽（贴边到 0.93 会压到画布边，0.90 更稳）
BAR_SCALE = 0.950      # 黄条宽 / 主标题墨迹宽（<1 = 字咬出黄条两侧，参考图就是这样）
BAR_H = 1.42           # 黄条高 / 主标题墨迹高
BAR_CY = 0.620         # 黄条中心 y / 画布高
GAP_ID = 0.024         # 身份行墨迹底 → 黄条顶 / 画布宽
GAP_BOT = 0.024        # 黄条底 → 底行墨迹顶 / 画布宽
STROKE = 0.065         # 黑描边 / 字号
ID_CAP = 0.80          # 身份行字号上限 / 主标题字号（绝对上限为主，这个只兜底）
BOT_CAP = 0.88         # 底行字号上限 / 主标题字号（绝对上限为主，这个只兜底）
MIN_SIZE = 0.045       # 字号下限 / 画布宽
MAX_SIZE = 0.230       # 字号上限 / 画布宽
# 主标题字号范围（这是本卡最容易失控的地方）
# 主标题宽度写死 0.92W 时，4 字会放到 235 号——黄条厚成一条路障，字比画面还重。
# 参考图是 6 字 / 87.9%W → 159 号，所以给主标题一个字号上下限，超出就让宽度自己收。
# 三行各自一个字号范围，互不联动。以前身份行/底行按「主标题 × 比例」算，
# 主标题一变大，上下两行跟着膨胀，底行会撑到 93%W 撞边 —— 比例制必须换掉。
INK_MAX = 0.148        # 主标题字号上限 / 画布宽（≈160 号）
# ↑ 这个上限不是"保守"，是死锁的一半：主标题 4 字想撑 82%W 要放到 227 号，
#   层级比（主标题/身份行）会从 1.25 飙到 1.97，三行结块、底行顶到画布边。
#   4 字主标题在这套卡里无解，换断句才是正解。详见 style-library/05 的踩坑表。
ID_MAX = 0.118         # 身份行字号上限 / 画布宽（≈127 号）
BOT_MAX = 0.120        # 底行字号上限 / 画布宽（≈130 号）

SHADOW_ALPHA = 120     # 白字投影浓度（底图本身暗，不需要太重）
SHADOW_DY = 0.0050     # / 画布高
SHADOW_BLUR = 0.0028   # / 画布宽


# ------------------------------------------------------------ 基础

def hex2rgba(s, a=255):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


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


def char_colors(text, hl_words, base, hl):
    """把高亮词对应位置的字换色。同名多次出现全部换。"""
    cs = [base] * len(text)
    for w in hl_words:
        if not w:
            continue
        i = 0
        while True:
            i = text.find(w, i)
            if i < 0:
                break
            for k in range(i, i + len(w)):
                cs[k] = hl
            i += len(w)
    return cs


# ------------------------------------------------------------ 单行渲染

def render_line(text, font, size, colors, stroke_w, stroke_color):
    """画一行字：先整行描边（fill 透明），再逐字填充颜色。
    两遍法保证描边在字与字之间是连续的一圈，不会出现接缝。
    """
    pad = int(size * 0.7) + int(stroke_w) + 24
    adv = [font.getlength(c) for c in text]
    tw = sum(adv)
    canvas = Image.new('RGBA', (int(tw) + pad * 2, int(size * 1.9) + pad * 2),
                       (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    base_y = pad + int(size * 1.35)
    st = int(round(stroke_w))

    if st > 0:
        x = pad
        for ch, a in zip(text, adv):
            d.text((x, base_y), ch, font=font, fill=(0, 0, 0, 0), anchor='ls',
                   stroke_width=st, stroke_fill=stroke_color)
            x += a

    x = pad
    for ch, c, a in zip(text, colors, adv):
        d.text((x, base_y), ch, font=font, fill=c, anchor='ls')
        x += a

    bb = canvas.getbbox()
    return canvas.crop(bb) if bb else canvas


def estimate_w(text, font, stroke_w):
    return sum(font.getlength(c) for c in text) + stroke_w * 2


def fit_line(text, presets, preset, target_w, canvas_w, base_color,
             hl_words=None, hl_color=YELLOW, stroke_ratio=0.0,
             max_size=None):
    """二分反解字号，让这一行的墨迹宽度 = target_w"""
    hl_words = hl_words or []
    lo = canvas_w * MIN_SIZE
    hi = canvas_w * MAX_SIZE
    if max_size:
        hi = min(hi, max_size)
    hi0 = hi                     # 回修的绝对上限，不能用二分收敛后的 hi
    lo = min(lo, hi)

    for _ in range(26):
        mid = (lo + hi) / 2
        f = make_font(presets, preset, mid)
        if estimate_w(text, f, mid * stroke_ratio) <= target_w:
            lo = mid
        else:
            hi = mid
    size = lo

    # 实绘回修：估算不含墨迹内边距，和真画出来差 1-3%
    colors = char_colors(text, hl_words, base_color, hl_color)
    layer = None
    for _ in range(4):
        f = make_font(presets, preset, size)
        layer = render_line(text, f, size, colors,
                            size * stroke_ratio, BLACK)
        if not layer or layer.width == 0:
            break
        ratio = target_w / layer.width
        if abs(1 - ratio) < 0.004:
            break
        size = min(max(size * ratio, canvas_w * MIN_SIZE), hi0)
    return layer, size


def add_shadow(img, layer, pos, alpha, dy, blur):
    W, H = img.size
    a = layer.getchannel('A')
    sil = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sil.paste((0, 0, 0, alpha), pos, a)
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh.alpha_composite(sil, (0, max(1, dy)))
    sh = sh.filter(ImageFilter.GaussianBlur(max(1, blur)))
    return Image.alpha_composite(img, sh)


# ------------------------------------------------------------ 主渲染

def render(base, out, id_text='', ink_text='', bot_text='', hl_words='',
           font='noto', yellow=YELLOW, ink=WHITE,
           bar_scale=BAR_SCALE, bar_cy=BAR_CY, stroke=STROKE,
           id_w=ID_W, ink_w=INK_W, bot_w=BOT_W,
           ink_max=INK_MAX, id_max=ID_MAX, bot_max=BOT_MAX,
           id_cap=ID_CAP, bot_cap=BOT_CAP,
           width=1080, height=1440, offset_y=0, shadow=True):
    W, H = width, height
    img = crop_to_ratio(Image.open(base).convert('RGB'), W / H).resize(
        (W, H), Image.LANCZOS).convert('RGBA')

    records = []
    yc = round(H * bar_cy) + offset_y

    # ---- 主标题：黑字无描边，压在黄条上
    ink_layer, ink_size = fit_line(
        ink_text, FONTS, font, W * ink_w, W, hex2rgba(BLACK),
        stroke_ratio=0.0, max_size=W * ink_max) if ink_text else (None, 0)

    # 这套样式的骨架是「主标题 4-6 字」：少于 4 字黄条窄成一坨，多于 7 字字号塌到跟上下行一样大
    # 副标题也是「一条撑满 0.90W」：超过 9 字字号会掉到身份行以下，读起来比上面还弱
    for t in (bot_text or '').split('|'):
        n_bot = len(t.strip())
        if n_bot > 9:
            print(f'  [warn] 副标题「{t.strip()}」{n_bot} 字，字号会掉到 '
                  f'{max(60, round(880 / n_bot))} 上下，比身份行还小；建议压到 9 字内',
                  file=sys.stderr)
            break

    n_ink = len(ink_text.strip()) if ink_text else 0
    if n_ink and n_ink < 4:
        print(f'  [warn] 主标题只有 {n_ink} 字，黄条会窄到 {n_ink/6:.0%} 左右；'
              f'建议补到 4-6 字', file=sys.stderr)
    elif n_ink > 7:
        print(f'  [warn] 主标题 {n_ink} 字，字号已降到 {round(ink_size)}，'
              f'层级会跟上下行拉平；建议压到 7 字以内', file=sys.stderr)

    # ---- 身份行：白字黑边，字号不许超过主标题
    id_layer, id_size = fit_line(
        id_text, FONTS, font, W * id_w, W, hex2rgba(ink),
        stroke_ratio=stroke, max_size=min(W * id_max, ink_size * id_cap)
    ) if id_text else (None, 0)
    # 主标题字多时字号本来就小，cap 会把身份行压成一小团 —— 撑不满 0.62 W 就放宽重解
    if id_layer and id_layer.width < W * 0.62:
        id_layer, id_size = fit_line(
            id_text, FONTS, font, W * id_w, W, hex2rgba(ink),
            stroke_ratio=stroke, max_size=min(W * id_max, ink_size * id_cap * 1.35))

    # ---- 底行：白字黑边 + 高亮词，按 | 拆多行
    bot_lines = [t.strip() for t in (bot_text or '').split('|') if t.strip()]
    bot_layers = []
    net = [w.strip() for w in (hl_words or '').split('|') if w.strip()]
    for t in bot_lines:
        bot_layers.append(fit_line(
            t, FONTS, font, W * bot_w, W, hex2rgba(ink),
            hl_words=net, hl_color=hex2rgba(yellow),
            stroke_ratio=stroke, max_size=min(W * bot_max, ink_size * bot_cap)))
    # 多行副标题用同一个字号：各行独立反解会一大一小，读起来像两句不相干的话
    if len(bot_layers) > 1:
        uni = min(sz for _, sz in bot_layers)
        bot_layers = [(render_line(t, make_font(FONTS, font, uni), uni,
                                   char_colors(t, net, hex2rgba(ink),
                                               hex2rgba(yellow)),
                                   uni * stroke, BLACK), uni)
                      for t in bot_lines]

    # ---- 黄条
    if ink_layer:
        bar_w = ink_layer.width * bar_scale
        bar_h = ink_layer.height * BAR_H
        bar_top = yc - bar_h / 2
        bar_bottom = yc + bar_h / 2
        bar = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(bar).rectangle(
            [round((W - bar_w) / 2), round(bar_top),
             round((W + bar_w) / 2), round(bar_bottom)],
            fill=hex2rgba(yellow))
        img = Image.alpha_composite(img, bar)
        records.append({'kind': 'bar', 'size': 0,
                        'box': (round((W - bar_w) / 2), round(bar_top),
                                round((W + bar_w) / 2), round(bar_bottom))})

        x = round((W - ink_layer.width) / 2)
        y = round(yc - ink_layer.height / 2)
        img = Image.alpha_composite(img, _at(ink_layer, x, y, W, H))
        records.append({'kind': 'ink', 'text': ink_text, 'size': round(ink_size),
                        'box': (x, y, x + ink_layer.width, y + ink_layer.height)})

    # ---- 身份行：贴黄条上方
    if id_layer:
        bar_top = yc - (ink_layer.height * BAR_H) / 2 if ink_layer else yc
        y = round(bar_top - W * GAP_ID - id_layer.height)
        x = round((W - id_layer.width) / 2)
        if shadow:
            img = add_shadow(img, id_layer, (x, y + round(H * SHADOW_DY)),
                             SHADOW_ALPHA, round(H * SHADOW_DY),
                             round(W * SHADOW_BLUR))
        img = Image.alpha_composite(img, _at(id_layer, x, y, W, H))
        records.append({'kind': 'id', 'text': id_text, 'size': round(id_size),
                        'box': (x, y, x + id_layer.width, y + id_layer.height)})

    # ---- 底行：贴黄条下方，自下而上不需要，直接向下堆
    if bot_layers:
        bar_bottom = yc + (ink_layer.height * BAR_H) / 2 if ink_layer else yc
        y = round(bar_bottom + W * GAP_BOT)
        block_h = sum(l.height for l, _ in bot_layers) + \
            round(min(s for _, s in bot_layers) * 0.16) * (len(bot_layers) - 1)
        if y + block_h > H * 0.950:                    # 多行时兜底，别掉出画面
            y = round(H * 0.950) - block_h
        for (layer, size), t in zip(bot_layers, bot_lines):
            x = round((W - layer.width) / 2)
            if shadow:
                img = add_shadow(img, layer, (x, y + round(H * SHADOW_DY)),
                                 SHADOW_ALPHA, round(H * SHADOW_DY),
                                 round(W * SHADOW_BLUR))
            img = Image.alpha_composite(img, _at(layer, x, y, W, H))
            records.append({'kind': 'bot', 'text': t, 'size': round(size),
                            'box': (x, y, x + layer.width, y + layer.height)})
            y += layer.height + round(size * 0.16)

    img.convert('RGB').save(out, quality=94, subsampling=1)
    return {'size': (W, H), 'records': records}


def _at(layer, x, y, W, H):
    """把图层贴到与画布同尺寸的透明层上（超出部分自动裁掉）"""
    stage = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    stage.alpha_composite(layer, (x, y))
    return stage


def main():
    ap = argparse.ArgumentParser(description='样式05 · 黄条压字')
    ap.add_argument('--base', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--id', default='', help='身份行（白字黑边），如「斯坦福神经科学家：」')
    ap.add_argument('--ink', default='', help='主标题（黑字压黄条），如「早晨去晒太阳」')
    ap.add_argument('--bot', default='', help='底行（白字黑边），多行用 | 分隔')
    ap.add_argument('--hl', default='', help='底行要高亮成黄字的词，多个用 | 分隔')
    ap.add_argument('--font', default='noto', choices=list(FONTS))
    ap.add_argument('--yellow', default=YELLOW, help='黄条与高亮字颜色')
    ap.add_argument('--bar-scale', type=float, default=BAR_SCALE,
                    help='黄条宽 / 主标题墨迹宽，默认 1.06；0.92 = 复刻参考图的字咬边')
    ap.add_argument('--bar-cy', type=float, default=BAR_CY, help='黄条中心 y / 画布高')
    ap.add_argument('--stroke', type=float, default=STROKE, help='黑描边 / 字号')
    ap.add_argument('--id-w', type=float, default=ID_W)
    ap.add_argument('--ink-w', type=float, default=INK_W,
                    help='主标题墨迹宽上限 / 画布宽，默认 0.92；实际宽度受 --ink-max 约束')
    ap.add_argument('--ink-max', type=float, default=INK_MAX,
                    help='主标题字号上限 / 画布宽，默认 0.158（≈171 号）；'
                         '字少时在这里封顶，黄条跟着收窄')
    ap.add_argument('--id-max', type=float, default=ID_MAX,
                    help='身份行字号上限 / 画布宽，默认 0.118（≈127 号）')
    ap.add_argument('--bot-max', type=float, default=BOT_MAX,
                    help='底行字号上限 / 画布宽，默认 0.132（≈143 号）')
    ap.add_argument('--bot-w', type=float, default=BOT_W)
    ap.add_argument('--id-cap', type=float, default=ID_CAP)
    ap.add_argument('--bot-cap', type=float, default=BOT_CAP)
    ap.add_argument('--width', type=int, default=1080,
                    help='画布宽，高度自动按 3:4 计算（全库统一 3:4）')
    ap.add_argument('--offset-y', type=int, default=0)
    ap.add_argument('--no-shadow', action='store_true')
    a = ap.parse_args()

    p = render(a.base, a.out, a.id, a.ink, a.bot, a.hl,
               font=a.font, yellow=a.yellow, ink=WHITE,
               bar_scale=a.bar_scale, bar_cy=a.bar_cy, stroke=a.stroke,
               id_w=a.id_w, ink_w=a.ink_w, bot_w=a.bot_w,
               ink_max=a.ink_max, id_max=a.id_max, bot_max=a.bot_max,
               id_cap=a.id_cap, bot_cap=a.bot_cap,
               width=a.width, height=round(a.width * 4 / 3),
               offset_y=a.offset_y, shadow=not a.no_shadow)

    W, H = p['size']
    print(f"saved: {a.out}  {W}x{H}")
    for r in p['records']:
        x0, y0, x1, y1 = r['box']
        tag = r.get('text', '黄条')
        print(f"  [{r['kind']:4}] {tag}  字号{r['size']}  "
              f"墨迹 {x1-x0}x{y1-y0}  宽占比 {(x1-x0)/W:.1%}  "
              f"y {y0}-{y1} ({y1/H:.1%}H)")


if __name__ == '__main__':
    main()
