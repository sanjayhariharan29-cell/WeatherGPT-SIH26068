# WeatherGPT — IMD Meteorological Assistant (SIH26068)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Test Suite](https://img.shields.io/badge/tests-698%20passed-brightgreen.svg)]()
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

> **Smart, Multilingual, Safety-First Conversational Meteorological Decision Support Platform**  
> Developed for the Ministry of Earth Sciences (MoES) / India Meteorological Department (IMD) — Smart India Hackathon (SIH) Problem Statement 26068.

---

## 📌 Executive Summary

WeatherGPT bridges the gap between complex meteorological telemetry and real-world human decision-making. Standard weather applications display raw numbers (e.g., "78% humidity, 15 km/h wind"). WeatherGPT translates these data points into actionable, context-aware, hyper-personalized advisory intelligence for farmers, daily commuters, fishermen, event planners, and disaster management officials across India.

### Core Value Proposition
- **IMD / Official Warning Priority**: Government weather alerts (CAP feeds, severe weather warnings) are prioritized with zero severity loss and strict guardrails.
- **Multilingual Conversational AI**: Native support for English, Hindi, Tamil, Tanglish, Hinglish, and regional language variations via text and voice.
- **Explainable Weather Reasoning**: Transparent decision traces explaining *why* an advisory is issued, grounded in actual meteorological parameters.
- **Offline & Low-Bandwidth Resilience**: Robust client-side caching, graceful API degradation, and local decision engine fallbacks.

---

## 🏗️ Architecture Overview

```
                        ┌───────────────────────────────────────────┐
                        │          CLIENT APPS (Mobile / PWA)       │
                        │  - Interactive Weather Map & Radar        │
                        │  - Multilingual Voice & Chat Interface    │
                        │  - Dynamic Severe Weather Banners        │
                        └─────────────────────┬─────────────────────┘
                                              │ (HTTPS / REST)
                                              ▼
                        ┌───────────────────────────────────────────┐
                        │          FASTAPI BACKEND GATEWAY          │
                        │  - CORS & Security Headers Middleware     │
                        │  - Correlation ID & Audit Logging         │
                        │  - Rate Limiting & JWT Authentication     │
                        └─────────────────────┬─────────────────────┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
┌──────────────────────────────────────┐             ┌─────────────────────────────────────┐
│       WEATHER DATA ADAPTERS          │             │     AI INTELLIGENCE PIPELINE        │
│  - OpenWeatherMap API                │             │  - Intent & Entity Extraction       │
│  - Open-Meteo API                    │             │  - Conversation Memory Engine       │
│  - Official IMD / CAP Alert Feed     │             │  - Weather Reasoner & Hazard Engine │
│  - Historical Weather Engine         │             │  - LLM Synthesis & Output Guardrail │
└──────────────────┬───────────────────┘             └──────────────────┬──────────────────┘
                   │                                                    │
                   └─────────────────────────┬──────────────────────────┘
                                             ▼
                             ┌───────────────────────────────┐
                             │       DATA & AUDIT LAYER      │
                             │  - SQLite / PostgreSQL WAL    │
                             │  - Automated DB Backup System │
                             └───────────────────────────────┘
```

---

## 🌟 Key Features

| Category | Features |
|---|---|
| **Conversational AI** | Natural language weather queries, context retention across sessions, custom personas (Farmer, Commuter, Fisherman, General Public). |
| **Multilingual Voice** | End-to-end Speech-to-Text (STT) → AI Reasoning → Text-to-Speech (TTS) pipeline for regional Indian languages. |
| **Severe Weather Safety** | Automatic detection of heavy rainfall, heatwaves, cyclones, and thunderstorms with uncompromised IMD alert severity (RED / ORANGE / YELLOW). |
| **Weather Dashboard & Maps** | Interactive map layers (precipitation, wind, temperature) powered by Leaflet and Open-Meteo. |
| **Enterprise Backend** | Correlation ID tracing, structured JSON logging, JWT user authentication, rate limiting, and database recovery. |
| **Cross-Platform Delivery** | Mobile-responsive PWA and native Android application powered by Capacitor. |

---

## 📂 Repository Structure

