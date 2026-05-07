# AWS 인프라 구성안

기준 문서: [technical-core-concepts.md](technical-core-concepts.md)

## 1. 목적

이 문서는 기술 구현이 성공했을 때 AWS에서 최소 인프라를 어떻게 구성할지 정리한다.

목표는 대규모 운영이 아니라 다음 루프를 AWS 위에서 반복 가능하게 만드는 것이다.

```text
프로젝트 생성
  -> Docker sandbox 생성
  -> 파일 조작
  -> 코드 실행
  -> 브라우저 조작
  -> 보고서/대시보드 생성
  -> 웹 링크 노출
  -> 아카이브
  -> 복구
```

## 2. AWS 최소 구성 결론

초기 AWS 구성은 **단일 EC2 + Docker Compose**로 시작한다.

```text
Route 53
  -> ALB or CloudFront
  -> EC2
       -> Docker Compose
            -> web
            -> api
            -> traefik
            -> postgres
            -> minio(optional)
            -> project sandbox containers
       -> EBS volume
  -> S3
       -> workspace archives
       -> generated artifacts
```

초기에는 인프라를 쪼개기보다, 제품 루프가 AWS에서 안정적으로 반복되는지 보는 것이 중요하다.

## 3. 서비스 매핑

| 역할 | AWS 서비스 | 초기 결정 |
| --- | --- | --- |
| DNS | Route 53 | 사용 |
| HTTPS 진입점 | ALB 또는 CloudFront | 초기에는 ALB 권장 |
| 앱 서버 | EC2 | Docker Compose 실행 |
| 컨테이너 실행 | EC2 내부 Docker Engine | 사용 |
| Web UI | Docker container | Next.js |
| API | Docker container | Fastify |
| Reverse Proxy | Docker container | Traefik |
| DB | EC2 내부 PostgreSQL 또는 RDS | 초기에는 EC2 내부, 이후 RDS |
| 활성 workspace | EBS volume + Docker volume | 사용 |
| 아카이브 저장 | S3 | 사용 |
| 산출물 저장 | S3 | 사용 |
| 로그 | CloudWatch Logs | 최소 연동 |
| Secret | AWS Secrets Manager 또는 SSM Parameter Store | 초기에는 SSM 권장 |
| 이미지 저장 | ECR | sandbox image 관리 시 사용 |

## 4. 도메인 구조

초기 도메인은 단순하게 잡는다.

```text
app.example.com
preview.example.com
share.example.com
api.example.com
```

역할:

| 도메인 | 역할 |
| --- | --- |
| `app.example.com` | 사용자가 접속하는 제품 UI |
| `api.example.com` | Control Plane API |
| `preview.example.com/p/{project_id}` | sandbox 내부 preview/report 서버 |
| `share.example.com/r/{report_id}` | 광고주/의사결정자 공유용 보고서 URL |

초기에는 wildcard subdomain보다 path 기반 preview를 권장한다.

```text
https://preview.example.com/p/{project_id}
```

이 방식이 DNS와 인증서 관리가 단순하다.

## 5. 네트워크 구성

초기 VPC 구성:

```text
VPC
  public subnet
    -> ALB
    -> EC2
  S3
  CloudWatch
```

초기에는 단순화를 위해 EC2를 public subnet에 둘 수 있다. 다만 보안그룹은 최소한으로 제한한다.

보안그룹:

| 대상 | Inbound |
| --- | --- |
| ALB | 80, 443 from internet |
| EC2 | 80, 443 from ALB, 22 from admin IP only |
| Sandbox containers | 외부 직접 접근 금지, Traefik 통해서만 접근 |

운영에 가까워지면 다음으로 바꾼다.

```text
VPC
  public subnet
    -> ALB
  private subnet
    -> EC2 sandbox host
    -> RDS
  VPC endpoint
    -> S3
```

## 6. EC2 구성

초기 EC2는 Docker host로 사용한다.

권장 시작 스펙:

```text
Instance: t3.large 또는 t3.xlarge
OS: Ubuntu 22.04 LTS
Disk: gp3 EBS 100GB 이상
Runtime: Docker + Docker Compose
```

브라우저 자동화와 Playwright/Chromium은 메모리를 꽤 사용하므로 `t3.medium`은 빠르게 답답해질 수 있다.

