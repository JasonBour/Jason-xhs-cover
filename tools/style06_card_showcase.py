# -*- coding: utf-8 -*-
"""
样式 06 · 卡片展示 / Card Showcase
================================================================
米白圆角卡片 + 三行左对齐大标题（末行强调色）+ 中间深色内容区 + 右下圆形头像。
像把一张「产品说明书」拍在桌上：干净、可信、信息密度高，适合工具清单 / 教程 / 系统介绍。

和 01-05 的根本区别
  01-05 都是「文字直接压在照片上」；06 是「文字压在一块米白卡片上，卡片再压在画布上」。
  卡片给了一层干净的纸面，所以标题可以做到最大、底图多脏都不影响可读性。

设计常量（相对画布 W / H）
  卡片      外距 0.046 W，圆角 0.065 W，色 #F5F2EB
  标题左        0.111 W
  标题字号  首行 0.124 W / 次行 0.111 W / 末行 0.111 W（末行用强调色）
  行距      0.161 W（行基线间距）
  内容区     距卡片左右各 0.065 W，上接标题下沿 0.030 H，下距卡片底 0.045 H
  圆角      0.035 W
  头像      直径 0.24 W，落在内容区右下，白色描边 0.012 W

用法
  python style06_card_showcase.py --out 封面.png \
      --l1 "个人常用的" --l2 "6 个" --l3 "AI 工具" \
      --tiles "ChatGPT:#10A37F|Claude:#D97757|Midjourney:#7C5CFF|Cursor:#2C2C2E|Gemini:#4285F4|剪映:#00C8FF"
  ... --avatar 头像.png       # 可选：右下角圆形头像
  ... --accent "#E8622A"      # 末行强调色
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_PATH = r'C:\Windows\Fonts\NotoSansSC-VF.ttf'

CARD_BG = '#F5F2EB'
PAPER = '#FFFFFF'
INK = '#111111'
ACCENT = '#E8622A'
PANEL = '#1C1C1E'
TILE_BG = '#2A2A2C'
TILE_INK = '#FFFFFF'
SUB_INK = '#8E8E93'


def hex2rgb(h):
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def font(size, weight=900):
    f = ImageFont.truetype(FONT_PATH, max(8, int(size)))
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def rounded(img, box, radius, fill, outline=None, width=0):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def shade(size, sigma):
    """白色遮罩：中间实心，边缘模糊，用于整体柔光"""
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rectangle([0, 0, size[0], size[1]], fill=255)
    return m.filter(ImageFilter.GaussianBlur(sigma))


def ellipse_avatar(base, avatar_path, center, diameter, ring=12):
    """把头像裁成圆形贴上去，带白描边"""
    av = Image.open(avatar_path).convert('RGB')
    w, h = av.size
    side = min(w, h)
    av = av.crop(((w - side) // 2, (h - side) // 2,
                  (w + side) // 2, (h + side) // 2)).resize((diameter, diameter), Image.LANCZOS)
    mask = Image.new('L', (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, diameter, diameter], fill=255)
    cx, cy = center
    d = ImageDraw.Draw(base)
    if ring:
        r = diameter // 2
        d.ellipse([cx - r - ring, cy - r - ring, cx + r + ring, cy + r + ring],
                  fill=(255, 255, 255, 255))
    base.paste(av, (cx - diameter // 2, cy - diameter // 2), mask)


def render(out, l1, l2, l3, tiles, accent=ACCENT, avatar=None,
           width=1080, height=1440):
    W, H = width, height
    img = Image.new('RGB', (W, H), hex2rgb(PAPER))

    # 外圈一层极淡的灰，让米白卡片浮起来
    grad = Image.new('L', (1, H), 0)
    for y in range(H):
        grad.putpixel((0, y), int(18 * (y / H) ** 1.2))
    img.paste(Image.new('RGB', (W, H), (0, 0, 0)), (0, 0), grad.resize((W, H)))

    pad = int(0.046 * W)
    radius = int(0.065 * W)
    card = [pad, pad, W - pad, H - pad]
    rounded(img, card, radius, hex2rgb(CARD_BG) + (255,))

    # ---- 标题 ----
    left = int(0.111 * W)
    s1, s2, s3 = int(0.104 * W), int(0.108 * W), int(0.108 * W)
    gap = int(0.138 * W)
    d = ImageDraw.Draw(img)
    y = pad + int(0.125 * W)
    for txt, sz, color, gapk in ((l1, s1, INK, 1.0), (l2, s2, INK, 1.0), (l3, s3, accent, 1.0)):
        if not txt:
            continue
        d.text((left, y), txt, font=font(sz), fill=hex2rgb(color), anchor='ls')
        y += int(gap * gapk)

    # ---- 内容区 ----
    top = y + int(0.010 * H)
    cw0 = pad + int(0.065 * W)
    cw1 = W - pad - int(0.065 * W)
    cbot = H - pad - int(0.045 * H)
    rounded(img, [cw0, top, cw1, cbot], int(0.035 * W), hex2rgb(PANEL) + (255,))

    # 内容区顶部小节标题，模拟 App 的 section header
    hpad = int(0.026 * W)
    d.text((cw0 + hpad, top + int(0.052 * W)), '我的工具箱', font=font(int(0.026 * W), 700),
           fill=(255, 255, 255), anchor='ls')
    d.text((cw1 - hpad, top + int(0.052 * W)), f'{len([t for t in tiles.split("|") if t.strip()])} 个在用',
           font=font(int(0.024 * W), 500), fill=hex2rgb(SUB_INK), anchor='rs')

    # ---- 工具格子 2x3（横排：图标 + 名称/用途） ----
    items = [t for t in tiles.split('|') if t.strip()]
    cols, rows = 2, 3
    gx, gy = int(0.014 * W), int(0.012 * W)
    inner = int(0.018 * W)
    head = int(0.062 * W)
    grid_w = (cw1 - cw0) - 2 * inner
    grid_h = (cbot - top) - 2 * inner - head
    tw = (grid_w - (cols - 1) * gx) // cols
    th = (grid_h - (rows - 1) * gy) // rows

    for i, item in enumerate(items[:cols * rows]):
        parts = item.split(':')
        name, color = parts[0], (parts[1] if len(parts) > 1 else TILE_BG)
        use = parts[2] if len(parts) > 2 else ''
        c, r = i % cols, i // cols
        x0 = cw0 + inner + c * (tw + gx)
        y0 = top + inner + head + r * (th + gy)
        rounded(img, [x0, y0, x0 + tw, y0 + th], int(0.020 * W), hex2rgb(TILE_BG) + (255,))
        # App 图标：圆角色块 + 白色首字
        ic = int(0.076 * W)
        ix, iy = x0 + int(0.022 * W), y0 + (th - ic) // 2
        rounded(img, [ix, iy, ix + ic, iy + ic], int(0.022 * W), hex2rgb(color) + (255,))
        d.text((ix + ic // 2, iy + ic // 2), name[0].upper(), font=font(int(0.040 * W), 900),
               fill=(255, 255, 255), anchor='mm')
        # 名称 + 用途
        tx = ix + ic + int(0.026 * W)
        d.text((tx, iy + int(ic * 0.40)), name, font=font(int(0.033 * W), 800),
               fill=hex2rgb(TILE_INK), anchor='ls')
        if use:
            d.text((tx, iy + int(ic * 0.95)), use, font=font(int(0.024 * W), 500),
                   fill=hex2rgb(SUB_INK), anchor='ls')

    # ---- 头像 ----
    if avatar and os.path.exists(avatar):
        dia = int(0.240 * W)
        ellipse_avatar(img, avatar,
                       (cw1 - int(0.030 * W) - dia // 2, cbot - int(0.030 * W) - dia // 2),
                       dia, ring=int(0.012 * W))

    img.save(out, quality=95)
    return {'size': (W, H), 'tiles': len(items[:cols * rows])}


def main():
    ap = argparse.ArgumentParser(description='样式06 · 卡片展示')
    ap.add_argument('--out', required=True)
    ap.add_argument('--l1', default='', help='标题第一行（黑）')
    ap.add_argument('--l2', default='', help='标题第二行（黑）')
    ap.add_argument('--l3', default='', help='标题第三行（强调色）')
    ap.add_argument('--tiles', default='', help='内容格子，格式 名字:色值，用 | 分隔（最多 6 个）')
    ap.add_argument('--accent', default=ACCENT, help='末行强调色')
    ap.add_argument('--avatar', default='', help='右下角圆形头像图（可选）')
    ap.add_argument('--width', type=int, default=1080)
    a = ap.parse_args()

    p = render(a.out, a.l1, a.l2, a.l3, a.tiles, a.accent, a.avatar,
               a.width, round(a.width * 4 / 3))
    print(f"saved: {a.out}  {p['size'][0]}x{p['size'][1]}  格子={p['tiles']}")


if __name__ == '__main__':
    main()
