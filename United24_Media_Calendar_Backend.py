from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import uvicorn
import sqlite3
import datetime
import requests

# ========== CONFIGURATION ==========
DATABASE = "calendar.db"
TELEGRAM_TOKEN = "7640591835:AAG6toSafZ_2Rmk2N3_f_qgOy0gC41ZIK-E"
ADMIN_CHAT_ID = "1016871922"  # Replace with your admin's Telegram user/chat ID

# ========== FASTAPI APP INIT ==========
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow frontend access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== DATABASE SETUP ==========
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            description TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL,
            created_by TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending'
        )
    """)
    conn.commit()
    conn.close()

create_table()

# ========== MODELS ==========
class EventIn(BaseModel):
    event_type: str
    description: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    time_start: str  # HH:MM
    time_end: str    # HH:MM
    created_by: str
    status: str = "Pending"

class EventOut(EventIn):
    id: int

class ActionRequest(BaseModel):
    id: int

# ========== HELPERS ==========
ALLOWED_TYPES = ["Holiday", "Day Off", "Sick Leave", "Business Trip"]

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

def find_user_chat_id(username):
    # Implement your logic or a mapping here, or keep as placeholder for now
    return ADMIN_CHAT_ID

# ========== ROUTES ==========

@app.post("/add_event")
def add_event(event: EventIn):
    if event.event_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Invalid event type.")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO events (event_type, description, start_date, end_date, time_start, time_end, created_by, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event.event_type,
        event.description,
        event.start_date,
        event.end_date,
        event.time_start,
        event.time_end,
        event.created_by,
        "Pending" if event.status == "Pending" else "Approved"
    ))
    conn.commit()
    event_id = cur.lastrowid
    conn.close()

    # Notify admin in Telegram
    send_telegram_message(
        ADMIN_CHAT_ID,
        f"New Event Submitted by {event.created_by}:\n"
        f"{event.event_type}: {event.description}\n"
        f"{event.start_date} {event.time_start} - {event.end_date} {event.time_end}\n"
        f"Approve via Admin Panel."
    )
    return {"ok": True, "id": event_id}

@app.get("/events", response_model=List[EventOut])
def get_events():
    conn = get_db_connection()
    events = conn.execute("SELECT * FROM events").fetchall()
    conn.close()
    return [dict(e) for e in events]

@app.post("/approve_event")
def approve_event(req: ActionRequest):
    conn = get_db_connection()
    event = conn.execute("SELECT * FROM events WHERE id = ?", (req.id,)).fetchone()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    conn.execute("UPDATE events SET status='Approved' WHERE id = ?", (req.id,))
    conn.commit()
    conn.close()

    # Notify creator
    send_telegram_message(
        find_user_chat_id(event["created_by"]),
        f"Your event '{event['event_type']}: {event['description']}' was approved!"
    )
    return {"ok": True}

@app.post("/reject_event")
def reject_event(req: ActionRequest):
    conn = get_db_connection()
    event = conn.execute("SELECT * FROM events WHERE id = ?", (req.id,)).fetchone()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    conn.execute("UPDATE events SET status='Rejected' WHERE id = ?", (req.id,))
    conn.commit()
    conn.close()

    # Notify creator
    send_telegram_message(
        find_user_chat_id(event["created_by"]),
        f"Your event '{event['event_type']}: {event['description']}' was rejected."
    )
    return {"ok": True}

@app.get("/")
def root():
    return {"status": "Backend running!"}

# ========== MAIN ==========
if __name__ == "__main__":
    uvicorn.run("United24_Media_Calendar_Backend:app", host="127.0.0.1", port=8000, reload=True)