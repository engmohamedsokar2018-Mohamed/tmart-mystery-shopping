# Talabat Mart Mystery Shopping System - Full Web App

A complete Flask + SQLite web application converted from the original single-page HTML/localStorage version.

## Features
- Login / logout with secure password hashing
- Admin dashboard
- SQLite database
- Admin can add/edit/delete users
- Admin can add/edit/delete audits
- Admin can add/edit/delete issues
- Store directory seeded with DS01–DS75
- Auditor can submit audits and view own submissions
- CSV export for audits, issues, and users
- Responsive UI based on the uploaded Talabat Mart Mystery Shopping design

## Default accounts
- Admin: `admin` / `Admin@2024`
- Auditor: `abdelmaged` / `AMaged@2024`

## Run locally
```bash
cd tmart_mystery_full_app
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open: http://127.0.0.1:5000

## Database
The app creates `tmart_mystery.db` automatically on first run and seeds default users, stores, sample audits, and sample issues.
