# 🐕 Project Cerberus

**A life list for dog spotters.** Every time you see a dog, log its breed. The first time you log a breed it becomes a *lifer*. The goal is to collect all 100 of the most popular breeds.

It's inspired by bird-watching life lists, but for the dogs you pass in the park.

## Features

- **Spotter profiles**: several people can keep their own life lists on one machine.
- **Log a sighting**: pick the breed (searchable, and breeds you haven't collected yet are marked ✨ new), the date, where you saw it, the dog's name and notes.
- **Lifer celebrations**: a new breed gets balloons 🎉.
- **Life list**: progress towards 100 breeds, the date you first saw each one and how many times, filterable by collected or still to find.
- **Sightings history**: every dog you've logged, with the option to delete mistakes.

## Tech

| Layer | Choice |
|---|---|
| UI | [Streamlit](https://streamlit.io) |
| Storage | SQLite (Python's built-in `sqlite3`) |
| Data | Pandas |
| Tests | pytest, plus Streamlit's `AppTest` for end-to-end checks |

```
project-cerberus/
├── app.py              # Streamlit UI
├── cerberus/
│   └── db.py           # Database schema and queries (lifer logic lives here)
├── data/
│   └── breeds.csv      # Top 100 breeds, AKC 2025 popularity ranking
└── tests/              # Unit tests for db.py and an end-to-end app test
```

## Run it locally

You need Python 3.12 or newer.

```bash
git clone https://github.com/charlesingramsmith/project-cerberus.git
cd project-cerberus
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

Run the tests with `pytest`.

Your sightings are saved to `data/cerberus.db`. That file is git-ignored, so your data stays on your machine.

## Roadmap

- [x] Manual sighting log and life list for the top 100 breeds
- [ ] 📷 Photo upload with a sighting
- [ ] 🤖 Breed identification from a photo (an image classification model)
- [ ] More breeds beyond the top 100 (just add rows to `data/breeds.csv`)
- [ ] Map of where you've spotted dogs
- [ ] Deploy to Streamlit Community Cloud with real user accounts

## Data source

Breed popularity ranking: [American Kennel Club, Most Popular Dog Breeds of 2025](https://www.akc.org/expert-advice/news/most-popular-dog-breeds-2025/).
