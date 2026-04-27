# MMF 피어그룹 비교표

## 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 파일 구조
```
mmf_app/
├── app.py          # Streamlit 진입점
├── config.py       # ★ 펀드 추가/삭제/변경은 여기만
├── parser.py       # 엑셀 파싱 로직
├── renderer.py     # HTML·PNG 렌더링
└── requirements.txt
```

## 펀드 추가/삭제/변경
`config.py` 에서:
1. `FUND_MAP`      → 펀드코드 : 정규화명 추가
2. `FUND_DISPLAY`  → 펀드코드 : 표 헤더명 추가
3. `FUND_ORDER`    → 표시 순서에 코드 추가
4. `STATIC_ROWS`   → 각 하드코딩 행에 값 추가
