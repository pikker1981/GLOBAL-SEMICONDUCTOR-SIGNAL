# 긴급 복구 패키지: 기사 데이터 + 버튼 2개 복구

## 왜 기사와 버튼이 사라졌나

- `docs/data/latest.json`이 빈 placeholder로 덮이면 기사 목록이 전부 사라집니다.
- 이 복구 ZIP은 사고 방지를 위해 `docs/data/latest.json`을 포함하지 않습니다.
- 새 기사 데이터는 `scripts/collect.py`를 실행해서 다시 생성해야 합니다.

## 복구되는 버튼

- `Update Data`: GitHub Actions의 `update.yml` 실행 화면을 엽니다.
- `Reload`: 현재 배포된 `docs/data/latest.json`을 다시 불러옵니다.

주의: GitHub Pages는 정적 페이지라 브라우저에서 Python을 직접 실행할 수 없습니다.
실제 수집은 로컬 `collect.py` 또는 GitHub Actions가 수행합니다.

## 덮어쓰기 파일

- `docs/index.html`
- `docs/app.js`
- `docs/style.css`
- `scripts/collect.py`
- `requirements.txt`
- `.github/workflows/update.yml`

## 기사 복구

로컬에서:

```bat
cd C:\GLOBAL-SEMICONDUCTOR-SIGNAL-main
py -m pip install -r requirements.txt
py scripts\collect.py
```

또는 ZIP 안의 `RUN_UPDATE_LOCAL.bat`를 프로젝트 루트에 복사한 뒤 실행하세요.

생성된 `docs/data/latest.json`을 GitHub에 업로드해야 웹에 기사 목록이 다시 표시됩니다.
