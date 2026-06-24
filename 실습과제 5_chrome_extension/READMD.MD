# 부처 RSS 알리미 (Chrome Extension)

## 개요
이 확장 프로그램은 아래 RSS를 읽어와서, 작성자(부처명) 기준으로 기사를 필터링해 보여줍니다.

- RSS 주소: `https://www.mois.go.kr/gpms/view/jsp/rss/rss.jsp?ctxCd=1012`
- 작성자 필드(`dc:creator`/`author`)를 "부처명"으로 사용

## 주요 기능
1. 부처명 다중 선택 (기본값: 전체 부처 자동 선택)
2. 선택한 부처의 기사 제목 + 내용 일부(요약) 표시
3. 기사 클릭 시 새 탭으로 원문 링크 열기
4. 선택된 부처 중 새 RSS 글 등록 시 크롬 알림 표시

## 파일 구성
- `manifest.json`: 확장 프로그램 설정
- `popup.html`: 팝업 UI 구조
- `popup.css`: 팝업 스타일
- `popup.js`: RSS 조회/필터/목록 렌더링
- `background.js`: 주기 체크 및 신규 글 알림
- `rss.svg`: 확장/알림 아이콘
- `READMD.MD`: 설명 문서

## 설치 방법 (개발자 모드)
1. 크롬에서 `chrome://extensions` 접속
2. 우측 상단 `개발자 모드` 활성화
3. `압축해제된 확장 프로그램을 로드` 클릭
4. `mois_rss_chrome_extension` 폴더 선택

## ZIP 생성 방법
아래 명령으로 압축 파일을 만들 수 있습니다.

```bash
cd mois_rss_chrome_extension
zip -r ../mois_rss_chrome_extension.zip .
```

## 참고
- 알림은 선택된 부처의 최신 글이 이전 체크 시점 대비 바뀌면 발생합니다.
- 최초 기준점 설정 시에는 알림이 발생하지 않습니다.
