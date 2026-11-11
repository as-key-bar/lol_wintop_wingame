import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.champions import Champion, search_champions
from app.matchups import MatchupVideo, UnknownChampionError, get_matchup_videos

load_dotenv()

logger = logging.getLogger(__name__)
database_url = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://wintop:local_only_password@127.0.0.1:3306/wintop",
)
engine = create_engine(database_url, pool_pre_ping=True)

app = FastAPI(title="wintop-wingame API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


class ChampionListResponse(BaseModel):
    dataDragonVersion: str
    items: list[Champion]


class MatchupResponse(BaseModel):
    playerChampionId: str
    opponentChampionId: str
    items: list[MatchupVideo]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health/database")
def database_health() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503, detail="Database connection is unavailable"
        ) from error

    return {"status": "ok"}


@app.get("/api/v1/champions", response_model=ChampionListResponse)
def get_champions(
    q: str | None = Query(default=None, max_length=100),
) -> ChampionListResponse:
    try:
        version, champions = search_champions(q)
    except RuntimeError as error:
        logger.exception("Champion catalog request failed")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "catalog_unavailable",
                "message": "Champion data is unavailable.",
            },
        ) from error

    return ChampionListResponse(dataDragonVersion=version, items=champions)


@app.get(
    "/api/v1/matchups/{playerChampionId}/{opponentChampionId}",
    response_model=MatchupResponse,
)
def get_matchup(
    playerChampionId: str,
    opponentChampionId: str,
    includeCandidates: bool = Query(default=False),
) -> MatchupResponse:
    try:
        items = get_matchup_videos(
            playerChampionId,
            opponentChampionId,
            include_candidates=includeCandidates,
        )
    except UnknownChampionError as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "unknown_champion",
                "message": "指定されたチャンピオンが見つかりません。",
            },
        ) from error
    except RuntimeError as error:
        logger.exception("Matchup catalog request failed")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "matchup_data_unavailable",
                "message": "マッチアップデータを読み込めませんでした。",
            },
        ) from error

    return MatchupResponse(
        playerChampionId=playerChampionId,
        opponentChampionId=opponentChampionId,
        items=items,
    )
