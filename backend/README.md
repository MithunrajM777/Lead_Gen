# Website Scraping & Lead Generation Tool

A professional FastAPI-based tool to scrape business data (email, phone, address) from websites, including contact pages and bulk scraping via Excel upload. Designed for high accuracy and performance.

## 🚀 Features

- **Website Scraping**: Extract contact details from any business website.
- **Deep Extraction**: Automatically finds and scrapes `/contact`, `/about`, and other relevant pages.
- **Intelligent Detection**: Uses regex and selector logic to find valid emails and 10+ digit phone numbers.
- **Excel Bulk Upload**: Process hundreds of URLs at once via CSV or XLSX.
- **Data Validation**: Sanitizes company names and validates contact info before saving.
- **Duplicate Removal**: Built-in logic to prevent duplicate leads by domain or email.
- **Admin Dashboard**: Approve users, manage payments, and monitor scraping jobs.

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite (SQLAlchemy ORM)
- **Scraping**: BeautifulSoup4, Playwright (for JS-heavy sites), HTTPX
- **Data Processing**: Pandas, Openpyxl
- **Auth**: JWT (OAuth2 with Password Flow)

## 📦 Project Structure

```text
backend/
  app/
    main.py           # Entry point
    database.py       # DB connection & migrations
    models.py         # SQLAlchemy models
    auth.py           # Security & JWT logic
    routes/           # API Endpoints
      auth.py         # Login/Signup
      leads.py        # Scraping & Results
      admin.py        # User & Payment management
    services/         # Core Logic
      scraper.py      # Playwright & HTTPX scrapers
      validator.py    # Data cleaning & validation
      worker.py       # Background job processing
  requirements.txt    # Dependencies
  .env.example        # Configuration template
```

## ⚙️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd "scrabing tool/backend"
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Setup Environment**:
   - Copy `.env.example` to `.env`
   - Configure your `SECRET_KEY`

5. **Run the server**:
   ```bash
   uvicorn app.main:app --reload
   ```

## 📖 API Usage

### Authentication
- `POST /signup`: Create a new account (requires admin approval).
- `POST /token`: Login to get JWT access token.

### Scraping
- `POST /jobs`: Start a Google Maps or single URL scraping job.
- `POST /jobs/stream`: Start a streaming job (SSE) to see results in real-time.
- `POST /upload-excel`: Bulk upload URLs for scraping.

### Results
- `GET /results`: Fetch all scraped leads with pagination and filtering.
- `GET /results/export`: Download all leads as a CSV.
- `DELETE /results/clear`: Clear all your scraped data.

## 🔮 Future Improvements

- **Async Scaling**: Full integration with PostgreSQL for high-volume data.
- **Distributed Scraping**: Use a cluster of workers for massive bulk jobs.
- **Advanced UI**: A React-based dashboard for easier visualization.

## 📄 License
MIT License
