import logging
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.auth import require_editor
from app.auth_routes import router as auth_router
from app.champions import Champion, search_champions
from app.database import compute_voter_hash, get_engine
from app.matchups import (
    InvalidUpvoteError,
    MatchupVideo,
    UnknownChampionError,
    analyze_matchup_video_metadata,
    get_matchup_videos,
    save_manual_video_metadata,
    save_video_waves,
    toggle_matchup_video_upvote,
)
from app.rate_limit import rate_limit
from app.video_analysis import VideoMetadataAnalysis, WaveNote, load_game_assets

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_COMMIT = os.getenv("APP_COMMIT", "unknown")

app = FastAPI(title="wintop-wingame API", version=APP_VERSION)
app.include_router(auth_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
    allow_credentials=True,
)


MAX_REQUEST_BODY_BYTES = 64 * 1024


@app.middleware("http")
async def limit_request_body(request, call_next):
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_REQUEST_BODY_BYTES:
        return JSONResponse(
            status_code=413,
            content={
                "detail": {
                    "code": "payload_too_large",
                    "message": "リクエストが大きすぎます。",
                }
            },
        )
    return await call_next(request)


@app.exception_handler(UnknownChampionError)
async def unknown_champion_handler(request, error):
    return JSONResponse(
        status_code=404,
        content={
            "detail": {
                "code": "unknown_champion",
                "message": "指定されたチャンピオンが見つかりません。",
            }
        },
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


class AnalyzeMetadataRequest(BaseModel):
    video: MatchupVideo
    refresh: bool = False


class SaveMetadataRequest(BaseModel):
    video: MatchupVideo
    metadata: VideoMetadataAnalysis


class SaveWavesRequest(BaseModel):
    video: MatchupVideo
    waves: list[WaveNote] = Field(default_factory=list, max_length=20)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/version")
def get_version() -> dict[str, str]:
    return {"version": APP_VERSION, "commit": APP_COMMIT}


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
    dependencies=[Depends(rate_limit("matchup-read", 120, 60))],
)
def get_matchup(
    playerChampionId: str,
    opponentChampionId: str,
    voterToken: str | None = Query(default=None, max_length=128),
) -> MatchupResponse:
    voter_hash = compute_voter_hash(voterToken)
    try:
        items = get_matchup_videos(
            playerChampionId,
            opponentChampionId,
            voter_hash=voter_hash,
        )
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
    dependencies=[Depends(rate_limit("upvote", 20, 60))],
)
def post_matchup_upvote(
    playerChampionId: str,
    opponentChampionId: str,
    body: UpvoteRequest,
) -> MatchupVideo:
    voter_hash = compute_voter_hash(body.voterToken)
    try:
        return toggle_matchup_video_upvote(
            player_champion_id=playerChampionId,
            opponent_champion_id=opponentChampionId,
            video=body.video,
            voter_hash=voter_hash,
        )
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


@app.get("/api/v1/game-assets")
def get_game_assets() -> dict:
    try:
        return load_game_assets()
    except Exception as error:
        logger.exception("Failed to load game assets catalog")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "game_assets_unavailable",
                "message": "ゲームアセット情報を読み込めませんでした。",
            },
        ) from error


@app.post(
    "/api/v1/matchups/{playerChampionId}/{opponentChampionId}/analyze",
    response_model=VideoMetadataAnalysis,
    dependencies=[Depends(rate_limit("analyze", 10, 60))],
)
def post_analyze_matchup_video(
    playerChampionId: str,
    opponentChampionId: str,
    body: AnalyzeMetadataRequest,
) -> VideoMetadataAnalysis:
    return analyze_matchup_video_metadata(
        player_champion_id=playerChampionId,
        opponent_champion_id=opponentChampionId,
        video=body.video,
        refresh=body.refresh,
    )


@app.put(
    "/api/v1/matchups/{playerChampionId}/{opponentChampionId}/metadata",
    response_model=VideoMetadataAnalysis,
    dependencies=[Depends(rate_limit("metadata-write", 10, 60)), Depends(require_editor)],
)
def put_matchup_video_metadata(
    playerChampionId: str,
    opponentChampionId: str,
    body: SaveMetadataRequest,
) -> VideoMetadataAnalysis:
    try:
        return save_manual_video_metadata(
            player_champion_id=playerChampionId,
            opponent_champion_id=opponentChampionId,
            video=body.video,
            metadata=body.metadata,
        )
    except InvalidUpvoteError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_metadata",
                "message": str(error),
            },
        ) from error
    except RuntimeError as error:
        logger.exception("Saving video metadata failed")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "metadata_unavailable",
                "message": "ビルド情報の保存に失敗しました。",
            },
        ) from error


@app.put(
    "/api/v1/matchups/{playerChampionId}/{opponentChampionId}/waves",
    response_model=VideoMetadataAnalysis,
    dependencies=[Depends(rate_limit("waves-write", 60, 60)), Depends(require_editor)],
)
def put_matchup_video_waves(
    playerChampionId: str,
    opponentChampionId: str,
    body: SaveWavesRequest,
) -> VideoMetadataAnalysis:
    try:
        return save_video_waves(
            player_champion_id=playerChampionId,
            opponent_champion_id=opponentChampionId,
            video=body.video,
            waves=body.waves,
        )
    except InvalidUpvoteError as error:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_waves", "message": str(error)},
        ) from error
    except RuntimeError as error:
        logger.exception("Saving wave notes failed")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "waves_unavailable",
                "message": "ウェーブ情報の保存に失敗しました。",
            },
        ) from error

