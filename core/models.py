from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    language: Mapped[str] = mapped_column(String(2), default='ar')
    points: Mapped[int] = mapped_column(Integer, default=0)
    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    referrer: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

class Gift(Base):
    __tablename__ = 'gifts'
    __table_args__ = (UniqueConstraint('user_id', 'day', name='uq_gift_user_day'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    day: Mapped[int] = mapped_column(Integer)
    claimed_at: Mapped[int] = mapped_column(BigInteger)

class PairCode(Base):
    __tablename__ = 'pair_codes'
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[int] = mapped_column(BigInteger)

class Device(Base):
    __tablename__ = 'devices'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    last_seen: Mapped[int] = mapped_column(BigInteger, default=0)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

class Offer(Base):
    __tablename__ = 'offers'
    bid: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(String(50))
    size: Mapped[str] = mapped_column(String(50))
    price_points: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(20), default='internet')
    ussd: Mapped[str] = mapped_column(String(160))
    success_regex: Mapped[str] = mapped_column(String(200), default='')
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)

class Command(Base):
    __tablename__ = 'commands'
    __table_args__ = (UniqueConstraint('user_id', 'idempotency_key', name='uq_command_user_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    device_id: Mapped[int] = mapped_column(ForeignKey('devices.id'))
    offer_id: Mapped[int] = mapped_column(ForeignKey('offers.bid'))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(16), default='queued')
    ussd: Mapped[str] = mapped_column(String(160))
    offer_name: Mapped[str] = mapped_column(String(100))
    success_regex: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[int] = mapped_column(BigInteger)
    expires_at: Mapped[int] = mapped_column(BigInteger)
    response: Mapped[str] = mapped_column(Text, default='')
    reason: Mapped[str] = mapped_column(String(200), default='')
    notified: Mapped[bool] = mapped_column(Boolean, default=False)

class Interest(Base):
    __tablename__ = 'interests'
    __table_args__ = (UniqueConstraint('user_id', 'feature', name='uq_interest'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    feature: Mapped[str] = mapped_column(String(30))

class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    event: Mapped[str] = mapped_column(String(80))
    at: Mapped[int] = mapped_column(BigInteger)
