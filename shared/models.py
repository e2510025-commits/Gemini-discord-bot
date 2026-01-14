"""Shared SQLAlchemy models used by bot and API"""
from datetime import datetime
from sqlalchemy import (Column, Integer, BigInteger, String, DateTime, Float, Text)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class AIChannel(Base):
    __tablename__ = "ai_channels"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False, unique=True)
    name = Column(String, nullable=True)
    type = Column(String, default="public")  # 'public' or 'private'
    owner_id = Column(BigInteger, nullable=True)  # for private channels: owner user id
    owner_name = Column(String, nullable=True)
    owner_avatar = Column(String, nullable=True)

class Mode(Base):
    __tablename__ = "modes"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False)
    mode = Column(String, default="standard")

class UsageLog(Base):
    __tablename__ = "usage_logs"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=True)
    user_id = Column(BigInteger, nullable=True)
    tokens = Column(Float, default=0.0)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class ConversationHistory(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False)
    guild_id = Column(BigInteger, nullable=True)
    context = Column(Text)  # serialized JSON or pickled small history
    updated_at = Column(DateTime, default=datetime.utcnow)


# New models for chat logs and guild config
class GuildConfig(Base):
    __tablename__ = "guild_configs"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, unique=True, nullable=False)
    prefix = Column(String, default="/")
    mode = Column(String, default="standard")
    reaction_channels = Column(Text, nullable=True)  # JSON list of channel ids


class ChatLog(Base):
    __tablename__ = "chat_logs"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=True)
    channel_id = Column(BigInteger, nullable=True)
    channel_name = Column(String, nullable=True)
    user_id = Column(BigInteger, nullable=False)
    user_name = Column(String, nullable=True)
    user_avatar = Column(String, nullable=True)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=True)
    tokens = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class MusicChannel(Base):
    __tablename__ = "music_channels"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(BigInteger, nullable=True)


class MusicTrack(Base):
    __tablename__ = "music_tracks"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False)
    requested_by = Column(BigInteger, nullable=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    stream_url = Column(String, nullable=True)
    duration = Column(Float, nullable=True)  # seconds
    thumbnail = Column(String, nullable=True)
    reason = Column(String, nullable=True)  # why recommended
    created_at = Column(DateTime, default=datetime.utcnow)


class MusicPlayback(Base):
    __tablename__ = "music_playback"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, unique=True)
    current_track_id = Column(Integer, nullable=True)
    is_playing = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    position = Column(Float, default=0.0)  # seconds


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False)
    guild_id = Column(BigInteger, nullable=True)
    summary = Column(Text, nullable=True)
    tokens_used = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SystemState(Base):
    __tablename__ = "system_state"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Quota(Base):
    __tablename__ = "quota"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    limit = Column(Float, nullable=False)
    window_seconds = Column(Integer, default=86400)  # default daily window
    updated_at = Column(DateTime, default=datetime.utcnow)


class Stats(Base):
    __tablename__ = "stats"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=True)
    total_messages = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)
