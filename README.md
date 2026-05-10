# K-POLITICS Update

Overwrite these files:

- docs/index.html
- docs/app.js
- scripts/collect.py
- requirements.txt

Then append `docs/style-additions.css` to the bottom of your existing `docs/style.css`.

Run:

```bat
py -m pip install -r requirements.txt
py scripts\collect.py
```

Expected final output:

```txt
Items: ? / News: ? / GDELT: ? / RSS: ? / K-INVEST: ? / K-POLITICS: ? / Papers: ?
```
