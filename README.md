# OPC UA Client Python

OPC UA 서버와 상호작용할 수 있는 Python 기반 클라이언트 애플리케이션입니다. asyncua 라이브러리를 기반으로 하여 안정적이고 확장 가능한 OPC UA 클라이언트 기능을 제공합니다.

## 주요 기능

### 🔗 연결 관리
- **다중 세션 지원**: 여러 서버에 동시 연결 가능
- **자동 재연결**: 연결 끊김 시 자동 복구
- **엔드포인트 조회**: 서버의 보안 정책 및 인증서 정보 확인

### 📊 데이터 처리
- **노드 정보 조회**: 상세한 노드 속성 및 메타데이터 확인
- **데이터 읽기/쓰기**: 다양한 데이터 타입 지원
- **노드 탐색**: 계층적 구조 탐색 및 검색

### 📡 구독 및 모니터링
- **데이터 변경 구독**: 실시간 데이터 변경 알림
- **이벤트 구독**: 서버 이벤트 실시간 모니터링
- **구독 관리**: 생성, 수정, 삭제 기능

### ⚙️ 고급 기능
- **메서드 호출**: 서버 메서드 실행
- **모니터링 모드**: 실시간 데이터 스트리밍
- **이벤트 뷰**: 전용 이벤트 모니터링 인터페이스

## 설치 및 설정

### 1. 시스템 요구사항
- Python 3.8 이상
- pip 패키지 관리자

### 2. 의존성 설치
```bash
# 저장소 클론
git clone https://github.com/Ignimkk/opcua_client_python.git
cd opcua_client_python

# 필요한 패키지 설치
pip install -r requirements.txt
```

### 3. 기본 설정
```bash
# 기본 서버 URL 설정 (선택사항)
# opcua_app.py 파일의 DEFAULT_SERVER_URL 변수 수정
DEFAULT_SERVER_URL = "opc.tcp://your-server:4840/your-endpoint"
```

## 테스트용 OPC UA 서버

### 공식 레퍼런스 서버 사용

