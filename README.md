# Disease Prediction

A symptom-based disease prediction app with login, dashboard, symptom checker, ranked result report,
history, health profile and BMI / blood pressure / blood sugar tools.

This is an educational, rule-based tool. The match score shows how closely symptoms fit a condition.
It is not a probability and not a medical diagnosis.

## What is in this repo

| Path | What it is | Where it runs |
| --- | --- | --- |
| `app.py`, `requirements.txt` | Python app (Streamlit + SQLite) | Your computer, Streamlit Community Cloud |
| `netlify/index.html` | Static version (HTML, CSS, JavaScript, one file) | Netlify, GitHub Pages |

Netlify hosts static sites only, so it cannot run `app.py`. Use `netlify/index.html` for Netlify.

## Run the Python app on your computer

```
pip install -r requirements.txt
streamlit run app.py
```

The database file `disease_prediction.db` is created automatically on the first run.

## Put the code on GitHub

```
git init
git add .
git commit -m "Disease Prediction app"
git branch -M main
git remote add origin https://github.com/<your-username>/disease-prediction.git
git push -u origin main
```

Or create a new repository on github.com, choose "uploading an existing file" and drag in the unzipped files.

## Deploy the Python app (free): Streamlit Community Cloud

1. Push this repo to GitHub.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click "Create app", pick this repo, branch `main`, main file `app.py`, then Deploy.

Note: the SQLite file on Streamlit Community Cloud can reset when the app restarts. For permanent accounts
use a hosted database.

## Deploy the static site on Netlify

Option 1, drag and drop: open https://app.netlify.com/drop and drop the `netlify` folder (or the
`disease-prediction-netlify.zip` file).

Option 2, from GitHub: Add new site, Import an existing project, choose this repo. `netlify.toml`
already sets the publish directory to `netlify`, so leave the build command empty.

The static version saves accounts and reports in the visitor's own browser (localStorage). They are not shared
between devices.
