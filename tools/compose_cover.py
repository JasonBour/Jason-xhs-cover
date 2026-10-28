# -*- coding: utf-8 -*-
"""
cover-style-lab / 实拍压字 · PIL 合成出图工具
底图 100% 保真 + 逐字精准压字 + 无水印，零 credits。
适用：真人/场景底图不需要改动、只需压标题的场景（AI 图生图会重绘人物，此类需求禁用）。

用法示例：
  python compose_cover.py --base 底图.jpg --out 封面.png \
      --small "别打工了" --lines "这3个副业" "够你月入过万" --color "#E8B92E"
"""
import argparse
from PIL import Image, FontFile  # noqa
from PIL import ImageFont, ImageDraw

FONT_PATH = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"  # 思源黑体可变字体，可拉满字重
TARGET_W, TARGET_H = 1242, 1656  # 小红书 3:4
RATIO = TARGET_W / TARGET_H


def load_font(size: int, weight: int = 900) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(FONT_PATH, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def crop_to_ratio(img: Image.Image) -> Image.Image:
    w, h = img.size
    if w / h > RATIO:  # 过宽 -> 裁宽
        new_w = int(h * RATIO)
        x0 = (w - new_w) // 2
        img = img.crop((x0, 0, x0 + new_w, h))
    else:  # 过高 -> 裁高（偏上保留，人物主体通常在上部）
        new_h = int(w / RATIO)
        y0 = max(0, int((h - new_h) * 0.25))
        img = img.crop((0, y0, w, y0 + new_h))
    return img.resize((TARGET_W, TARGET_H), Image.LANCZOS)


def draw_text_with_shadow(
    layer: Image.Image,
    xy_center: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    shadow: tuple = (0, 0, 0, 150),
    shadow_offset: tuple = (5, 7),
):
    """居中画字 + 半透明投影"""
    d = ImageDraw.Draw(layer)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = xy_center[0] - tw // 2 - bbox[0]
    y = xy_center[1] - th // 2 - bbox[3]
    d.text((x + shadow_offset[0], y + shadow_offset[1]), text, font=font, fill=shadow)
    d.text((x, y), text, font=font, fill=fill)


def hex2rgba(h: str, alpha: int = 255) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="底图路径")
    ap.add_argument("--out", required=True, help="输出路径")
    ap.add_argument("--small", default=None, help="顶部白色小短句(可选)")
    ap.add_argument("--lines", nargs="+", required=True, help="主标题行(金黄大字,可多行)")
    ap.add_argument("--color", default="#E8B92E", help="主标题色,默认金黄")
    ap.add_argument("--small-size", type=int, default=92)
    ap.add_argument("--big-size", type=int, default=138)
    args = ap.parse_args()

    img = crop_to_ratio(Image.open(args.base).convert("RGB"))
    W, H = img.size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    white = (255, 255, 255, 255)
    gold = hex2rgba(args.color)
    cx = W // 2

    y = int(H * 0.045)  # 顶部 padding
    if args.small:
        f_small = load_font(args.small_size, weight=700)
        draw_text_with_shadow(layer, (cx, y + args.small_size // 2), args.small, f_small, white)
        y += int(args.small_size * 1.55) + 24

    f_big = load_font(args.big_size, weight=900)
    for line in args.lines:
        draw_text_with_shadow(layer, (cx, y + args.big_size // 2), line, f_big, gold)
        y += int(args.big_size * 1.42)

    out = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    out.save(args.out, quality=95)
    print(f"saved: {args.out} ({W}x{H})")


if __name__ == "__main__":
    main()
