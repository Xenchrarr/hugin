from datetime import datetime, date
from sqlalchemy import Column, BigInteger, Integer, Float, String, DateTime, Date, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class PowerReading(Base):
    __tablename__ = "power_readings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    pv1_power = Column(Float)
    pv2_power = Column(Float)
    grid_power = Column(Float)
    grid_status = Column(String)


class DailyEnergy(Base):
    __tablename__ = "daily_energy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    pv1_energy_wh = Column(Float, nullable=False, default=0)
    pv2_energy_wh = Column(Float, nullable=False, default=0)
    total_energy_wh = Column(Float, nullable=False, default=0)
    grid_energy_wh = Column(Float, nullable=False, default=0)
    pv1_max_power = Column(Float, nullable=False, default=0)
    pv2_max_power = Column(Float, nullable=False, default=0)
    grid_max_power = Column(Float, nullable=False, default=0)
    reading_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
