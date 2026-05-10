# Final GitHub Upload Files

이 ZIP은 `docs/data/latest.json`을 포함하지 않습니다.
빈 latest.json이 올라가면 기사 목록이 사라지기 때문입니다.

## 포함 파일

- docs/index.html
- docs/app.js
- docs/style.css
- scripts/collect.py
- requirements.txt
- .github/workflows/update.yml

## 적용 후 로컬 실행

```bat
cd C:\GLOBAL-SEMICONDUCTOR-SIGNAL-main
py -m pip install -r requirements.txt
py scripts\collect.py
```

정상 출력에는 아래가 포함되어야 합니다.

```txt
K-POLITICS: 숫자
```

그 후 생성된 `docs/data/latest.json`도 GitHub에 업로드하세요.

## 버튼

- Update Data: GitHub Actions update.yml 화면 열기
- Reload: 현재 배포된 latest.json 다시 읽기
