# Inkloom Project

Inkloom is a Django application for checking marketing content against brand rules, collecting creator decisions, and recording manager approvals in an audit log.

## Requirements

- Python 3.12 or later
- The dependencies in `requirements.txt`

## Run locally (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. The dashboard seeds the starter rule set on first use. To run the tests, use `python manage.py test`.

For deployments, set `DJANGO_SECRET_KEY` to a unique secret, set `DJANGO_DEBUG=false`, and set `DJANGO_ALLOWED_HOSTS` to a comma-separated list of the site's hostnames. The development secret fallback is not suitable for deployment.

## Workflow

1. Submit a draft for a scan of configured phrases, visual color, and image alt text.
2. Review findings and accept suggestions or provide a justification to override them.
3. Approve the submission or request changes after all findings have been resolved.
4. Review the recorded actions and hashes in the submission audit trail.

This project currently uses a local SQLite database and a deterministic phrase-matching scanner; it does not call an external AI service. Configure authentication, a production database, backups, and HTTPS before using it with real users or confidential content.
