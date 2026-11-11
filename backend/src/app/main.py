import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.champions import Champion, search_champions
from app.database import compute_voter_hash, get_engine
from app.matchups import (
    InvalidUpvoteError,
    MatchupVideo,
    UnknownChampionError,
    get_matchup_videos,
    toggle_matchup_video_upvote,
)

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(title="wintop-wingame API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ChampionListResponse(BaseModel):
    dataDragonVersion: str
    items: list[Champion]


class MatchupResponse(BaseModel):
    playerChampionId: str
    opponentChampionId: str
    items: list[MatchupVideo]


class UpvoteRequest(BaseModel):
    video: MatchupVideo
    voterToken: str = Field(min_length=1, max_length=128)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health/database")
def database_health() -> dict[str, str]:
    try:
        with get_engine().connect() as connection:
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
    request: Request,
    playerChampionId: str,
    opponentChampionId: str,
    includeCandidates: bool = Query(default=False),
    voterToken: str | None = Query(default=None, max_length=128),
) -> MatchupResponse:
    client_host = request.client.host if request.client else None
    voter_hash = compute_voter_hash(voterToken, client_host)
    try:
        items = get_matchup_videos(
            playerChampionId,
            opponentChampionId,
            include_candidates=includeCandidates,
            voter_hash=voter_hash,
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


@app.post(
    "/api/v1/matchups/{playerChampionId}/{opponentChampionId}/upvote",
    response_model=MatchupVideo,
)
def post_matchup_upvote(
    request: Request,
    playerChampionId: str,
    opponentChampionId: str,
    body: UpvoteRequest,
) -> MatchupVideo:
    client_host = request.client.host if request.client else None
    voter_hash = compute_voter_hash(body.voterToken, client_host)
    try:
        return toggle_matchup_video_upvote(
            player_champion_id=playerChampionId,
            opponent_champion_id=opponentChampionId,
            video=body.video,
            voter_hash=voter_hash,
        )
    except UnknownChampionError as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "unknown_champion",
                "message": "指定されたチャンピオンが見つかりません。",
            },
        ) from error
    except InvalidUpvoteError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_upvote",
                "message": str(error),
            },
        ) from error
    except RuntimeError as error:
        logger.exception("Matchup upvote failed")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "upvote_unavailable",
                "message": "UVの保存に失敗しました。データベースの起動状態を確認してください。",
            },
        ) from error
