# Talabat Mart Mystery Shopping Pro

Full Flask web app with admin panel, users, roles, audits, issues, stores, dashboard, CSV export, and Railway-ready deployment.

## Default Admin
Username: `admin`  
Password: `Admin@2024`

Change password after first login.

## Local Run
```bash
pip install -r requirements.txt
python app.py
```

## Railway Run
Start command:
```bash
gunicorn app:app
```

Recommended Railway variables:
```bash
SECRET_KEY=change-this-secret
DATABASE_URL=Railway PostgreSQL URL
```

If no DATABASE_URL exists, the app uses local SQLite.
