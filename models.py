from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Resource(Base):
    __tablename__ = 'resources'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    resource_type = Column(String)

class Service(Base):
    __tablename__ = 'services'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    duration = Column(Integer)
    price = Column(Integer)

class Booking(Base):
    __tablename__ = 'bookings'
    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey('resources.id'))
    service_id = Column(Integer, ForeignKey('services.id'))
    start_time = Column(DateTime)