"""
Database setup and models using SQLAlchemy + PostgreSQL
"""

import os
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    telegram_id = Column(String, primary_key=True)
    telegram_username = Column(String)
    name = Column(String)
    height_inches = Column(Integer, nullable=True)
    weight_lbs = Column(Integer, nullable=True)
    age = Column(Integer, nullable=True)
    goals = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserTokens(Base):
    __tablename__ = "user_tokens"
    telegram_id = Column(String, primary_key=True)
    whoop_refresh_token = Column(String, nullable=True)
    whoop_client_id = Column(String, nullable=True)
    whoop_client_secret = Column(String, nullable=True)
    strava_refresh_token = Column(String, nullable=True)
    strava_client_id = Column(String, nullable=True)
    strava_client_secret = Column(String, nullable=True)
    hevy_api_key = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    telegram_id = Column(String, primary_key=True)
    messages = Column(Text, default="[]")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
