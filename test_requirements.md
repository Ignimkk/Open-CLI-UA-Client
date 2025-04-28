# OPC UA 클라이언트 테스트 요구사항 체크리스트

UA Reference 서버에서 다음 기능들을 모두 테스트하고 결과를 체크리스트로 관리합니다.

## 연결(Connection)

- [ ]  Get Endpoints (서버에서 엔드포인트 가져오기)
  - 파일: `examples/connection_examples.py` - `example_get_endpoints` 함수
  - 설명: 서버에서 사용 가능한 엔드포인트 목록을 가져옵니다.

- [ ]  Session - No Security (보안 없음 정책으로 서버에 연결하기)
  - 파일: `examples/connection_examples.py` - `example_session_without_security` 함수
  - 설명: 보안 정책 없이 서버에 연결합니다.

- [ ]  Session - Activate Session (연결 후 세션 활성화)
  - 파일: `examples/connection_examples.py` - `example_activate_session` 함수
  - 설명: 서버에 연결한 후 세션을 활성화합니다.

- [ ]  Session - Close (세션 종료)
  - 파일: `examples/connection_examples.py` - 모든 예제에서 사용
  - 설명: 서버 세션을 정상적으로 종료합니다.

- [ ]  Multiple Sessions (다중 세션 만들기)
  - 파일: `examples/connection_examples.py` - `example_multiple_sessions` 함수
  - 설명: 여러 개의 서버 세션을 생성하고 관리합니다.

## 검색 및 데이터 처리

- [ ]  Browse Single Node (단일 노드 검색)
  - 파일: `examples/node_and_method_examples.py` - `example_browse_node` 함수
  - 설명: 특정 노드의 자식 노드들을 검색합니다.

- [ ]  Read Node Attribute (노드 속성 읽기)
  - 파일: `examples/node_and_method_examples.py` - `example_read_node_attribute` 함수
  - 설명: 노드의 속성 값을 읽습니다.

- [ ]  Read Array Node Attribute (서버 배열 노드 특성 읽기)
  - 파일: `examples/node_and_method_examples.py` - `example_read_array_node` 함수
  - 설명: 배열 형태의 노드 값을 읽습니다.

- [ ]  Write Node (서버 노드에 값 쓰기)
  - 파일: `examples/node_and_method_examples.py` - `example_write_node` 함수
  - 설명: 노드에 새 값을 씁니다.

## 메서드

- [ ]  Method Call Without In/Out Param (In/Out 파라미터가 없는 메소드 호출)
  - 파일: `examples/node_and_method_examples.py` - `example_call_method` 함수
  - 설명: 입력 파라미터 없이 서버 메서드를 호출합니다.

- [ ]  Method Call With In/Out Param (In/Out 파라미터가 있는 메소드 호출)
  - 파일: `examples/node_and_method_examples.py` - `example_call_method_with_params` 함수
  - 설명: 입력 파라미터를 가진 서버 메서드를 호출합니다.

## 구독

- [ ]  Empty (빈 구독 생성하기)
  - 파일: `examples/subscription_and_event_examples.py` - `example_empty_subscription` 함수
  - 설명: 빈 구독을 생성합니다.

- [ ]  Modify (기존 구독 수정하기)
  - 파일: `examples/subscription_and_event_examples.py` - `example_modify_subscription` 함수
  - 설명: 기존 구독의 속성을 수정합니다.

- [ ]  Delete (기존 구독 삭제하기)
  - 파일: `examples/subscription_and_event_examples.py` - 여러 예제에서 사용
  - 설명: 생성된 구독을 삭제합니다.

- [ ]  Set Publishing Mode (기존 구독의 게시 모드 설정)
  - 파일: `examples/subscription_and_event_examples.py` - `example_subscription_publishing_mode` 함수
  - 설명: 구독의 게시 모드를 활성화/비활성화합니다.

- [ ]  Publish Value Changes (구독 설정으로 값 변경 확인하기)
  - 파일: `examples/subscription_and_event_examples.py` - `example_data_change_subscription` 함수
  - 설명: 노드 값 변경 시 알림을 받도록 구독을 설정합니다.

- [ ]  Publish Keep Alive (연결 유지 메시지 보내기)
  - 파일: `examples/subscription_and_event_examples.py` - `example_keep_alive` 함수
  - 설명: 서버 연결을 유지하기 위한 메시지를 주기적으로 전송합니다.

- [ ]  Publish Parallel (다중 구독 생성하기)
  - 파일: `examples/subscription_and_event_examples.py` - `example_parallel_subscriptions` 함수
  - 설명: 여러 개의 구독을 동시에 생성하고 관리합니다.

## 이벤트 및 모니터링

- [ ]  Subscribe Event (객체 이벤트 구독하기)
  - 파일: `examples/subscription_and_event_examples.py` - `example_event_subscription` 함수
  - 설명: 서버에서 발생하는 이벤트를 구독합니다.

- [ ]  Add MonitoredItem (MonitoredItem 추가하기)
  - 파일: `examples/subscription_and_event_examples.py` - `example_monitored_item` 함수
  - 설명: 모니터링할 아이템을 구독에 추가합니다.

- [ ]  Modify MonitoredItem (MonitoredItem 수정하기)
  - 파일: `examples/subscription_and_event_examples.py` - `example_monitored_item` 함수
  - 설명: 모니터링 아이템의 설정을 수정합니다.

- [ ]  Delete MonitoredItem (MonitoredItem 삭제하기)
  - 파일: `examples/subscription_and_event_examples.py` - `example_monitored_item` 함수
  - 설명: 모니터링 아이템을 구독에서 제거합니다.

- [ ]  Set Monitoring Mode - Reporting (Monitor모드를 Reporting으로 설정하기)
  - 파일: `examples/subscription_and_event_examples.py` - `example_monitoring_mode` 함수
  - 설명: 모니터링 아이템의 모드를 Reporting으로 설정합니다.

## UA Reference 서버 특화 테스트

- [ ]  서버 연결 테스트
  - 파일: `reference_server_specific_tests.py`
  - 설명: UA Reference 서버에 연결합니다.

- [ ]  루트 노드 탐색
  - 파일: `reference_server_specific_tests.py`
  - 설명: 루트 노드의 자식 노드들을 탐색합니다.

- [ ]  변수 노드 읽기/쓰기
  - 파일: `reference_server_specific_tests.py`
  - 설명: UA Reference 서버의 변수 노드에 값을 읽고 씁니다.

- [ ]  메서드 호출
  - 파일: `reference_server_specific_tests.py`
  - 설명: UA Reference 서버의 메서드를 찾아 호출합니다.

- [ ]  구독 및 데이터 변경 감지
  - 파일: `reference_server_specific_tests.py`
  - 설명: UA Reference 서버의 변수 값 변경을 구독합니다. 