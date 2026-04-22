# MediFind — AI-Powered Smart Hospital Locator

A Flask-based web application for finding hospitals and booking doctor appointments in Chennai.

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables** (copy and edit `.env.example` to `.env`)
   ```bash
   cp .env.example .env
   # Edit .env with your keys
   ```

3. **Run the app**
   ```bash
   python app.py
   ```

4. **Open** `http://localhost:5000` in your browser.

## Features

- 🏥 Browse 6 Chennai hospitals with ratings and specializations
- 👨‍⚕️ Find doctors by specialization or hospital
- 📅 Book appointments with real-time slot availability
- 🤖 AI chatbot powered by Claude (requires `ANTHROPIC_API_KEY`)
- 🔐 JWT-based authentication (register / login / logout)
- 📋 View and cancel your appointments

## Project Structure

```
medifind/
├── app.py                  # Flask backend (API + routes)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── README.md               # This file
├── templates/
│   └── index.html          # Frontend SPA (self-contained)
└── static/                 # Static assets (CSS/JS if needed)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| GET  | `/api/auth/me` | Current user profile |
| GET  | `/api/hospitals` | List hospitals (supports `?lat=&lng=&radius=`) |
| GET  | `/api/hospitals/<id>` | Single hospital |
| GET  | `/api/doctors` | List doctors (supports `?specialization=&hospital_id=`) |
| GET  | `/api/doctors/<id>` | Doctor + available slots |
| POST | `/api/appointments` | Book appointment |
| GET  | `/api/appointments` | My appointments |
| PATCH | `/api/appointments/<id>/cancel` | Cancel appointment |
| POST | `/api/chatbot` | AI chatbot |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret | Random |
| `JWT_SECRET_KEY` | JWT signing key | Random |
| `DATABASE_URL` | SQLAlchemy DB URI | `sqlite:///medifind.db` |
| `ANTHROPIC_API_KEY` | Claude API key for chatbot | None (uses fallback) |
| `FLASK_ENV` | `development` or `production` | `development` |
| `PORT` | Server port | `5000` |
