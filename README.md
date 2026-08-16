# CampusEvents — College Event Management System

A production-grade Flask + SQLite event platform with professional UI, 3D effects, and full role-based workflows.

## Quick Start

```bash
cd college_event_system
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**

## Demo Accounts

| Role      | Email                   | Password      |
|-----------|--------------------------|---------------|
| Admin     | admin@college.edu       | admin123      |
| Organizer | organizer@college.edu   | organizer123  |
| Student   | student@college.edu     | student123    |

Delete `college_events.db` to reset all data.

## Features

- **Students**: Browse events, register with one click, get unique tickets
- **Organizers**: Submit events, build schedules, manage sponsors, track attendees
- **Admins**: Approve/reject events & registrations, full oversight dashboard
- **Real-time**: Seat availability polling, interactive 3D card effects
- **Design**: Glassmorphism navbar, holographic tickets, animated gradients, responsive

## Tech Stack

- Python 3.12 + Flask 3.x
- SQLite (zero external DB)
- Vanilla CSS with CSS variables & 3D transforms
- Vanilla JS with IntersectionObserver
