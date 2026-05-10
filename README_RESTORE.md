# 원래 실시간 업데이트 방식 복구 파일

## 복구 핵심

원래 구조는 다음과 같습니다.

1. `scripts/collect.py`가 외부 기사/논문/RSS를 수집합니다.
2. 수집 결과를 `docs/data/latest.json`으로 저장합니다.
3. 웹페이지의 `Reload` 버튼은 새로 수집하는 버튼이 아니라, 현재 올라가 있는 `latest.json`을 다시 불러오는 버튼입니다.
4. 새 기사 수집은 로컬에서 `py scripts\collect.py`를 실행하거나, GitHub Actions의 `Run workflow` / schedule로 실행합니다.

## 덮어쓰기 파일

아래 파일은 기존 프로젝트 같은 경로에 덮어쓰세요.

- `docs/index.html`
- `docs/app.js`
- `docs/style.css`
- `scripts/collect.py`
- `requirements.txt`
- `.github/workflows/update.yml`

## 주의

이 ZIP에는 `docs/data/latest.json`을 넣지 않았습니다.
이미 정상 기사 데이터가 들어 있는 파일을 빈 파일로 덮어쓰는 사고를 막기 위해서입니다.

새 데이터는 아래 명령으로 생성하세요.

```bat
cd C:\GLOBAL-SEMICONDUCTOR-SIGNAL-main
py -m pip install -r requirements.txt
py scripts\collect.py
```

정상 출력 예시:

```txt
Items: ? / News: ? / GDELT: ? / RSS: ? / K-INVEST: ? / Papers: ?
```

그 다음 GitHub에는 아래를 올리세요.

- `docs/index.html`
- `docs/app.js`
- `docs/style.css`
- `scripts/collect.py`
- `requirements.txt`
- `.github/workflows/update.yml`
- `docs/data/latest.json`  ← collect.py 실행 후 생성/갱신된 파일
