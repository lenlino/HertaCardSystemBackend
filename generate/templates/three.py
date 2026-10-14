import math
from functools import lru_cache

import i18n
from PIL import Image, ImageChops, ImageDraw, ImageFont

from generate.templates.two import get_rolls
from generate.utils import get_json_from_url, get_json_from_json, get_image_from_url, get_relic_score_text, \
    get_star_image_path_from_int, convert_old_roman_from_int, get_relic_score, get_file_path, \
    get_relic_full_score_text, get_relic_sets_score, get_relic_score_color

RES_URL = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/"
font_file_path = f"{get_file_path()}/assets/zh-cn.ttf"

W, H = 1920, 1080
BG = (14, 16, 22, 255)
PANEL = (255, 255, 255, 16)
TEXT = "#f2f2f2"
SUB = "#9aa0aa"
DIM = "#5a606b"
RADIUS = 18

PORTRAIT_BOX = (40, 40, 560, 1040)
PORTRAIT_ZOOM = 1.15
HEADER_BOX = (590, 40, 1170, 200)
STATS_BOX = (590, 216, 1170, 640)
LIGHT_CONE_BOX = (590, 656, 1170, 750)
SETS_BOX = (590, 766, 1170, 866)
SCORE_BOX = (590, 882, 1170, 1040)
RELIC_W, RELIC_H, RELIC_GAP = 332, 322, 16
RELIC_X, RELIC_Y = 1200, 40
BASE_FIELDS = ("hp", "atk", "def", "spd", "crit_rate", "crit_dmg")


@lru_cache(maxsize=None)
def font(size):
    return ImageFont.truetype(font_file_path, size)


def fit_font(draw, text, max_width, size, min_size=14):
    while size > min_size and draw.textlength(text, font=font(size)) > max_width:
        size -= 1
    return font(size)


def ellipsize(draw, text, max_width, text_font):
    if draw.textlength(text, font=text_font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=text_font) > max_width:
        text = text[:-1]
    return text + "…"


