from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from models import Base, Resource, Service, Booking, User
from datetime import datetime, timedelta
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
# Importujeme vše potřebné z tvého auth.py
from auth import get_password_hash, verify_password, create_access_token, get_current_user

# Nastavení databáze
SQLALCHEMY_DATABASE_URL = "sqlite:///./rs2.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic modely
class ResourceCreate(BaseModel):
    name: str
    resource_type: str

class ServiceCreate(BaseModel):
    name: str
    duration: int
    price: int

class BookingCreate(BaseModel):
    resource_id: int
    service_id: int
    start_time: datetime

# --- AUTENTIZACE ---

@app.post("/register")
def register(username: str, password: str, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Uživatel už existuje")
    hashed = get_password_hash(password)
    new_user = User(username=username, hashed_password=hashed, role="user")
    db.add(new_user)
    db.commit()
    return {"message": "Uživatel vytvořen"}

@app.post("/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Špatné jméno nebo heslo")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}

# --- STATICKÉ SOUBORY ---

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/web")
def read_index():
    return FileResponse("static/index.html")

# --- ZDROJE A SLUŽBY ---

@app.post("/resources/")
def create_resource(resource: ResourceCreate, db: Session = Depends(get_db)):
    new_resource = Resource(name=resource.name, resource_type=resource.resource_type)
    db.add(new_resource)
    db.commit()
    db.refresh(new_resource)
    return new_resource

@app.get("/resources/")
def get_resources(db: Session = Depends(get_db)):
    return db.query(Resource).all()

@app.post("/services/")
def create_service(service: ServiceCreate, db: Session = Depends(get_db)):
    new_service = Service(name=service.name, duration=service.duration, price=service.price)
    db.add(new_service)
    db.commit()
    db.refresh(new_service)
    return new_service

@app.get("/services/")
def get_services(db: Session = Depends(get_db)):
    return db.query(Service).all()

# --- REZERVACE A LOGIKA ---

def is_slot_available(db: Session, resource_id: int, start_time: datetime, duration: int):
    end_time = start_time + timedelta(minutes=duration)
    existing_bookings = db.query(Booking).filter(Booking.resource_id == resource_id).all()
    for b in existing_bookings:
        s = db.query(Service).filter(Service.id == b.service_id).first()
        if s:
            b_end_time = b.start_time + timedelta(minutes=s.duration)
            if start_time < b_end_time and end_time > b.start_time:
                return False
    return True

@app.post("/bookings/")
def create_booking(booking: BookingCreate, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == booking.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Služba nenalezena")
    if not is_slot_available(db, booking.resource_id, booking.start_time, service.duration):
        raise HTTPException(status_code=400, detail="Tento termín koliduje!")
    new_booking = Booking(resource_id=booking.resource_id, service_id=booking.service_id, start_time=booking.start_time)
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return new_booking

@app.get("/bookings/")
def get_bookings(db: Session = Depends(get_db)):
    return db.query(Booking).all()

# TENTO ENDPOINT JE NYNÍ ZABEZPEČENÝ
@app.delete("/bookings/{booking_id}")
def delete_booking(
    booking_id: int, 
    db: Session = Depends(get_db), 
    current_user: str = Depends(get_current_user)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Rezervace nenalezena")
    db.delete(booking)
    db.commit()
    return {"message": f"Rezervace {booking_id} smazána uživatelem {current_user}"}

@app.get("/available-slots/")
def get_available_slots(resource_id: int, date: str, duration: int = 30, db: Session = Depends(get_db)):
    start_work = datetime.strptime(f"{date} 08:00:00", "%Y-%m-%d %H:%M:%S")
    end_work = datetime.strptime(f"{date} 17:00:00", "%Y-%m-%d %H:%M:%S")
    bookings = db.query(Booking).filter(Booking.resource_id == resource_id).all()
    slots = []
    current_time = start_work
    while current_time + timedelta(minutes=duration) <= end_work:
        is_free = True
        for b in bookings:
            s = db.query(Service).filter(Service.id == b.service_id).first()
            b_end = b.start_time + timedelta(minutes=s.duration)
            if current_time < b_end and (current_time + timedelta(minutes=duration)) > b.start_time:
                is_free = False
                break
        if is_free:
            slots.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=duration)
    return slots
    