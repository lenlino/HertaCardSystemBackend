import io
import os

import i18n
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from starlette.responses import StreamingResponse, Response

import generate.generate
from generate.utils import get_score_rank

i18n.load_path.append(f"{os.path.dirname(os.path.abspath(__file__))}/i18n")
i18n.set('fallback', 'en')

app = FastAPI()


@app.get("/gen_card/{uid}")
async def gen_card(uid: str, select_number: int, is_uid_hide: bool, is_hide_roll: bool, calculation_value: str, lang: str):
    image_binary = io.BytesIO()
    panel_img = await generate.generate.generate_panel(uid=uid, chara_id=int(select_number), template=2,
                                                       is_hideUID=is_uid_hide
                                                       , calculating_standard=calculation_value, lang=lang, is_hide_roll=is_hide_roll)
    panel_img['img'].save(image_binary, 'PNG')
    image_binary.seek(0)
    score_rank = get_score_rank(int(panel_img['avatar_id']), uid, panel_img['score'])
    return Response(content=image_binary.getvalue(), headers={"X-score": str(panel_img["score"]), "X-top-score": score_rank['top_score'],
                                                              'X-before-score': score_rank['before_score'], 'X-median': score_rank['median'],
                                                              'X-mean': score_rank['mean'], 'X-rank': score_rank['rank'], 'X-data-count': 'data_count'},
                    media_type="image/png")
