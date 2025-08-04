from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    DateTime,
    Numeric,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship

# declarative base is a base class created, which all mapped classes should inherit
Base = declarative_base()


# Create a database
class SeismicEvent(Base):
    # Name of database
    __tablename__ = "seismic_event"

    # Fields

    # Primary Key
    eq_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)

    # Foreign Key
    eq_business_key = Column(String(50), unique=True)

    #
    eq_no = Column(Integer)
    datetime = Column(DateTime, index=True)
    latitude_str = Column(String(20))
    longitude_str = Column(String(30))
    latitude = Column(Numeric(10, 8), index=True)
    longitude = Column(Numeric(11, 8), index=True)
    region = Column(Text)
    location = Column(Text)
    municipality = Column(Text)
    province = Column(Text, index=True)
    depth_km = Column(Numeric(6, 2))
    depth_str = Column(String(6))
    origin = Column(Text, index=True)
    magnitude_type = Column(String(10))
    magnitude_value = Column(Numeric(3, 2), index=True)
    magnitude_str = Column(Text)
    filename = Column(Text)
    issued_datetime = Column(DateTime)
    authors = Column(JSON)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    """Composite indexes are indexes on multiple columns together
        Faster query
    """
    __table_args__ = (
        Index("idx_datetime_province", "datetime", "province"),
        Index("idx_lat_lon", "latitude", "longitude"),
        Index("idx_province_datetime", "province", "datetime"),
        Index("idx_origin_province", "origin", "province"),
        Index("idx_magnitudevalue_datetime", "magnitude_value", "datetime"),
    )

    intensities = relationship("Intensities", back_populates="seismic_event")


# Create database for intensity report
class Intensities(Base):
    __tablename__ = "intensities"

    # Primary key
    intensity_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key -> Reference to Seismicevent
    eq_id = Column(Integer, ForeignKey("seismic_event.eq_id"), nullable=False)

    # Intensity data
    intensity_type = Column(
        String(20),
    )
    intensity_value = Column(String(10))
    location = Column(Text)

    # Relationship back to seismic event
    seismic_event = relationship("SeismicEvent", back_populates="intensities")
