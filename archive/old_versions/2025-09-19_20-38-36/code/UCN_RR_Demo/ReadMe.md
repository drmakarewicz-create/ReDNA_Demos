# UcnrrEngineDemo

This is a tiny UCN/RR-side demo that can:

- Connect to a running **Core** (if the `core` package is importable) **or**
- Load a Core snapshot JSON
- Run a very small **validator** to sanity-check the Core snapshot structure
- Show the snapshot

## Quick start

```bash
cd UcnrrEngineDemo
pip install -r requirements.txt  # if you have one, otherwise streamlit only
streamlit run app.py