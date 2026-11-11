CREATE TABLE IF NOT EXISTS matchup_videos (
    id VARCHAR(191) NOT NULL PRIMARY KEY,
    player_champion_id VARCHAR(64) NOT NULL,
    opponent_champion_id VARCHAR(64) NOT NULL,
    title VARCHAR(512) NOT NULL,
    video_url VARCHAR(512) NOT NULL,
    channel_name VARCHAR(255) NOT NULL,
    channel_url VARCHAR(512) NOT NULL,
    published_at VARCHAR(64) NULL,
    game_patch VARCHAR(32) NULL,
    verified_at VARCHAR(64) NOT NULL,
    verification_status VARCHAR(32) NOT NULL DEFAULT 'verified',
    embed_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
    source_url VARCHAR(512) NOT NULL,
    upvote_count INT NOT NULL DEFAULT 0,
    INDEX idx_matchup_pair (player_champion_id, opponent_champion_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS matchup_video_votes (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    video_record_id VARCHAR(191) NOT NULL,
    voter_hash VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_video_voter (video_record_id, voter_hash),
    INDEX idx_vote_video (video_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

