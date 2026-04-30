# haro 제품 스펙 폴더

이 폴더는 haro를 비개발자용 AI 업무 실행 솔루션으로 발전시키기 위한 제품/기능 스펙을 모은다.
haro는 특정 직종 전용 도구가 아니라, 화이트칼라 업무를 workflow와 의사결정 트리로 구조화해 자동화하는 플랫폼을 지향한다.

현재 구현물은 프로젝트 워크스페이스, 파일/폴더 탐색, 업로드, 미리보기, 편집, 채팅형 에이전트, 작업모드/배포모드의 기술 기반을 갖춘 상태다. 다음 단계의 제품 방향은 이 기반을 비개발자가 실제 업무에 쓸 수 있는 형태로 감싸는 것이다.

## 핵심 방향

1. 강력한 하네스 기능
2. 비개발언어로 스킬 제작

여기서 하네스는 단순한 파일 탐색기가 아니다. 사용자가 흩어진 파일을 던지면 haro가 업무 단위로 정리하고, 파일의 의미와 처리 상태를 파악하며, 다음 실행에 필요한 맥락을 유지하는 작업 환경이다.

비개발언어 스킬 제작은 사용자가 코드를 작성하지 않고도 “우리 팀은 이렇게 처리한다”는 업무규칙을 haro가 반복 가능한 스킬로 바꾸는 기능이다.
대행사/마케팅 시나리오는 대표 적용 예시이며, 제품 구조는 HR, 재무, 법무, 영업, CS, 운영 등 화이트칼라 업무 전반에 열려 있어야 한다.
성공한 프로젝트의 meta 설정은 프로젝트 fork를 통해 template family로 저장하고, 새 프로젝트와 다른 vertical에 확장할 수 있어야 한다.

## 문서 목록

- [01-product-direction.md](./01-product-direction.md): 제품 방향과 핵심 개념
- [02-harness-spec.md](./02-harness-spec.md): 하네스 기능 상세 스펙
- [03-natural-language-skill-spec.md](./03-natural-language-skill-spec.md): 비개발언어 스킬 제작 스펙
- [04-agency-scenario-spec.md](./04-agency-scenario-spec.md): 대행사 시나리오 기반 사용자 흐름
- [05-development-roadmap.md](./05-development-roadmap.md): 구현 단계와 우선순위
- [06-chat-session-file-spec.md](./06-chat-session-file-spec.md): 채팅세션을 폴더/파일로 관리하는 스펙
- [07-clean-room-versioning-spec.md](./07-clean-room-versioning-spec.md): Data/Meta Clean Room과 내부 Git 버전 관리 스펙
- [08-white-collar-workflow-spec.md](./08-white-collar-workflow-spec.md): 화이트칼라 업무를 workflow/의사결정 트리로 일반화하는 스펙
- [09-project-fork-template-spec.md](./09-project-fork-template-spec.md): 프로젝트 fork와 meta template engine/템플릿 엔진 스펙
- [10-google-drive-connector-spec.md](./10-google-drive-connector-spec.md): Google Drive 데이터소스 연결과 가져오기 중심 연동 스펙
- [11-gmail-crm-inbox-spec.md](./11-gmail-crm-inbox-spec.md): Gmail LLM triage 기반 CRM형 업무 인박스 스펙
- [12-hook-integration-spec.md](./12-hook-integration-spec.md): 통지형/외부 연계형 hook과 정책별 자동 실행 스펙
- [13-human-context-analysis-spec.md](./13-human-context-analysis-spec.md): 인간분석과 숨은 사람 맥락 관리 스펙
- [14-workspace-file-db-spec.md](./14-workspace-file-db-spec.md): 워크스페이스 파일관리 DB와 FTS 검색 스펙
- [15-debug-mode-spec.md](./15-debug-mode-spec.md): 채팅 턴별 LLM 교신을 추적하는 디버그 모드 스펙
- [tasks/README.md](./tasks/README.md): 스펙을 실제 개발 주기로 쪼갠 작업 계획과 검증 기록

## 상세 사용자 시나리오

- [scenarios/README.md](./scenarios/README.md): 긴 서사형 사용자 시나리오 폴더 안내
- [scenarios/00-writing-guide.md](./scenarios/00-writing-guide.md): 시나리오 작성 톤과 기능 번역 규칙
- [scenarios/01-agency-survival-scenario.md](./scenarios/01-agency-survival-scenario.md): 마진 박한 대행사의 생존과 확산 시나리오
- [scenarios/02-startup-planner-cs-scenario.md](./scenarios/02-startup-planner-cs-scenario.md): CS까지 떠안은 스타트업 기획자 시나리오
- [scenarios/03-smartstore-founder-scenario.md](./scenarios/03-smartstore-founder-scenario.md): 오늘 할 일을 잃은 스마트스토어 창업자 시나리오
- [scenarios/04-hr-manager-scenario.md](./scenarios/04-hr-manager-scenario.md): 반복 질문에 묶인 300명 조직 HR 담당자 시나리오

## 참고 문서

- [../haro-project-spec.md](../haro-project-spec.md): 현재 구현 기반 스펙
- [../marketing-cowork-solution/haro-main-features.md](../marketing-cowork-solution/haro-main-features.md): 업무규칙 학습과 기억 중심의 제품 정의
- [../marketing-cowork-solution/user-scenario-haro.md](../marketing-cowork-solution/user-scenario-haro.md): 대행사/마케팅팀 사용자 시나리오
- [../marketing-cowork-solution/technical-poc.md](../marketing-cowork-solution/technical-poc.md): 기술 POC 아이디어
