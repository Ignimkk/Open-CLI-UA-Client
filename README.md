# OPC UA Client Python

A modular OPC UA client implementation using the asyncua library.

## 기능

- 연결 관리
- 노드 검색 및 데이터 처리
- 메서드 호출
- 구독 처리
- 이벤트 및 모니터링

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

`examples` 디렉토리에서 다양한 기능에 대한 사용 예제를 확인할 수 있습니다.

## UA Reference 서버 테스트 방법

UA Reference 서버에 대한 테스트를 실행하려면 다음 단계를 따르세요:

1. UA Reference 서버 실행:
   ```bash
   # UA Reference 서버 실행 명령어 예시
   dotnet run --project ConsoleReferenceServer.csproj --framework net9.0
   ```

2. 서버 URL 업데이트:
   ```bash
   python update_server_url.py
   ```

3. 모든 기능 테스트 실행:
   ```bash
   python run_all_tests.py
   ```

4. UA Reference 서버 특화 테스트 실행:
   ```bash
   python reference_server_specific_tests.py
   ```

## 테스트 결과 확인

테스트 결과는 `test_results_YYYYMMDD_HHMMSS.txt` 형식의 파일에 저장됩니다. 이 파일에는 각 테스트 항목의 성공/실패 여부와 발생한 오류에 대한 정보가 포함됩니다. 