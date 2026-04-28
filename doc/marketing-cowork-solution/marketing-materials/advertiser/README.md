# 광고주 시나리오 웹툰 자료

기준 시나리오: [user-scenario-haro-advertiser.md](../../user-scenario-haro-advertiser.md)

## 제작물

| 파일 | 역할 |
| --- | --- |
| [storyboard.md](storyboard.md) | 컷별 장면, 대사, 감정, 화면 구성 |
| [character-sheet.md](character-sheet.md) | 주요 인물과 하로의 시각적 설정 |
| [webtoon-script.md](webtoon-script.md) | 실제 웹툰 원고 형태의 세로 스크롤 구성 |
| [assets/](assets/) | 생성된 캐릭터 시트, UI 레퍼런스, 웹툰 컷 이미지 |

## 이미지 저장 규칙

생성 이미지는 반드시 `assets/` 폴더에 저장한다.

현재 저장된 이미지:

| 파일 | 내용 |
| --- | --- |
| [assets/character-sheet-v1.png](assets/character-sheet-v1.png) | 초기 인물 캐릭터 시트 |
| [assets/haro-ui-reference-v1.png](assets/haro-ui-reference-v1.png) | 최종 유지할 하로 UI 레퍼런스 |
| [assets/haro-icon-reference-v2.png](assets/haro-icon-reference-v2.png) | 최종 하로 아이콘 레퍼런스 |

완성된 웹툰 이미지:

| 페이지 | 파일 | 내용 |
| --- | --- | --- |
| 1 | [assets/webtoon-page-01-text.png](assets/webtoon-page-01-text.png) | 숫자가 이상하다 |
| 2 | [assets/webtoon-page-02-text.png](assets/webtoon-page-02-text.png) | 대행사 보고서의 괴리 |
| 3 | [assets/webtoon-page-03-text.png](assets/webtoon-page-03-text.png) | 모두 광고 문제처럼 말한다 |
| 4 | [assets/webtoon-page-04-text.png](assets/webtoon-page-04-text.png) | 작은 단서들이 지나간다 |
| 5 | [assets/webtoon-page-05-text.png](assets/webtoon-page-05-text.png) | 서진의 진짜 공포 |
| 6 | [assets/webtoon-page-06-text.png](assets/webtoon-page-06-text.png) | 누군가 하로를 소개한다 |
| 7 | [assets/webtoon-page-07-text.png](assets/webtoon-page-07-text.png) | 반신반의하며 열어본 첫 화면 |
| 8 | [assets/webtoon-page-08-text.png](assets/webtoon-page-08-text.png) | 하로는 바로 답하지 않는다 |
| 9 | [assets/webtoon-page-09-text.png](assets/webtoon-page-09-text.png) | 시간축이 맞물린다 |
| 10 | [assets/webtoon-page-10-text.png](assets/webtoon-page-10-text.png) | 고객의 말이 원인이 된다 |
| 11 | [assets/webtoon-page-11-text.png](assets/webtoon-page-11-text.png) | 클레임은 미래의 매출 하락이다 |
| 12 | [assets/webtoon-page-12-text.png](assets/webtoon-page-12-text.png) | 서진의 요구가 바뀐다 |
| 13 | [assets/webtoon-page-13-text.png](assets/webtoon-page-13-text.png) | 상황판의 등장 |
| 14 | [assets/webtoon-page-14-text.png](assets/webtoon-page-14-text.png) | 팀 회의가 달라진다 |
| 15 | [assets/webtoon-page-15-text.png](assets/webtoon-page-15-text.png) | 대행사 미팅의 역전 |
| 16 | [assets/webtoon-page-16-text.png](assets/webtoon-page-16-text.png) | 작은 승리 |
| 17 | [assets/webtoon-page-17-text.png](assets/webtoon-page-17-text.png) | 하로의 정체 |
| 18 | [assets/webtoon-page-18-text.png](assets/webtoon-page-18-text.png) | 마지막, CEO의 퇴근 |

하로 UI는 [assets/haro-ui-reference-v1.png](assets/haro-ui-reference-v1.png)의 깔끔한 SaaS 스타일을 기준으로 한다.

하로 아이콘은 [assets/haro-icon-reference-v2.png](assets/haro-icon-reference-v2.png)를 최종 기준 레퍼런스로 사용한다. 이 파일의 앱 아이콘, 말풍선 버전, 대시보드 보조 버전, 360도 뷰, 얼굴 클로즈업, 표정 변형을 웹툰과 제품 화면의 공통 기준으로 삼는다.

하로 아이콘은 다음처럼 설정한다.

```text
라임 그린 원형 아이콘
귀여운 타원형 눈 두 개
광택감 있는 말랑한 구체
단순하고 기억하기 쉬운 AI 파트너
특정 캐릭터를 그대로 복제하지 않는 오리지널 디자인
```

이후 생성물은 다음 이름부터 사용한다.

```text
assets/webtoon-page-01-text.png
assets/webtoon-page-02-text.png
assets/webtoon-page-03-text.png
...
assets/webtoon-page-18-text.png
```

웹툰은 총 18페이지로 제작한다.

```text
스토리보드 1컷 = 웹툰 1페이지
...
```

## 톤

- 현실적인 스타트업/D2C 브랜드 내부 이야기
- CEO가 겪는 답답함에서 시작
- 광고 성과, 리뷰, 댓글, 클레임이 하나로 연결되는 순간을 시각적으로 강조
- 하로는 라임 그린 원형 아이콘과 깔끔한 SaaS UI로 표현
- 마지막에는 “CEO가 실무자가 아니라 슈퍼바이저가 되는 변화”를 보여준다.
