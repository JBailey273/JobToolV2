New Repo for V2 of Job Tracking Tool

### Getting started locally

1. Install dependencies: `pip install -r requirements.txt`
2. Apply database migrations: `python jobtracker/manage.py migrate`

The site returns a 500 error if migrations have not been applied because
the middleware detects the pending schema updates. Running the migrate
command initializes the SQLite database so the app can start normally.
