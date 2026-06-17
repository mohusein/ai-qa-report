# AI QA Report — Setup & Usage

## 1. Install dependencies
```
pip install -r requirements.txt
```

## 2. Configure API keys
Create two plain-text files in this folder (no quotes, just the raw key):
- `api_key.txt` — your OpenAI API key
- `deepgram_key.txt` — your Deepgram API key  
  *(only needed if processing audio files via `app.py`)*

## 3. Configure the database
Edit `config.py` and update `DB_CONFIG` with your MySQL credentials.

## 4. Create the database
```
mysql -u root -p < schema.sql
```

## 5. Grade transcript files (batch)
Drop `.txt` transcript files into the `output/` folder, then run:
```
python critiera.py
```
Filename format: `Agent_Name-PhoneNumber-YYYY-MM-DD.txt`  
Example: `John_Doe-5551234567-2026-05-28.txt`

## 6. Process a single audio recording
```
python app.py path/to/recording.wav \
  --uuid my-call-id \
  --agent-id 505 \
  --duration 320 \
  --hangup Customer \
  --transfer Mortgage_Dept
```

## 7. Launch the dashboard
```
streamlit run dashboard.py
```

---

## File overview
| File | Purpose |
|------|---------|
| `config.py` | Central config — DB credentials, key file paths, directories |
| `engine.py` | `QAEngine` class — Deepgram transcription + OpenAI grading |
| `critiera.py` | Batch-grade `.txt` transcript files |
| `app.py` | Process a single audio file end-to-end |
| `dashboard.py` | Streamlit dashboard |
| `schema.sql` | MySQL schema (run once) |
