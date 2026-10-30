# -*- coding: utf-8 -*-
"""
样式 03 · 白条压字 / White Bar
================================================================
纯白硬边横条 + 黑色宋体，左对齐堆叠，压在人物身上。
底图 100% 保真，文字像素级精准，无水印，零 credits。

设计常量（相对画布宽 W 的比例，换画布也成立）
  字号        S      = 0.0901 W
  内边距      pad    = 0.16 S        （白条四边到字身框）
  白条高度           = S + 2 pad     = 1.32 S
  条间距             = 0.63 S        （上条底 → 下条顶）
  左边距             = 0.062 W
  白条宽度           = 本行字身框宽 + 2 pad（随文字长度伸缩，不固定）
  白条颜色    #FFFFFF 纯色，无圆角、无投影、无描边，边缘硬切
  文字颜色    #000000
  字块顶边    0.495 H（参考图实测，偏下）

用法
  python style03_white_bar.py --base 底图.png --out 封面.png \
      --split "如何让别人觉得|你的前途一片光明？"
  python style03_white_bar.py --base 底图.png --out 封面.png \
      --title "如何让别人觉得你的前途一片光明？"     # 自动断行
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

FONT_PRESETS = {
    # 思源宋体可变字体，字重可调（参考图约 600）
    'notoserif': (r'C:\Windows\Fonts\NotoSerifSC-VF.ttf', 600),
    'sourcehan': (r'C:\Windows\Fonts\Source Han Serif SC Heavy (TrueType).ttf', None),
    'stsong':    (r'C:\Windows\Fonts\STSONG.TTF', None),
    'simsun':    (r'C:\Windows\Fonts\simsun.ttc', None),
}

S_RATIO = 0.0901       # 字号 / 画布宽
PAD_RATIO = 0.16       # 内边距 / 字号
GAP_RATIO = 0.63       # 条间距 / 字号
LEFT_RATIO = 0.062     # 左边距 / 画布宽
TOP_RATIO = 0.495      # 第一行白条顶边 / 画布高

BAR_COLOR = (255, 255, 255)
INK = (0, 0, 0)

preset_holder = {'font': 'notoserif', 'weight': 600}


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


def load_font(size):
    path, _ = FONT_PRESETS.get(preset_holder['font'], FONT_PRESETS['notoserif'])
    if not os.path.exists(path):
        for alt in ('notoserif', 'sourcehan', 'stsong'):
            p, _ = FONT_PRESETS[alt]
            if os.path.exists(p):
                path = p
                break
    f = ImageFont.truetype(path, max(8, int(size)))
    w = preset_holder['weight']
    if w:
        try:
            f.set_variation_by_axes([w])
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
    """按视觉宽度尽量均分的 n 行断行（白条样式默认两行）"""
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
                if val < best[0]:
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


# ------------------------------------------------------------ 绘制

def render(base, out, split=None, title=None, font='notoserif', weight=600,
           width=1080, height=1440, s_ratio=S_RATIO, pad_ratio=PAD_RATIO,
           gap_ratio=GAP_RATIO, left_ratio=LEFT_RATIO, top_ratio=TOP_RATIO,
           offset_y=0, bar_color=BAR_COLOR, ink=INK, demo_grid=False):
    preset_holder['font'] = font
    preset_holder['weight'] = weight
    W, H = width, height

    img = crop_to_ratio(Image.open(base).convert('RGB'), W / H).resize(
        (W, H), Image.LANCZOS).convert('RGBA')

    lines = ([x.strip() for x in split.split('|') if x.strip()] if split
             else auto_split(title, 2) if title else None)
    if not lines:
        raise SystemExit('需要 --split 或 --title')

    S = W * s_ratio
    pad = S * pad_ratio
    gap = S * gap_ratio
    bar_h = S + 2 * pad
    left = W * left_ratio

    # 预排版：算出每行白条宽度与文字墨迹
    f = load_font(S)
    probe = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    # 用满框汉字「国」的墨迹中心作为垂直基准：
    # 汉字墨迹在字身框内偏上，按 ascent/descent 居中会整体偏上，必须按墨迹算
    rb = f.getbbox('国', anchor='ls')
    ink_off = (rb[1] + rb[3]) / 2.0        # 墨迹中心相对基线（负=在基线上方）
    rows = []
    for ln in lines:
        tw = probe.textlength(ln, font=f)
        rows.append({'text': ln, 'tw': tw, 'bw': tw + 2 * pad})

    y = H * top_ratio + offset_y
    draw = ImageDraw.Draw(img)
    for r in rows:
        x0, x1 = left, left + r['bw']
        draw.rectangle([x0, y, x1, y + bar_h], fill=bar_color + (255,))
        # 文字：墨迹中心对齐白条中心
        baseline = y + bar_h / 2 - ink_off
        draw.text((x0 + pad, baseline), r['text'], font=f, fill=ink + (255,),
                  anchor='ls')
        r['bar'] = (round(x0), round(y), round(x1), round(y + bar_h))
        y += bar_h + gap

    if demo_grid:
        g = ImageDraw.Draw(img)
        for gx in range(0, W, max(1, W // 10)):
            g.line([(gx, 0), (gx, H)], fill=(255, 0, 0, 70))
        for gy in range(0, H, max(1, H // 10)):
            g.line([(0, gy), (W, gy)], fill=(255, 0, 0, 70))

    img.convert('RGB').save(out, quality=96)
    return {'S': round(S), 'pad': round(pad, 1), 'gap': round(gap, 1),
            'bar_h': round(bar_h, 1), 'rows': rows, 'size': (W, H),
            'block_bottom': round(y - gap)}


def main():
    ap = argparse.ArgumentParser(description='样式03 · 白条压字')
    ap.add_argument('--base', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--split', help='手动分行，用 | 分隔')
    ap.add_argument('--title', help='整句标题，自动断成两行')
    ap.add_argument('--font', default='notoserif', choices=list(FONT_PRESETS))
    ap.add_argument('--weight', type=int, default=600, help='思源宋体字重 400-900')
    ap.add_argument('--width', type=int, default=1080,
                    help='画布宽，高度自动按 3:4 计算（全库统一 3:4）')
    ap.add_argument('--offset-y', type=int, default=0, help='整块上下微调')
    ap.add_argument('--demo-grid', action='store_true', help='画出1/10网格辅助核验')
    a = ap.parse_args()

    p = render(a.base, a.out, a.split, a.title, a.font, a.weight,
               a.width, round(a.width * 4 / 3), offset_y=a.offset_y,
               demo_grid=a.demo_grid)
    print(f"saved: {a.out}  {p['size'][0]}x{p['size'][1]}")
    print(f"字体={a.font}/{a.weight}  S={p['S']}  pad={p['pad']}  "
          f"条高={p['bar_h']}  条间距={p['gap']}")
    for r in p['rows']:
        print(f"  白条 x{r['bar'][0]}-{r['bar'][2]} ({r['bw']/p['size'][0]:.1%} W)"
              f"  y{r['bar'][1]}-{r['bar'][3]}  {r['text']}")
    print(f"  字块底边 y={p['block_bottom']} ({p['block_bottom']/p['size'][1]:.1%} H)")


if __name__ == '__main__':
    main()
