# Breathe ESG Ingestion Prototype

Django + React prototype for ingesting SAP fuel/procurement, utility electricity, and corporate travel extracts into a normalized analyst review queue.

## Run locally

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Demo rows seed automatically the first time the dashboard loads.

## Sample uploads

- `sample_data/sap_material_documents.csv`
- `sample_data/utility_electricity.csv`
- `sample_data/concur_travel_transactions.json`

## Deployment

Render/Railway settings:

- Build command: `python -m pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput`
- Start command: `gunicorn config.wsgi:application`
- Environment variables: `DEBUG=False`, `ALLOWED_HOSTS=<your-hostname>,localhost,127.0.0.1`, `SECRET_KEY=<secret>`

This prototype uses SQLite for portability. For a real deployment, use Postgres and persistent storage.
