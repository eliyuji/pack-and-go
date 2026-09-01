from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base

Base = declarative_base()
DB_PATH = Path(__file__).resolve().parent / "travel_data.db"

class City(Base):
    __tablename__ = "cities"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique= True)
    districts = relationship("District", back_populates="city") #Class, class attr

class District(Base):
    __tablename__="districts"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    city_id = Column(Integer, ForeignKey("cities.id"))
    city = relationship("City", back_populates= "districts")
    places = relationship("Place", back_populates= "district")


class Place(Base):
    __tablename__="places"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    category = Column(String)
    rating = Column(Float)
    address = Column(String)
    district_id = Column(Integer, ForeignKey("districts.id"))
    district = relationship("District", back_populates="places")
    place_id = Column(String, unique=True)

engine = create_engine(f"sqlite:///{DB_PATH}")
Base.metadata.create_all(engine)

Session= sessionmaker(bind=engine)
session= Session()

