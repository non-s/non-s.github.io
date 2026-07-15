"""
database.py - Gerenciamento do banco de dados SQLite
Armazena historico de videos publicados e estatisticas
"""
from datetime import datetime
import json
from typing import Dict, List, Optional
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from loguru import logger
import config

Base = declarative_base()


class VideoRecord(Base):
    """Modelo de registro de video publicado"""
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(50), unique=True, nullable=False)
    topic = Column(String(200), nullable=False)
    title = Column(String(500))
    description = Column(Text)
    tags = Column(Text)  # JSON
    youtube_id = Column(String(50))
    youtube_url = Column(String(200))
    video_path = Column(String(500))
    duration_seconds = Column(Integer)
    clips_count = Column(Integer)
    subtitles_count = Column(Integer)
    voice_used = Column(String(100))
    published_at = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, default=False)
    error_message = Column(Text)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)


class DatabaseManager:
    """Gerenciador do banco de dados"""

    def __init__(self, db_url: str = None):
        self.db_url = db_url or config.DATABASE_URL
        self.engine = create_engine(self.db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info(f"Banco de dados inicializado: {self.db_url}")

    def get_session(self) -> Session:
        return self.SessionLocal()

    def save_video(
        self,
        session_id: str,
        topic: str,
        title: str = None,
        description: str = None,
        tags: list = None,
        youtube_id: str = None,
        youtube_url: str = None,
        video_path: str = None,
        duration_seconds: int = None,
        clips_count: int = None,
        subtitles_count: int = None,
        voice_used: str = None,
        success: bool = False,
        error_message: str = None,
    ) -> VideoRecord:
        """Salva ou atualiza o registro de um video processado."""
        session = self.get_session()
        try:
            record = session.query(VideoRecord).filter_by(session_id=session_id).one_or_none()
            if record is None:
                record = VideoRecord(session_id=session_id, topic=topic)
                session.add(record)

            record.topic = topic
            record.title = title
            record.description = description
            record.tags = json.dumps(tags or [], ensure_ascii=False)
            record.youtube_id = youtube_id
            record.youtube_url = youtube_url
            record.video_path = video_path
            record.duration_seconds = duration_seconds
            record.clips_count = clips_count
            record.subtitles_count = subtitles_count
            record.voice_used = voice_used
            record.success = success
            record.error_message = error_message

            session.commit()
            session.refresh(record)
            logger.info(f"Registro salvo no banco: {session_id}")
            return record
        except Exception:
            session.rollback()
            logger.exception(f"Erro ao salvar registro no banco: {session_id}")
            raise
        finally:
            session.close()

    def get_video_by_session(self, session_id: str) -> Optional[VideoRecord]:
        """Busca um video pelo identificador da sessao."""
        session = self.get_session()
        try:
            return session.query(VideoRecord).filter_by(session_id=session_id).one_or_none()
        finally:
            session.close()

    def get_recent_videos(self, limit: int = 20) -> List[VideoRecord]:
        """Retorna os videos mais recentes."""
        session = self.get_session()
        try:
            return (
                session.query(VideoRecord)
                .order_by(VideoRecord.published_at.desc())
                .limit(limit)
                .all()
            )
        finally:
            session.close()

    def update_stats(self, session_id: str, views: int = None, likes: int = None) -> bool:
        """Atualiza estatisticas simples de um video publicado."""
        session = self.get_session()
        try:
            record = session.query(VideoRecord).filter_by(session_id=session_id).one_or_none()
            if record is None:
                return False
            if views is not None:
                record.views = views
            if likes is not None:
                record.likes = likes
            session.commit()
            return True
        except Exception:
            session.rollback()
            logger.exception(f"Erro ao atualizar estatisticas: {session_id}")
            raise
        finally:
            session.close()

    def as_dict(self, record: VideoRecord) -> Dict:
        """Converte um registro SQLAlchemy para dicionario serializavel."""
        return {
            "id": record.id,
            "session_id": record.session_id,
            "topic": record.topic,
            "title": record.title,
            "description": record.description,
            "tags": json.loads(record.tags or "[]"),
            "youtube_id": record.youtube_id,
            "youtube_url": record.youtube_url,
            "video_path": record.video_path,
            "duration_seconds": record.duration_seconds,
            "clips_count": record.clips_count,
            "subtitles_count": record.subtitles_count,
            "voice_used": record.voice_used,
            "published_at": record.published_at.isoformat() if record.published_at else None,
            "success": record.success,
            "error_message": record.error_message,
            "views": record.views,
            "likes": record.likes,
        }
