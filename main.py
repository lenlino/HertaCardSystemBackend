import datetime
import io
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from starlette.middleware.cors import CORSMiddleware

import i18n
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from starlette.responses import StreamingResponse, Response, JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler

import generate.generate
from generate.utils import get_score_rank

i18n.load_path.append(f"{os.path.dirname(os.path.abspath(__file__))}/i18n")
i18n.set('fallback', 'en')

app = FastAPI()

origins = [
    "https://herta-hazel.vercel.app/",
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,   # 追記により追加
    allow_methods=["*"],      # 追記により追加
    allow_headers=["*"]       # 追記により追加
)


@app.get("/gen_card/{uid}")
async def gen_card(uid: str, select_number: int, is_uid_hide: bool = False, is_hide_roll: bool = False,
                   calculation_value: str = "compatibility", lang: str = "jp"):
    image_binary = io.BytesIO()
    panel_img = await generate.generate.generate_panel(uid=uid, chara_id=int(select_number), template=2,
                                                       is_hideUID=is_uid_hide
                                                       , calculating_standard=calculation_value, lang=lang,
                                                       is_hide_roll=is_hide_roll)
    if "detail" in panel_img:
        raise HTTPException(status_code=panel_img["detail"])
    panel_img['img'].save(image_binary, 'PNG')
    image_binary.seek(0)
    score_rank = get_score_rank(int(panel_img['avatar_id']), uid, panel_img['score'])
    return Response(content=image_binary.getvalue(),
                    headers={"X-score": str(panel_img["score"]), "X-top-score": score_rank['top_score'],
                             'X-before-score': score_rank['before_score'], 'X-median': score_rank['median'],
                             'X-mean': score_rank['mean'], 'X-rank': score_rank['rank'], 'X-data-count': score_rank['data_count'],
                             'Access-Control-Allow-Origin': '*'},
                    media_type="image/png")


@app.get("/sr_info_parsed/{uid}")
async def sr_info_parsed(uid: str, lang: str = "jp"):
    result = await generate.utils.get_json_from_url(uid, lang)
    if "detail" in result:
        raise HTTPException(status_code=result["detail"])
    json_compatible_item_data = jsonable_encoder(result)
    return JSONResponse(content=json_compatible_item_data)

@app.get("/weight/{chara_id}")
async def weight(chara_id: str):
    result = generate.utils.get_all_weight(chara_id)
    return JSONResponse(content=jsonable_encoder(result))


async def remove_temp_task():
    dt_now = datetime.datetime.now()
    for k, v in list(generate.utils.temp_json.items()):
        if dt_now > v["expires"]:
            generate.utils.temp_json.pop(k, None)


async def update_weight_task():
    os.chdir(f"{os.path.dirname(os.path.abspath(__file__))}/generate")
    os.chdir('StarRailScore')
    os.system("git checkout")
    os.system("git pull")


@app.on_event("startup")
async def skd_process():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(remove_temp_task, "interval", minutes=1)
    scheduler.add_job(update_weight_task, "interval", minutes=60)
    os.chdir(f"{os.path.dirname(os.path.abspath(__file__))}/generate")
    os.system("git clone --filter=blob:none --no-checkout https://github.com/Mar-7th/StarRailRes.git")
    os.system("git clone --filter=blob:none --no-checkout https://github.com/lenlino/StarRailScore.git")
    os.chdir('StarRailRes')
    os.system("git sparse-checkout set index_min")
    os.system("git checkout")
    os.system("git pull")
    await update_weight_task()
    scheduler.start()
