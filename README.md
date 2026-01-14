
# Wallet Store Agent — Final Project

This repository contains a small example e-commerce "Wallet Store" agent used for demonstration and assignment purposes.

**Setup**
- **Prerequisites:** Python 3.10+ and pip.
- Create and activate a virtual environment (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

- Install dependencies (core and optional LLM extras):

```powershell
pip install -r requirements.txt
# Optional (for LLM/Gemini features):
pip install python-dotenv google-genai
```

**Database (seed)**
- The app uses an SQLite DB at `data/ecommerce.db` by default.
- Seed the database with sample users/products/orders:

```powershell
python -m src.seed_db
```

Seeded users (IDs): `u_1001` (Alex Chen), `u_1002` (Sam Rivera), `u_1003` (Taylor Okafor).

**Environment variables (optional LLM features)**
- For Gemini (LLM) features set `GEMINI_API_KEY` in your environment. For the current PowerShell session:

```powershell
$Env:GEMINI_API_KEY = "your_api_key_here"
```

To persist across sessions on Windows (PowerShell/cmd):

```powershell
setx GEMINI_API_KEY "your_api_key_here"
```

**Run / Usage**
- Interactive chat CLI (choose a seeded `user_id` when prompted):

```powershell
python -m src.chat_cli --mode auto --model gemini-2.5-flash
```

- Audit CLI (quick report for a user):

```powershell
python -m src.audit_cli --user_id u_1001
```

- Demo script (programmatic demo of tools):

```powershell
python -m src.tools_demo
```

**Files of interest**
- Source: [src/](src)
- Database schema: [src/schema.sql](src/schema.sql)
- DB seed script: [src/seed_db.py](src/seed_db.py)
- Interactive chat CLI: [src/chat_cli.py](src/chat_cli.py)
- Audit CLI: [src/audit_cli.py](src/audit_cli.py)

**Notes / Troubleshooting**
- If you plan to use LLM/Gemini features, install `google-genai` and set `GEMINI_API_KEY`.
- If the DB is missing, run the seed command above to create `data/ecommerce.db`.