이 클라이언트를 테스트하기 위해 [OPC Foundation의 공식 .NET Standard 레퍼런스 서버](https://github.com/OPCFoundation/UA-.NETStandard)를 사용할 수 있습니다.

#### 레퍼런스 서버 실행 방법

1. **레퍼런스 서버 다운로드**:
   ```bash
   git clone https://github.com/OPCFoundation/UA-.NETStandard.git
   cd UA-.NETStandard
   ```

2. **레퍼런스 서버 실행**:
   ```bash
   # Applications/ConsoleReferenceServer 디렉토리로 이동
   cd Applications/ConsoleReferenceServer
   
   # 서버 실행
   dotnet run --project ConsoleReferenceServer.csproj --framework net9.0
   ```

3. **연결 설정**:
   - 기본 URL: `opc.tcp://localhost:62541/Quickstarts/ReferenceServer`
   - 포트: 62541 (기본값)
   - 엔드포인트: Quickstarts/ReferenceServer

#### 레퍼런스 서버 특징

- **OPC Foundation 공식 인증**: OPC Foundation 인증 테스트 랩을 통과
- **완전한 OPC UA 기능**: 모든 표준 기능 지원
- **다양한 보안 정책**: Anonymous, Username, X.509 인증서 지원
- **이벤트 생성**: 테스트용 이벤트 자동 생성
- **메서드 제공**: 호출 가능한 메서드 포함

#### 레퍼런스 서버 설정

레퍼런스 서버는 자동으로 다음을 생성합니다:
- 자체 서명된 인증서 (첫 실행 시)
- Local Discovery Server (LDS) 등록
- 다양한 테스트 노드 및 데이터

### 다른 OPC UA 서버

다른 OPC UA 서버를 사용할 경우:
- 서버 URL 및 포트 확인
- 보안 정책 설정 확인
- 인증서 교환 필요 여부 확인

## 사용 방법

### 1. 애플리케이션 실행
```bash
python3 opcua_app.py
```

### 2. 메인 메뉴 사용법

#### 🔍 서버 연결 및 관리
```
0. List Server Endpoints    - 서버 엔드포인트 조회
1. Connect to Server       - 새 세션으로 서버 연결
2. Disconnect Current      - 현재 세션 연결 해제
3. List and Switch Sessions - 세션 목록 및 전환
```

#### 📊 데이터 작업
```
4. Get Node Information    - 노드 상세 정보 조회
5. Read Node Value         - 노드 값 읽기
6. Write Node Value        - 노드 값 쓰기
7. Browse Nodes            - 노드 탐색
8. Search Nodes            - 노드 검색
9. Call Method             - 메서드 호출
```

#### 📡 구독 및 모니터링
```
10. Create Subscription    - 구독 생성
11. Modify Subscription    - 구독 수정
12. Delete Subscription    - 구독 삭제
13. Execute Example Script - 예제 스크립트 실행
14. Enter Monitoring Mode  - 모니터링 모드
15. Event View             - 이벤트 전용 뷰
```

## 상세 사용 가이드

### 서버 연결하기

1. **엔드포인트 확인** (메뉴 0번)
   - 서버의 보안 정책 및 인증서 정보 확인
   - 연결 가능한 엔드포인트 목록 조회

2. **새 세션 생성** (메뉴 1번)
   ```
   Enter session name/ID: my_session
   Enter server URL: opc.tcp://localhost:62541/Quickstarts/ReferenceServer
   ```

3. **세션 관리** (메뉴 3번)
   - 여러 서버에 동시 연결 가능
   - 세션 간 전환으로 효율적인 작업

### 노드 작업하기

#### 노드 정보 조회 (메뉴 4번)
```
Enter node ID: ns=5;i=1242
Get detailed attributes? (y/n): y
```
- 노드의 모든 속성 정보 표시
- 데이터 타입, 접근 권한, 설명 등 확인

#### 데이터 읽기/쓰기 (메뉴 5, 6번)
```
Enter node ID: ns=3;i=2042
Enter value type: int16
Enter value: 42
```
- 다양한 데이터 타입 지원 (int, float, bool, string 등)
- 자동 타입 변환 및 검증

#### 노드 탐색 (메뉴 7번)
```
Enter node ID to browse: i=85 (Objects)
Browse type (1=Basic, 2=Tree): 2
Enter max depth: 3
```
- 계층적 구조 탐색
- 트리 형태로 노드 구조 표시

### 구독 설정하기

#### 구독 생성 (메뉴 10번)
```
Publishing Interval (ms): 1000
Lifetime Count: 600
Max Keep-Alive Count: 20
Priority: 0
```

#### 모니터링 항목 추가
```
Select subscription: 1
Enter node ID: ns=5;i=1242
Sampling Interval (ms): 1000
```

#### 구독 수정 (메뉴 11번)
- 발행 간격, 수명 카운트 조정
- 모니터링 항목 추가/삭제
- 모니터링 모드 설정 (Disabled/Sampling/Reporting)

### 실시간 모니터링

#### 데이터 모니터링 (메뉴 14번)
- 실시간 데이터 변경 알림
- 구독 상태 모니터링
- 연결 상태 자동 확인

#### 이벤트 모니터링 (메뉴 15번)
```
이벤트 구독 설정:
1. Server 노드 - BaseEventType (기본)
2. Server 노드 - SystemEventType
3. Objects 노드 - BaseEventType
4. 사용자 정의
```
- 서버 이벤트 실시간 수신
- 이벤트 타입별 필터링
- 이벤트 발생 통계

## 고급 기능

### 메서드 호출 (메뉴 9번)
```
Enter parent node ID: ns=?;i=??
Enter method node ID: ns=?;i=??
```
- 서버 메서드 실행
- 입력/출력 인수 자동 처리
- 타입 안전성 보장

