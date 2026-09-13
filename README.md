[README.md](https://github.com/user-attachments/files/32161428/README.md)
# ExceptionIQ

Operational exception intelligence & value recovery for B2B Order-to-Cash (O2C).

## Stack
- Python / Streamlit
- PostgreSQL
- pandas
- psycopg2

## Architecture
Raw source data -> staging -> trusted core -> analytics -> Streamlit case-management UI.

The app expects an accessible PostgreSQL database containing the `analytics` schema and its ExceptionIQ tables.

## Run locally
1. Install dependencies:
   `pip install -r requirements.txt`
2. Set the PostgreSQL environment variables from `.env.example`.
3. Run:
   `streamlit run app.py`

## Deploy on Streamlit Community Cloud
1. Push this repository to GitHub.
2. Create a Community Cloud app from the GitHub repository and select `app.py` as the entrypoint.
3. In Advanced settings / Secrets, add a hosted PostgreSQL connection string:
   `DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require"`
4. Deploy.

Do not commit database credentials. Streamlit Community Cloud secrets are stored outside the repository.

## Database note
The local development database currently runs on PostgreSQL. A cloud deployment cannot reach `localhost`, so the same schema/data must be hosted on an externally reachable PostgreSQL provider (for example, Neon or Supabase) before the deployed app can function end-to-end.
