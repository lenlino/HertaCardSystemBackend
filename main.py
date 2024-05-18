import datetime
import io
import json
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

import i18n
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from starlette.responses import StreamingResponse, Response, JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler

import generate.generate
from generate.utils import get_score_rank

load_dotenv()

root_origins = os.environ.get("ROOT_ORIGINS", "").split(",")

i18n.load_path.append(f"{os.path.dirname(os.path.abspath(__file__))}/i18n")
i18n.set('fallback', 'en')

app = FastAPI(docs_url=None)

origins = [
    "https://herta-hazel.vercel.app/",
    "http://localhost",
    "http://localhost:8080"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # 追記により追加
    allow_methods=["GET"],
    allow_headers=["*"]  # 追記により追加
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=root_origins,
    allow_credentials=True,  # 追記により追加
    allow_methods=["*"],
    allow_headers=["*"]  # 追記により追加
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
                             'X-mean': score_rank['mean'], 'X-rank': score_rank['rank'],
                             'X-data-count': score_rank['data_count']},
                    media_type="image/png")


@app.get("/sr_info_parsed/{uid}")
async def sr_info_parsed(uid: str, lang: str = "jp"):
    result = await generate.utils.get_json_from_url(uid, lang)
    if "detail" in result:
        raise HTTPException(status_code=result["detail"])
    json_compatible_item_data = jsonable_encoder(result)
    return JSONResponse(content=json_compatible_item_data)


class Weight1(BaseModel):
    HPDelta: float


class Weight2(BaseModel):
    AttackDelta: float


class Weight3(BaseModel):
    HPAddedRatio: float
    AttackAddedRatio: float
    DefenceAddedRatio: float
    CriticalChanceBase: float
    CriticalDamageBase: float
    HealRatioBase: float
    StatusProbabilityBase: float


class Weight4(BaseModel):
    HPAddedRatio: float
    AttackAddedRatio: float
    DefenceAddedRatio: float
    SpeedDelta: float


class Weight5(BaseModel):
    HPAddedRatio: float
    AttackAddedRatio: float
    DefenceAddedRatio: float
    PhysicalAddedRatio: float
    FireAddedRatio: float
    IceAddedRatio: float
    ThunderAddedRatio: float
    WindAddedRatio: float
    QuantumAddedRatio: float
    ImaginaryAddedRatio: float


class Weight6(BaseModel):
    BreakDamageAddedRatioBase: float
    SPRatioBase: float
    HPAddedRatio: float
    AttackAddedRatio: float
    DefenceAddedRatio: float


class WeightSub(BaseModel):
    HPDelta: float
    AttackDelta: float
    DefenceDelta: float
    HPAddedRatio: float
    AttackAddedRatio: float
    DefenceAddedRatio: float
    SpeedDelta: float
    CriticalChanceBase: float
    CriticalDamageBase: float
    StatusProbabilityBase: float
    StatusResistanceBase: float
    BreakDamageAddedRatioBase: float


class WeightMain(BaseModel):
    w1: Weight1
    w2: Weight2
    w3: Weight3
    w4: Weight4
    w5: Weight5
    w6: Weight6


class Lang(BaseModel):
    jp: str
    en: str


class Weight(BaseModel):
    main: WeightMain
    weight: WeightSub
    max: float
    lang: Lang


@app.get("/weight/{chara_id}")
async def weight(chara_id: str):
    result = generate.utils.get_all_weight(chara_id)
    return JSONResponse(content=jsonable_encoder(result))


@app.post("/weight/{chara_id}")
async def post_weight(weight: Weight, chara_id: str):
    with open(f"{os.path.dirname(os.path.abspath(__file__))}/generate/StarRailScore/score.json") as f:
        weight_json = json.load(f)
    weight_json[chara_id] = weight.model_dump()
    with open(f"{os.path.dirname(os.path.abspath(__file__))}/generate/StarRailScore/score.json", 'wt',
              encoding='utf-8') as f:
        json.dump(weight_json, f, ensure_ascii=False, indent=4, sort_keys=True, separators=(',', ': '))
    return {"done": True}


@app.put("/weight/{chara_id}")
async def put_weight(weight: Weight, chara_id: str):
    with open(f"{os.path.dirname(os.path.abspath(__file__))}/generate/StarRailScore/score.json") as f:
        weight_json = json.load(f)
    weight_json[chara_id] = weight.model_dump()
    with open(f"{os.path.dirname(os.path.abspath(__file__))}/generate/StarRailScore/score.json", 'wt',
              encoding='utf-8') as f:
        json.dump(weight_json, f, ensure_ascii=False, indent=4, sort_keys=True, separators=(',', ': '))
    return {"done": True}


@app.get("/weight_list/{chara_id}")
async def get_weight_list(chara_id: str):
    result = generate.utils.get_all_weight(None)
    weight_list = {}
    for key, value in result.items():
        if key.startswith(chara_id):
            weight_list[key] = value
    return JSONResponse(content=jsonable_encoder(weight_list))


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
    # os.system("git clone --filter=blob:none --no-checkout https://github.com/lenlino/StarRailScore.git")
    os.chdir('StarRailRes')
    os.system("git sparse-checkout set index_min")
    os.system("git checkout")
    os.system("git pull")
    # await update_weight_task()
    scheduler.start()