초기 추천:

```text
t3.xlarge
  4 vCPU
  16GB RAM
```

동시에 여러 sandbox를 돌릴 계획이면 더 큰 인스턴스가 필요하다.

## 7. Docker Compose 구성

EC2 안에서는 다음 컨테이너를 실행한다.

```text
docker-compose.yml
  web
  api
  traefik
  postgres
  minio(optional)
```

project sandbox container는 `api`가 Docker Engine을 통해 동적으로 생성한다.

```text
api container
  -> Docker socket or Docker API
  -> create project sandbox container
  -> mount project workspace volume
  -> attach network
  -> register preview route
```

중요한 결정:

```text
Docker-in-Docker를 기본 방식으로 쓰지 않는다.
```

대신 API container가 host Docker daemon을 조작해서 **형제 sandbox container**를 만든다.

```text
EC2
  -> Docker Engine
       -> web container
       -> api container
       -> traefik container
       -> postgres container
       -> project-sandbox-123 container
       -> project-sandbox-456 container
```

API container 입장에서는 Docker 안에서 Docker를 만드는 것처럼 보일 수 있지만, 실제 구조는 다음이다.

```text
api container
  -> /var/run/docker.sock
  -> host Docker Engine
  -> create sibling project sandbox container
```

이 방식을 선택하는 이유:

- 진짜 Docker-in-Docker보다 네트워크와 볼륨 관리가 단순하다.
- sandbox container가 Traefik과 같은 Docker network에 붙을 수 있다.
- sandbox 내부 웹서버를 외부 preview URL로 연결하기 쉽다.
- 디버깅이 쉽다.
- 현재 구현 난이도가 낮다.

주의:

Docker socket을 API container에 직접 마운트하면 강력한 권한을 갖게 된다. 현재 구현에서는 허용하되, 운영에서는 별도 sandbox controller process로 분리한다.

운영에 가까워지면 다음 구조로 분리한다.

```text
api container
  -> sandbox-controller service
  -> Docker Engine
```

즉, 현재 구현에서는 빠르게 가기 위해 Docker socket을 사용하되, 이것이 최종 보안 구조는 아니다.

## 8. Workspace 저장

활성 workspace는 EC2의 EBS 기반 Docker volume에 둔다.

```text
/var/lib/docker/volumes/project_{project_id}_workspace
```

샌드박스 내부에서는 다음 경로로 마운트한다.

```text
/workspace
```

비활성화 시:

```text
/workspace
  -> tar.gz
  -> S3 upload
  -> archive metadata DB 저장
```

재활성화 시:

```text
S3 archive download
  -> Docker volume 생성
  -> tar.gz extract
  -> sandbox container start
```

## 9. S3 버킷 구조

S3는 archive와 산출물 저장에 사용한다.

```text
s3://marketing-cowork-prod/
  projects/
    {project_id}/
      archives/
        archive_{timestamp}.tar.gz
      artifacts/
        reports/
        charts/
        exports/
      uploads/
```

공유용 보고서는 초기에는 app 서버가 인증/권한을 확인한 뒤 S3 파일을 읽어 제공한다.

public S3 object를 바로 열어주는 방식은 초기에 피한다.

## 10. DB 구성

초기에는 EC2 내부 PostgreSQL로 시작할 수 있다.

```text
postgres container
  -> EBS volume
```

하지만 현재 구현 이후에는 RDS로 옮기는 것이 좋다.

초기 테이블:

```text
users
projects
project_members
sandboxes
workspace_files
exec_runs
browser_sessions
preview_servers
reports
archives
audit_events
```

## 11. Preview 라우팅

초기 preview는 Traefik path routing으로 처리한다.

```text
https://preview.example.com/p/{project_id}
  -> ALB
  -> EC2
  -> Traefik
  -> project sandbox container:port
```

project sandbox가 preview server를 시작하면 API가 Traefik에 라우팅 정보를 등록한다.

Docker label 방식 또는 Traefik dynamic config file 방식을 사용할 수 있다.

현재 구현에서는 dynamic config file 방식이 디버깅하기 쉽다.

외부 접속 흐름:

