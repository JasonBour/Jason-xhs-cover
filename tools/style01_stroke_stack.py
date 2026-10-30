# -*- coding: utf-8 -*-
"""
样式 01 · 描边压脸 / Stroke Stack
================================================================
黑描边 + 强调色钩子行 + 白结论行 + 多行堆叠压住人物脸部居中。
底图 100% 保真（不重绘、不磨皮），文字像素级精准，无水印，零 credits。

设计常量（相对画布宽 W 的比例，换画布也成立）
  字块宽度    block = 0.80 W       ← 硬约束：最宽一行的墨迹宽度，与文案长短无关
  安全线      usable = 0.88 W      ← 描边外沿绝不越过
  字块位置    墨迹中心 = 画布中心 (0.5 W, 0.5 H)   ← 硬约束
  描边粗细    stroke = 0.080 × 本行字号
  行距        1.36 × 正文字号（行中心 → 行中心）
  行字号系数  首行 0.91 / 中间 1.00 / 末行 1.065（梯形，末行落点最重）
  字号范围    0.072 W ≤ S ≤ 0.200 W（下限→加行，上限→仅极短文案触发）
  投影        黑 58/255，偏移 0.0074 W，模糊 0.0056 W

用法
  python style01_stroke_stack.py --base 底图.png --out 封面.png \
      --title "如何用 AI 找到属于自己的隐藏天赋！"          # 自动断行
  python style01_stroke_stack.py --base 底图.png --out 封面.png \
      --split "如何用 AI|找到属于自己的|隐藏天赋！"          # 手动分行
  ... --font heiti --accent "#FF3B30" --offset-y -20      # 换字体/颜色/微调
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_PRESETS = {
    'noto':  (r'C:\Windows\Fonts\NotoSansSC-VF.ttf', 900),   # 思源黑体 Heavy，最重最方正（默认）
    'yahei': (r'C:\Windows\Fonts\msyhbd.ttc', None),         # 微软雅黑 Bold，略圆、年轻
    'heiti': (r'C:\Windows\Fonts\simhei.ttf', None),         # 黑体，硬朗综艺感
}

USABLE = 0.88          # 物理安全线：描边外沿不越界（两侧各留 6%）
STROKE_RATIO = 0.080   # 描边 / 字号
LINE_GAP = 1.36        # 行距 / 正文字号

# ===== 硬约束：字块必须撑满这个宽度，写死，不随文案长短变化 =====
BLOCK_W = 0.80         # 字块最宽行的墨迹宽度 / 画布宽
MAX_SIZE = 0.200       # 字号上限 / 画布宽（只在文案极短时触发，防止撑爆）
MIN_SIZE = 0.072       # 字号下限 / 画布宽（低于此说明字太小，自动加行）


def hex2rgba(h, alpha=255):
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def load_font(preset, size):
    path, weight = FONT_PRESETS.get(preset, FONT_PRESETS['noto'])
    if not os.path.exists(path):
        for alt in ('noto', 'yahei', 'heiti'):
            p, w = FONT_PRESETS[alt]
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


def crop_to_ratio(img, ratio, focus=0.35):
    w, h = img.size
    if w / h > ratio:
        nw = int(h * ratio)
        x0 = (w - nw) // 2
        img = img.crop((x0, 0, x0 + nw, h))
    elif w / h < ratio:
        nh = int(w / ratio)
        y0 = max(0, int((h - nh) * focus))
        img = img.crop((0, y0, w, y0 + nh))
    return img


# ------------------------------------------------------------ 断行

def visual_width(u):
    return len(u) * 0.55 if u[0].isascii() and not u[0].isspace() else (
        0.30 if u.isspace() else float(len(u)))


NO_LINE_START = '的了着地得吗呢吧啊呀！？。，、；：）」』】…—'  # 不能出现在行首
NO_LINE_END = '（「『【《'                                        # 不能出现在行尾


def _merge_forbidden(units):
    """中文禁则：行首不能是虚词/标点，行尾不能是开引号"""
    out = []
    for u in units:
        if out and (u[0] in NO_LINE_START or out[-1][-1] in NO_LINE_END):
            out[-1] += u
        else:
            out.append(u)
    return out


def split_units(text):
    """切分成不可再拆的语义单元：优先 jieba 分词，缺失时退回逐字 + 禁则"""
    raw = []
    try:
        import jieba
        for tok in jieba.cut(text, HMM=True):
            if tok.strip():
                raw.append(tok)
            elif raw:
                raw[-1] += tok
    except Exception:
        buf = ''
        for ch in text:
            if ch.isascii() and not ch.isspace():
                buf += ch
            else:
                if buf:
                    raw.append(buf)
                    buf = ''
                raw.append(ch)
        if buf:
            raw.append(buf)
    # 合并连续英文/数字，避免切断 AI / Codex
    merged, buf = [], ''
    for u in raw:
        if u.isascii() and not u.isspace():
            buf += u
        else:
            if buf:
                merged.append(buf)
                buf = ''
            merged.append(u)
    if buf:
        merged.append(buf)
    return _merge_forbidden(merged)


def balanced_split(text, n):
    """切成 n 行：最小化最长行的视觉宽度，保持顺序，不切断英文/数字串"""
    units = split_units(text)
    if n >= len(units):
        return [u for u in units if not u.isspace()]
    w = [visual_width(u) for u in units]
    m = len(units)
    INF = float('inf')
    dp = [[(INF, -1)] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = (0.0, -1)
    for k in range(1, n + 1):
        for i in range(1, m + 1):
            best, acc = (INF, -1), 0.0
            for j in range(i - 1, -1, -1):
                acc += w[j]
                prev = dp[k - 1][j][0]
                if prev == INF:
                    continue
                val = max(prev, acc)
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
    out = [''.join(units[a:b]).strip() for a, b in cuts]
    return [s for s in out if s]


def auto_split(text, max_visual=7.4):
    """能一行放得下就一行；放不下再加行（最少行数优先）"""
    text = text.strip()
    fallback = None
    for n in (1, 2, 3):
        lines = balanced_split(text, n)
        longest = max(sum(visual_width(u) for u in split_units(ln)) for ln in lines)
        if longest <= max_visual:
            return lines
        if fallback is None or longest < fallback[0]:
            fallback = (longest, lines)
    return fallback[1]


# ------------------------------------------------------------ 绘制

def draw_line(canvas_w, text, size, fill, stroke, tracking):
    """逐字绘制（字距可控），按墨迹裁切。返回 (图层, 基线在图层内的 y)"""
    f = load_font(preset_holder['font'], size)
    tmp = Image.new('RGBA', (canvas_w + 600, int(size * 2.6)), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    baseline, x = int(size * 1.6), 300.0
    for ch in text:
        d.text((x, baseline), ch, font=f, fill=fill, anchor='ls',
               stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        x += d.textlength(ch, font=f) + tracking
    bbox = tmp.getbbox()
    if not bbox:
        return None, 0
    return tmp.crop(bbox), baseline - bbox[1]


preset_holder = {'font': 'noto'}


def render(base, out, title=None, split=None, accent='#FFD400', font='noto',
           offset_y=0, shadow=True, width=1080, height=1440,
           tracking=-5, stroke_ratio=STROKE_RATIO):
    preset_holder['font'] = font
    W, H = width, height

    img = crop_to_ratio(Image.open(base).convert('RGB'), W / H).resize(
        (W, H), Image.LANCZOS)

    lines = ([s.strip() for s in split.split('|') if s.strip()] if split
             else auto_split(title) if title else sys_exit('需要 --title 或 --split'))

    usable = W * USABLE
    probe = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    accent_rgba, white = hex2rgba(accent), (255, 255, 255, 255)

    def coefs(n):
        """行字号系数：首行 0.91（钩子），末行 1.065（落点），中间 1.0"""
        return [1.0] if n == 1 else [0.91] + [1.0] * (n - 2) + [1.065]

    st = {'lines': lines, 'coef': coefs(len(lines))}

    def line_w(text, s, c):
        """某行在字号 s 下的墨迹宽度（含字距与描边）"""
        size = max(8, int(round(s * c)))
        stk = max(6, round(size * stroke_ratio))
        tl = probe.textlength(text, font=load_font(font, size))
        return tl + (len(text) - 1) * (tracking * size / 123.0) + 2 * stk

    def widest_w(s):
        return max(line_w(ln, s, c) for ln, c in zip(st['lines'], st['coef']))

    def build(S):
        """按正文字号 S 渲染整块文字，返回 (图层组, 墨迹裁切块, 各行字号, 行距)"""
        _gap = LINE_GAP * S
        _sizes = [max(int(W * 0.05), int(round(S * c))) for c in st['coef']]
        # 上下各留一倍画布高做缓冲，避免大字被裁
        stage = Image.new('RGBA', (W, H * 2), (0, 0, 0, 0))
        base0 = int(H * 0.90)          # 任意起点，后面由 bbox 重新定位
        for i, (ln, size) in enumerate(zip(st['lines'], _sizes)):
            stk = max(6, round(size * stroke_ratio))
            layer, base_in_layer = draw_line(
                W, ln, size, accent_rgba if i == 0 else white, stk,
                tracking * size / 123.0)
            if not layer:
                continue
            stage.alpha_composite(
                layer, (int(W / 2 - layer.width / 2),
                        int(base0 + i * _gap - base_in_layer)))
        bb = stage.getbbox()
        return stage, (stage.crop(bb) if bb else stage), _sizes, _gap

    # ===== 硬约束：字块宽度 = BLOCK_W × W，与文案长短无关 =====
    target_w = W * BLOCK_W

    def solve():
        lo, hi = W * MIN_SIZE, W * MAX_SIZE
        for _ in range(28):           # 解出「刚好撑满目标宽度」的字号
            mid = (lo + hi) / 2
            if widest_w(mid) <= target_w:
                lo = mid
            else:
                hi = mid
        return lo

    S = solve()

    # 字太小 = 说明行数不够：允许突破 3 行限制，最多 4 行
    if title and not split and len(st['lines']) < 4 and S < W * MIN_SIZE * 1.18:
        alt = balanced_split(title.strip(), len(st['lines']) + 1)
        if len(alt) == len(st['lines']) + 1:
            st['lines'] = alt
            st['coef'] = coefs(len(alt))
            S = solve()

    # 实际渲染后按真实墨迹宽度回修（估算与绘图存在 1-2% 偏差）
    for _ in range(3):
        stage, block, sizes, gap = build(S)
        if not block.width:
            break
        if abs(block.width - target_w) <= W * 0.006:
            break
        S = min(max(S * target_w / block.width, W * MIN_SIZE), W * MAX_SIZE)
    stage, block, sizes, gap = build(S)
    lines = st['lines']

    # 极端情况兜底：绝不越过安全线
    if block.width > usable:
        S = max(W * MIN_SIZE, S * usable / block.width)
        stage, block, sizes, gap = build(S)

    x = int(round((W - block.width) / 2))
    y = int(round((H - block.height) / 2 + offset_y))

    if shadow:
        off = max(3, round(W * 0.0074))
        sil = Image.new('RGBA', block.size, (0, 0, 0, 0))
        sil.paste((0, 0, 0, 58), (0, 0), block.getchannel('A'))
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        sh.alpha_composite(sil, (x, min(y + off, H - block.height)))
        img = Image.alpha_composite(
            img.convert('RGBA'),
            sh.filter(ImageFilter.GaussianBlur(max(2, round(W * 0.0056)))))

    img.alpha_composite(block, (x, y))

    img.convert('RGB').save(out, quality=96)
    return {'lines': lines, 'sizes': sizes, 'S': round(S), 'gap': int(gap),
            'block': (block.width, block.height), 'offset': (x, y),
            'size': (W, H)}


def sys_exit(msg):
    raise SystemExit(msg)


def main():
    ap = argparse.ArgumentParser(description='样式01 · 描边压脸')
    ap.add_argument('--base', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--title', help='整句标题，自动断行')
    ap.add_argument('--split', help='手动分行，用 | 分隔')
    ap.add_argument('--accent', default='#FFD400', help='首行钩子色，默认亮黄')
    ap.add_argument('--font', default='noto', choices=list(FONT_PRESETS))
    ap.add_argument('--offset-y', type=int, default=0,
                    help='在正中基础上的微调像素，默认 0（正=下移）')
    ap.add_argument('--width', type=int, default=1080,
                    help='画布宽，高度自动按 3:4 计算（全库统一 3:4）')
    ap.add_argument('--tracking', type=int, default=-5)
    ap.add_argument('--stroke-ratio', type=float, default=STROKE_RATIO)
    ap.add_argument('--no-shadow', action='store_true')
    a = ap.parse_args()

    p = render(a.base, a.out, a.title, a.split, a.accent, a.font, a.offset_y,
               shadow=not a.no_shadow, width=a.width, height=round(a.width * 4 / 3),
               tracking=a.tracking, stroke_ratio=a.stroke_ratio)
    print(f"saved: {a.out}  {p['size'][0]}x{p['size'][1]}")
    print(f"字体={a.font}  S={p['S']}  行距={p['gap']}  "
          f"字块 {p['block'][0]}x{p['block'][1]} @ {p['offset']}（画布正中）")
    print(f"字块宽度占比 = {p['block'][0] / p['size'][0]:.1%}（标准 {BLOCK_W:.0%}）")
    for ln, s in zip(p['lines'], p['sizes']):
        print(f"  [{s:>4}px] {ln}")


if __name__ == '__main__':
    main()