```
WeatherGPT-SIH26068/
├── ai/                         # Person 1: AI Pipeline & Intelligence Core
│   ├── advisory/               # Advisory depth & domain-specific recommendations
│   ├── core/                   # Core pipeline orchestrator & decision trace engine
│   ├── evaluation/             # Realistic AI evaluation & safety benchmarks
│   ├── hazard/                 # Severe weather hazard detector & guardrails
│   ├── llm/                    # LLM synthesis engine (OpenAI & local fallbacks)
│   ├── memory/                 # Short-term and long-term conversation memory
│   └── nlu/                    # Intent recognition & entity extraction engine
├── backend/                    # Person 2: FastAPI Backend Infrastructure
│   ├── api/                    # REST API routes (chat, voice, weather, auth, health)
│   ├── core/                   # Configuration, security, CORS, and startup logic
│   ├── db/                     # SQLite/PostgreSQL layer, migrations, and automated backups
│   ├── middleware/             # Correlation ID, telemetry, and error handling middleware
│   ├── services/               # WeatherManager, ChatIntegrationService, VoiceAIService
│   └── main.py                 # FastAPI application entrypoint
├── frontend/                   # Person 3: Web Application & PWA
│   ├── index.html              # Single Page Application entrypoint
│   ├── app.js                  # PWA router, chat manager, map controller
│   ├── styles.css              # Glassmorphic, modern CSS styling
│   └── sw.js                   # Service Worker for offline PWA functionality
├── android/                    # Capacitor Android Native Project
├── docs/                       # Comprehensive System Documentation & Phase Reports
│   ├── 00_DOCUMENTATION_INDEX.md # Master Documentation Directory Index
│   └── ...                     # Problem Statement Specs (01-11) & Phase Reports (Phase 0-26)
├── tests/                      # Automated Python & API Integration Test Suite (698 tests)
├── Dockerfile                  # Production Container Image Spec
├── docker-compose.yml          # Local Development Container Setup
├── docker-compose.prod.yml     # Production Stack Setup
├── package.json                # Frontend asset build & Capacitor scripts
├── requirements.txt            # Python backend & AI dependencies
└── README.md                   # Workspace Master Readme
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: v18 or higher (for frontend/Capacitor tasks)
- **Git**: For version management

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/sanjayhariharan29-cell/WeatherGPT-SIH26068.git
cd WeatherGPT-SIH26068

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to create your local `.env` file:

```bash
cp .env.example .env
```

Key variables in `.env`:
```env
ENVIRONMENT=development
OPENWEATHER_API_KEY=your_openweather_api_key
OPENAI_API_KEY=your_openai_api_key
JWT_SECRET_KEY=your_secret_key_here
```

### 3. Run FastAPI Backend

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
- API Documentation: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### 4. Serve Frontend Application

Serve the `frontend/` directory using any local web server or Python HTTP server:

```bash
python -m http.server 3000 --directory frontend
```
Access the UI in your browser at `http://localhost:3000`.

---

## 🐳 Docker Execution

### Development Stack
```bash
docker-compose up --build
```

### Production Stack
```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

---

## 📑 API Reference Overview

| Route | Method | Access | Description |
|---|---|---|---|
| `/health` | GET | Public | Diagnostic system health check |
| `/api/v1/chat` | POST | Public/Auth | Natural language weather query & AI advisory |
| `/api/v1/voice` | POST | Public/Auth | Audio file processing (STT → AI → TTS) |
| `/api/v1/weather/current` | GET/POST | Public | Current weather adapter with multi-provider fallback |
| `/api/v1/weather/forecast` | GET/POST | Public | 7-day normalized forecast |
| `/api/v1/weather/alerts` | GET | Public | Active official government alerts (IMD / CAP) |
| `/api/v1/weather/history` | GET | Public | Historical climate & weather queries |
| `/api/v1/auth/login` | POST | Rate Limited | JWT login |
| `/api/v1/auth/register` | POST | Rate Limited | User registration |
| `/api/v1/db/backup` | POST | Admin | Trigger database snapshot |

---

## 🧪 Testing & Verification

Run the full automated test suite containing 698 unit, integration, and E2E tests:

```bash
python -m pytest -v --tb=short -q
```

Run frontend verification:
```bash
npm run lint
npm run build:web
npm test
```

---

## 🛡️ Safety & Guardrail Principles

1. **No Alert Distortion**: Official severe weather warnings are preserved with 100% fidelity. AI synthesis cannot soften "RED" (Take Action) or "ORANGE" (Be Prepared) alerts.
2. **Transparent Decision Trace**: Every recommendation exposes the underlying meteorological triggers (e.g., precipitation rate, wind speed threshold).
3. **Data Privacy**: Telemetry scrubbers guarantee no passwords, API tokens, or raw voice recordings are saved to persistent logs.

---

## 📄 Documentation

For detailed technical designs, AI safety benchmarks, API contracts, and phase completion audits, view the master documentation index:
👉 [**docs/00_DOCUMENTATION_INDEX.md**](docs/00_DOCUMENTATION_INDEX.md)

---

## 📄 License
This project is licensed under the **MIT License**.