```text
project-sandbox-123
  -> report/dashboard server :3000

Traefik
  -> project-sandbox-123:3000

User
  -> https://preview.example.com/p/project_123
```

즉, sandbox container 안에서 실행한 웹서버도 Traefik이 같은 Docker network에서 라우팅하면 실제 외부 접속이 가능하다.

## 12. Browser Runtime

브라우저 자동화는 sandbox container 안에서 실행한다.

```text
project sandbox container
  -> Playwright
  -> Chromium
  -> Xvfb
  -> noVNC
```

사용자별 browser profile은 workspace 안에 둔다.

```text
/workspace/users/{user_id}/browser-profile/
```

2FA/MFA가 필요할 때:

```text
Agent detects 2FA
  -> API creates takeover session
  -> user opens temporary noVNC URL
  -> user completes verification
  -> agent resumes
```

noVNC URL은 짧은 만료시간을 둔다.

## 13. Report/Share 구성

보고서/대시보드 생성 결과는 두 가지 방식으로 처리한다.

### 13.1 Preview

작업 중 결과 확인용.

```text
https://preview.example.com/p/{project_id}
```

### 13.2 Share

광고주/의사결정자 공유용.

```text
https://share.example.com/r/{report_id}
```

share URL은 sandbox에 직접 연결하지 않는다. app/api가 보고서 산출물을 읽어 안전하게 제공한다.

이유:

- sandbox가 꺼져도 보고서 공유가 가능해야 한다.
- 광고주에게 내부 작업환경을 노출하면 안 된다.
- 보고서 접근 권한과 만료 시간을 관리해야 한다.

## 14. 로그와 관측성

최소 로그:

- API request log
- sandbox lifecycle log
- exec run log
- browser action log
- report generation log
- archive/restore log

초기에는 파일 + DB 저장으로 충분하다.

AWS에서는 CloudWatch Logs로도 보낸다.

```text
api logs -> CloudWatch
sandbox logs -> file + DB + CloudWatch
```

## 15. Secrets

초기 secret 저장:

```text
AWS SSM Parameter Store
```

저장 대상:

- DB password
- S3 credentials
- LLM API key
- OAuth client secrets
- internal signing secret

사용자별 외부 서비스 로그인 세션은 secret이 아니라 browser profile로 다룬다. 다만 이 profile은 민감 데이터로 보고 archive/restore 시 접근 권한을 엄격히 관리해야 한다.

## 16. 최소 AWS 단계

### Phase A. 단일 EC2 현재 구현 배포

```text
EC2
  -> docker compose
  -> local postgres
  -> local minio or S3
  -> traefik
```

성공 기준:

- 외부 URL로 app 접속
- project sandbox 생성
- 파일/코드/브라우저/보고서/preview/archive 루프 동작

### Phase B. S3 아카이브 전환

```text
archive
  -> S3
```

성공 기준:

- EC2 volume을 삭제해도 S3 archive에서 프로젝트 복구 가능

### Phase C. RDS 전환

```text
PostgreSQL
  -> RDS
```

성공 기준:

- 앱 컨테이너 교체/EC2 교체와 DB 상태가 분리됨

### Phase D. Sandbox Host 분리

```text
EC2 app host
EC2 sandbox host
```

성공 기준:

- sandbox 실행 부하가 web/api를 방해하지 않음

## 17. 언제 확장하는가

| 신호 | 확장 |
| --- | --- |
| sandbox 실행이 app/api를 느리게 함 | sandbox host 분리 |
| PostgreSQL 백업/복구가 중요해짐 | RDS |
| archive 용량 증가 | S3/R2 중심으로 전환 |
| preview 트래픽 증가 | ALB/CloudFront/Traefik 분리 |
| 동시 실행 증가 | sandbox worker pool |
| 고객별 보안 요구 증가 | 고객별 Docker host 또는 VM/microVM 검토 |

## 18. 이번 단계에서 하지 않는 것

초기 AWS 구성에서 하지 않는다.

- EKS
- ECS/Fargate
- Lambda 중심 구조
- VM/microVM
- 고객별 전용 VPC
- 복잡한 autoscaling
- 고급 billing/resource quota

먼저 단일 EC2 + Docker Compose로 기술 루프를 증명한다.