def draw_smooth_circle(img, center, radius, fill, outline, width, scale=4):
    size = (radius * 2 + 2) * scale
    patch = Image.new("RGBA", (size, size))
    ImageDraw.Draw(patch).ellipse((scale, scale, size - scale - 1, size - scale - 1), fill=fill, outline=outline,
                                  width=width * scale)
    patch = patch.resize((size // scale, size // scale), Image.LANCZOS)
    img.alpha_composite(patch, (center[0] - radius - 1, center[1] - radius - 1))


async def load_image(path, size):
    return Image.open(await get_image_from_url(RES_URL + path)).convert("RGBA").resize(size, Image.LANCZOS)


def hex_to_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def lighten(rgb, ratio):
    return tuple(int(c + (255 - c) * ratio) for c in rgb)


def score_key(chara_id, calculating_standard):
    if calculating_standard not in ("compatibility", "no_score", "string"):
        return f"{chara_id}_{calculating_standard}"
    return chara_id


def relic_box(index):
    col, row = divmod(index, 3)
    x = RELIC_X + col * (RELIC_W + RELIC_GAP)
    y = RELIC_Y + row * (RELIC_H + RELIC_GAP)
    return x, y, x + RELIC_W, y + RELIC_H


def pick_skills(skills):
    picked = []
    used_types = set()
    for i in skills:
        if len(picked) >= 5:
            break
        if i["level"] == 0 or (i["max_level"] == 1 and i["type"] != "Maze"):
            continue
        if i["type"] in ("Ultra", "Normal"):
            if i["type"] in used_types:
                continue
            used_types.add(i["type"])
        picked.append(i)
    return picked


def build_stats(helta_json):
    stats = []
    for i in helta_json["attributes"]:
        addition = get_json_from_json(helta_json["additions"], "field", i["field"])
        if i["field"] in ("crit_rate", "crit_dmg"):
            value = f"{math.floor((float(i['value']) + float(addition.get('value', '0'))) * 1000) / 10}%"
        elif i["field"] == "spd":
            value = f"{math.floor((float(i['value']) + float(addition.get('value', '0'))) * 10) / 10}"
        else:
            value = f"{int(i['display']) + int(addition.get('display', '0'))}"
        stats.append((i["icon"], i["name"], value))
    for i in helta_json["properties"]:
        if i["field"] in BASE_FIELDS:
            continue
        display = i["display"]
        if i["field"] == "sp_rate":
            display = f"{round((i['value'] + 1) * 100, 1)}%"
        stats.append((i["icon"], i["name"], display))
    return stats[:15]


def build_sets(relic_sets):
    sets = {}
    for s in relic_sets:
        if s["id"] not in sets or sets[s["id"]]["num"] < s["num"]:
            sets[s["id"]] = s
    return list(sets.values())


def draw_background(element_rgb):
    img = Image.new("RGBA", (W, H), BG)
    tint = Image.new("RGBA", (W, H), element_rgb + (255,))
    mask = Image.new("L", (W, 1))
    mask.putdata([max(0, int(120 * (1 - x / (W * 0.75)))) for x in range(W)])
    img = Image.composite(tint, img, mask.resize((W, H)))

    layer = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(layer)
    boxes = [PORTRAIT_BOX, HEADER_BOX, STATS_BOX, LIGHT_CONE_BOX, SETS_BOX, SCORE_BOX]
    boxes += [relic_box(i) for i in range(6)]
    for box in boxes:
        draw.rounded_rectangle(box, radius=RADIUS, fill=PANEL)
    return Image.alpha_composite(img, layer)


async def draw_portrait(img, helta_json):
    x0, y0, x1, y1 = PORTRAIT_BOX
    w, h = x1 - x0, y1 - y0
    size = int(h * PORTRAIT_ZOOM)
    top = int((size - h) * 0.35)
    portrait = (await load_image(helta_json["portrait"], (size, size))).crop(
        ((size - w) // 2, top, (size + w) // 2, top + h))

    shade = Image.new("RGBA", (w, h))
    shade_mask = Image.new("L", (1, h))
    shade_mask.putdata([0 if y < h * 0.6 else int(235 * (y - h * 0.6) / (h * 0.4)) for y in range(h)])
    shade.putalpha(shade_mask.resize((w, h)))
    portrait = Image.alpha_composite(portrait, shade)

    mask = Image.new("L", (w, h))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=RADIUS, fill=255)
    portrait.putalpha(ImageChops.multiply(portrait.getchannel("A"), mask))
    img.alpha_composite(portrait, (x0, y0))

    draw = ImageDraw.Draw(img, "RGBA")
    slot = w // 5
    for index, skill in enumerate(pick_skills(helta_json["skills"])):
        cx, cy = x0 + slot * index + slot // 2, y1 - 100
        draw_smooth_circle(img, (cx, cy), 36, fill=(0, 0, 0, 160), outline=TEXT, width=2)
        if skill["icon"] is not None:
            icon = await load_image(skill["icon"], (48, 48))
            img.paste(icon, (cx - 24, cy - 24), icon)
        draw.rounded_rectangle((cx - 24, cy + 42, cx + 24, cy + 72), radius=8, fill=TEXT)
        draw.text((cx, cy + 57), f"{skill['level']}", "#111111", font=font(24), anchor="mm")


def draw_header(draw, helta_json, player, is_hideUID):
    x0, y0, x1, y1 = HEADER_BOX
    name = helta_json["name"].replace("{NICKNAME}", player["nickname"])
    draw.text((x0 + 28, y0 + 82), name, TEXT,
              font=fit_font(draw, name, 370, 64), anchor="ls")
    draw.text((x0 + 28, y1 - 30), f"Lv.{helta_json['level']}", SUB, font=font(30), anchor="ls")
    rank_x = x0 + 28 + draw.textlength(f"Lv.{helta_json['level']}", font=font(30)) + 18
    draw.rounded_rectangle((rank_x, y1 - 60, rank_x + 52, y1 - 24), radius=8, outline=SUB, width=2)
    draw.text((rank_x + 26, y1 - 42), f"E{helta_json['rank']}", TEXT, font=font(24), anchor="mm")
    if is_hideUID is not True:
        draw.text((x1 - 28, y1 - 30), f"UID: {player['uid']}", SUB, font=font(24), anchor="rs")


async def draw_header_icons(img, helta_json):
    x0, y0, x1, y1 = HEADER_BOX
    element_icon = await load_image(helta_json["element"]["icon"], (52, 52))
    path_icon = await load_image(helta_json["path"]["icon"], (52, 52))
    img.paste(element_icon, (x1 - 140, y0 + 28), element_icon)
    img.paste(path_icon, (x1 - 80, y0 + 28), path_icon)


async def draw_stats(img, draw, stats):
    x0, y0, x1, y1 = STATS_BOX
    cols = 2 if len(stats) <= 10 else 3
    rows = math.ceil(len(stats) / cols)
    row_h = min(84, (y1 - y0 - 24) // max(rows, 1))
    col_w = (x1 - x0 - 40) // cols
    for index, (icon_path, name, value) in enumerate(stats):
        row, col = divmod(index, cols)
        x = x0 + 20 + col * col_w
        y = y0 + 12 + row * row_h
        icon = await load_image(icon_path, (44, 44))
        img.paste(icon, (x + 4, y + (row_h - 44) // 2), icon)
        draw.text((x + 60, y + row_h // 2 - 4), name, SUB,
                  font=fit_font(draw, name, col_w - 72, 22), anchor="ls")
        draw.text((x + 60, y + row_h // 2 + 30), value, TEXT, font=fit_font(draw, value, col_w - 64, 34), anchor="ls")


async def draw_light_cone(img, draw, light_cone):
    x0, y0, x1, y1 = LIGHT_CONE_BOX
    if not light_cone:
        return
    icon = await load_image(light_cone["icon"], (76, 76))
    img.paste(icon, (x0 + 16, y0 + 9), icon)
    star_img = await load_image(get_star_image_path_from_int(int(light_cone["rarity"])), (136, 32))
    img.paste(star_img, (x1 - 150, y0 + 31), star_img)
    draw.text((x0 + 108, y0 + 42), light_cone["name"], TEXT,
              font=fit_font(draw, light_cone["name"], x1 - x0 - 280, 30), anchor="ls")
    draw.text((x0 + 108, y0 + 78),
              f"Lv.{light_cone['level']}   {convert_old_roman_from_int(int(light_cone['rank']))}", SUB,
              font=font(24), anchor="ls")


async def draw_sets(img, draw, sets):
    x0, y0, x1, y1 = SETS_BOX
    line_h = (y1 - y0 - 16) // max(len(sets), 2)
    for index, s in enumerate(sets[:3]):
        cy = y0 + 8 + line_h * index + line_h // 2
        icon = await load_image(s["icon"], (34, 34))
        img.paste(icon, (x0 + 18, cy - 17), icon)
        draw.rounded_rectangle((x0 + 62, cy - 14, x0 + 92, cy + 14), radius=6, fill=TEXT)
        draw.text((x0 + 77, cy), f"{s['num']}", "#111111", font=font(22), anchor="mm")
        draw.text((x0 + 106, cy), s["name"], TEXT, font=fit_font(draw, s["name"], x1 - x0 - 130, 24), anchor="lm")


def draw_score(draw, total_score, relic_full_score, criteria, lang, has_score):
    x0, y0, x1, y1 = SCORE_BOX
    label = i18n.t('message.score', locale=lang).rstrip(": ：")
    draw.text((x0 + 28, y0 + 44), f"{label}  |  {criteria}", SUB,
              font=fit_font(draw, f"{label}  |  {criteria}", 380, 24), anchor="ls")
    if not has_score:
        draw.text((x0 + 28, y1 - 30), "-", TEXT, font=font(72), anchor="ls")
        return
    draw.text((x0 + 28, y1 - 30), f"{total_score}", TEXT, font=font(80), anchor="ls")
    draw.text((x1 - 32, y1 - 30), get_relic_full_score_text(relic_full_score),
              get_relic_score_color(relic_full_score / 6), font=font(110), anchor="rs")


async def draw_relic(img, draw, index, relic, relic_score_json, accent, has_score, is_hide_roll):
    x0, y0, x1, y1 = relic_box(index)
    icon = await load_image(relic["icon"], (88, 88))
    img.paste(icon, (x0 + 14, y0 + 14), icon)
    draw.rounded_rectangle((x0 + 56, y0 + 88, x0 + 104, y0 + 114), radius=6, fill=TEXT)
    draw.text((x0 + 80, y0 + 101), f"+{relic['level']}", "#111111", font=font(20), anchor="mm")

    main_affix = relic["main_affix"]
    main_icon = await load_image(main_affix["icon"], (32, 32))
    img.paste(main_icon, (x0 + 116, y0 + 22), main_icon)
    main_name_width = x1 - 16 - (x0 + 152)
    if has_score:
        relic_score = round(relic_score_json["score"] * 100, 1)
        grade = get_relic_score_text(relic_score)
        draw.text((x1 - 16, y0 + 72), grade, get_relic_score_color(relic_score), font=font(60), anchor="rs")
        draw.text((x1 - 16, y0 + 102), f"{relic_score}", SUB, font=font(24), anchor="rs")
        main_name_width -= draw.textlength(grade, font=font(60)) + 8

    main_font = fit_font(draw, main_affix["name"], main_name_width, 22)
    draw.text((x0 + 152, y0 + 38), ellipsize(draw, main_affix["name"], main_name_width, main_font), SUB,
              font=main_font, anchor="lm")
    main_value = round(main_affix["value"], 1) if main_affix["type"] == "SpeedDelta" else main_affix["display"]
    draw.text((x0 + 116, y0 + 100), f"{main_value}", TEXT, font=font(38), anchor="ls")

    draw.line((x0 + 16, y0 + 128, x1 - 16, y0 + 128), fill=DIM, width=1)

    sub_weights = relic_score_json.get("sub_weights", [])
    for sub_index, sub in enumerate(relic["sub_affix"]):
        cy = y0 + 160 + sub_index * 44
        weighted = not has_score or sub_index >= len(sub_weights) or sub_weights[sub_index] > 0
        color = TEXT if weighted else DIM
        sub_icon = await load_image(sub["icon"], (30, 30))
        if not weighted:
            sub_icon.putalpha(sub_icon.getchannel("A").point(lambda a: a * 0.4))
        img.paste(sub_icon, (x0 + 16, cy - 15), sub_icon)
        name_font = fit_font(draw, sub["name"], 120, 24)
        draw.text((x0 + 54, cy), sub["name"], color, font=name_font, anchor="lm")
        value = round(sub["value"], 1) if sub["type"] == "SpeedDelta" else sub["display"]
        draw.text((x1 - 16, cy), f"{value}", color, font=font(26), anchor="rm")

        if is_hide_roll is False:
            rolls = get_rolls(relic["rarity"], sub)
            dot_x = x0 + 54 + draw.textlength(sub["name"], font=name_font) + 12
            dot_color = accent if weighted else DIM
            for radius, count in zip((3, 4, 5), rolls):
                for _ in range(count):
                    draw.ellipse((dot_x, cy - radius, dot_x + radius * 2, cy + radius), fill=dot_color)
                    dot_x += radius * 2 + 4


async def generate_panel(uid="805477392", chara_id=1, is_hideUID=False, calculating_standard="compatibility",
                         lang="jp", is_hide_roll=False):
    json = await get_json_from_url(uid, lang)
    if "detail" in json:
        return json
    helta_json = json["characters"][int(chara_id)]
    has_score = calculating_standard != "no_score"
    key = score_key(helta_json["id"], calculating_standard)
    element_rgb = hex_to_rgb(helta_json["element"]["color"])
    accent = lighten(element_rgb, 0.55)

    img = draw_background(element_rgb)
    await draw_portrait(img, helta_json)
    await draw_header_icons(img, helta_json)
    draw = ImageDraw.Draw(img, "RGBA")
    draw_header(draw, helta_json, json["player"], is_hideUID)
    await draw_stats(img, draw, build_stats(helta_json))
    await draw_light_cone(img, draw, helta_json.get("light_cone"))
    await draw_sets(img, draw, build_sets(helta_json["relic_sets"]))

    relic_full_score = 0
    relic_score_json = {}
    for index, relic in enumerate(helta_json["relics"][:6]):
        relic_score_json = await get_relic_score(key, relic)
        relic_full_score += round(relic_score_json["score"] * 100, 1)
        await draw_relic(img, draw, index, relic, relic_score_json, accent, has_score, is_hide_roll)

    total_score = 0
    if has_score:
        relic_sets_score = (await get_relic_sets_score(key, helta_json["relic_sets"])).get("score", 0)
        total_score = round(relic_full_score + relic_sets_score, 1)
        compatibility = i18n.t('message.compatibility_criteria', locale=lang)
        criteria = compatibility if calculating_standard == "compatibility" else relic_score_json.get("name", compatibility)
    else:
        criteria = i18n.t('message.no_score', locale=lang)
    draw_score(draw, total_score, relic_full_score, criteria, lang, has_score)

    result = {}
    result['img'] = img.convert("RGB")
    result['score'] = total_score
    result['chara_name'] = helta_json['name']
    result['avatar_id'] = helta_json['id']
    return result
