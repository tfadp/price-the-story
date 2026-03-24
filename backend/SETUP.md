# Backend Setup

## 1. Get your Anthropic API key
1. Go to https://console.anthropic.com
2. Create an account and generate an API key
3. Copy it — you'll need it in step 3

## 2. Install dependencies
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate      # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Configure environment
```bash
cp .env.example .env
# Edit .env and paste your ANTHROPIC_API_KEY
```

## 4. Run the server
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 5. Test it
```bash
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0"}

curl -X POST http://localhost:8000/analyze-ticker \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'
```

## 6. Run tests
```bash
cd backend
pytest tests/ -v
```

## Optional API keys (improves data quality)
- **FMP** (analyst estimates): https://financialmodelingprep.com — free tier, no card
- **Finnhub** (news + transcripts): https://finnhub.io — free tier, no card
