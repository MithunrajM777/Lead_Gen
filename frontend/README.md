# 🔍 ScrapeVerify — Lead Generation & Web Scraping Tool

A production-ready web scraping and lead extraction platform. Search for companies by keyword, automatically crawl their websites, extract contact information (emails, phone numbers, addresses), and export results to CSV.

---

## 🏗️ Architecture

```
scrabing tool/
├── backend/          # FastAPI + Celery + SQLAlchemy
│   ├── app/
│   │   ├── main.py         # API routes & FastAPI app
│   │   ├── scraper.py      # Core scraping engine (Playwright + BS4)
│   │   ├── validator.py    # Email / phone / address validation
│   │   ├── worker.py       # Celery background task worker
│   │   ├── celery_app.py   # Celery configuration
│   │   ├── database.py     # SQLAlchemy models & DB session
│   │   ├── models.py       # Pydantic schemas
│   │   └── auth.py         # JWT Authentication
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/         # React + Vite
│   ├── src/
│   ├── package.json
│   └── vite.config.js
└── docker-compose.yml
```

---

## ⚙️ Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| PostgreSQL | 15+ |
| Redis | 7+ |
| Docker & Docker Compose | (optional but recommended) |

---

## 🔧 Environment Setup

Copy the environment file and fill in your values:

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env`:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/leadgen

# Redis & Celery
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-super-secret-key-change-me

# External APIs (optional)
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here

# Proxy rotation (optional, comma-separated)
PROXY_LIST=

# Email verification (optional)
SMTP_ENABLED=false
SMTP_SENDER=verify@yourdomain.com
```

---

## 🚀 Option A — Run with Docker (Recommended)

This starts PostgreSQL, Redis, the FastAPI backend, and the Celery worker all at once.

```bash
# From the project root (scrabing tool/)
docker-compose up --build
```

Services will be available at:

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

To stop:

```bash
docker-compose down
```

To stop and remove all data volumes:

```bash
docker-compose down -v
```

---

## 🚀 Option B — Run Locally (Manual)

### 1. Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for dynamic site scraping)
playwright install chromium
```

### 2. Run the FastAPI Backend

Make sure PostgreSQL and Redis are running locally, then:

```bash
cd backend

# Activate venv if not already active
venv\Scripts\activate   # Windows

# Start the API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API will be live at: **http://localhost:8000**
Swagger docs at: **http://localhost:8000/docs**

### 3. Run the Celery Worker

Open a **new terminal** in the `backend/` folder:

```bash
cd backend
venv\Scripts\activate   # Windows

# Start the Celery background worker
celery -A app.celery_app worker --loglevel=info
```

> **Note:** Redis must be running before starting the worker. The worker handles long-running scrape jobs in the background.

---

### 4. Frontend Setup

```bash
cd frontend

# Install Node.js dependencies
npm install

# Start the development server
npm run dev
```

Frontend will be live at: **http://localhost:5173**

To build for production:

```bash
npm run build
npm run preview
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/api/scrape` | Start a scrape job by keyword |
| `GET` | `/api/jobs/{job_id}` | Check job status & progress |
| `GET` | `/api/results/{job_id}` | Get extracted results |
| `GET` | `/api/results/{job_id}/csv` | Download results as CSV |
| `GET` | `/docs` | Interactive Swagger API docs |

---

## 🧪 Running Tests

```bash
cd backend
venv\Scripts\activate   # Windows

# Run test suite
pytest test_scraper.py -v
```

---

## 🛠️ Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) — API framework
- [Celery](https://docs.celeryq.dev/) — Background task queue
- [Playwright](https://playwright.dev/python/) — Dynamic website rendering
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing
- [SQLAlchemy](https://www.sqlalchemy.org/) — ORM
- [PostgreSQL](https://www.postgresql.org/) — Primary database
- [Redis](https://redis.io/) — Task broker & cache

**Frontend**
- [React 19](https://react.dev/) + [Vite](https://vite.dev/) — UI framework & build tool
- [React Router](https://reactrouter.com/) — Client-side routing
- [Framer Motion](https://www.framer.com/motion/) — Animations
- [Axios](https://axios-http.com/) — HTTP client
- [Lucide React](https://lucide.dev/) — Icons

---

## 📝 Features

- 🔎 Keyword-based company search
- 🌐 Multi-page crawling (`/contact`, `/contact-us`, `/about`)
- 📧 Email extraction with domain validation & deduplication
- 📞 Phone number extraction & normalization
- 🏠 Address extraction from page footers
- ⚡ Async background scraping via Celery
- 🔄 Retry mechanism for failed requests
- 📊 Real-time progress tracking
- 📥 CSV export
- 🔐 JWT Authentication
- 🐳 Docker support

---

## 🔒 Legal Notice

This tool is intended for legitimate lead generation and research purposes. Always ensure your scraping activities comply with the target website's **Terms of Service** and `robots.txt`. The authors are not responsible for misuse.
