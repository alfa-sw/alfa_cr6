from alfa_CR6_backend.lang import error_kr
D = {
    " ?": " ?",
    "alias": "정정",
    "before dispensing. Please check can.": "조색하기 전, 캔을 확인해주세요.",
    ",\ncreating {} cans": "{} 의 신규 바코드를 생성하였습니다", 
    "CAN PRESENCE": "캔 위치 OK.",
    "Cancel": "취소",
    "Carousel OK": "전체 컨베이어 동작 OK",
    "Carousel Paused": "자동화가 멈췄습니다.",
    "Condition not valid while reading barcode:{}": "{}바코드를 읽는 중",
    "DISPENSING POSITION PHOTOCELL": "디스펜싱 위치 센서",
    "INPUT ROLLER PHOTOCELL": "투입구 롤러 센서",
    "Jar volume not sufficient for barcode:{}.\nPlease, remove it.\n": "어뎁터 사이즈를 확인해주세요",
    "LIFTER DOWN PHOTOCELL": "리프터 하강 감지 센서",
    "LIFTER ROLLER PHOTOCELL": "리프터 롤러 감지 센서",
    "LIFTER UP PHOTOCELL": "리프터 상승 감지 센서",
    "MICROSWITCH 1": "마이크로스위치 1",
    "MICROSWITCH 2": "마이크로스위치 2",
    "OUTPUT ROLLER PHOTOCELL": "배출구 롤러 감지 센서",
    "OK": " 예",
    "STEP {} +": "단계{}+",
    "STEP {} -": "단계{}-",
    "Start  input roller": "투입구 컨베이어를 구동",
    "Start dispensing roller to photocell": "디스펜싱 롤러를 센서 방향으로 가동시킵니다",
    "Start dispensing roller": "디스펜싱 롤러를 가동시킵니다",
    "Start input roller to photocell": "센서쪽으로 투입구 롤러를 가동시킵니다",
    "Start input roller": "투입구 롤러를 가동시킵니다",
    "Start lifter down": "리프터를 아래로",
    "Start lifter roller CCW": "리프터를 반시계방향으로 회전",
    "Start lifter roller CW": "리프터를 시계방향으로 회전",
    "Start lifter up": "리프터 상승",
    "Start output roller CCW to photocell dark": "관련 포토셀이 맞물릴 때까지 배출구 롤러를 가동시킵니다.",
    "Start output roller CCW to photocell light": "관련 광전지가 풀릴 때까지 출력 롤러의 움직임을 시작합니다.", 
    "Start output roller CCW": "배출구 롤러를 반시계방향으로 동작",
    "Start output roller to photocell dark": "배출구에 있는 센서로 이동", # start the movement of the output roller until the related photocell gets engaged 
    "Start output roller to photocell light": "센서에서 배출구 끝까지 이동", # start the movement of the output roller until the related photocell gets unengaged 
    "Stop  input roller": "투입구 롤러를 멈춤",
    "Stop  lifter roller": "리프터 롤러를 멈춤",
    "Stop  lifter": "리프터를 멈춤",  
    "Stop  output roller": "배출구 롤러를 멈춤",
    "Stop dispensing roller": "디스펜싱 롤러를 멈춤",
    "Too many files saved and not used. Please delete unused files.": "파일이 너무 많이 저장되었습니다. 사용하지 않는 파일을 삭제해주세요",
    "[{}] Files:  search by file name": "[{}] 파일: 파일이름으로 찾습니다",
    "[{}] Jars:   search by status": "[{}] 캔:어뎁터 상태로 찾습니다",
    "[{}] Orders: search by order nr.": "[{}] 오더넘버에 따라 배합을 확인",
    "\nRemember to check the volume.\n": "\n캔의 용량과 선택된 배합의 양을 다시 한번 확인해주세요\n",
    "\nand printing barcodes": "\n을 출력중", # and printing barcodes (it is a second part of the complete message asking to confirm the action of creating new cans and printing related label) 
    "\npigments to be added by hand after dispensing:\n{}.": "해당 조색제는 현재 기기안에 없는 것으로 확인됩니다. 추후 손으로 직접 추가해야 합니다\n{}.", # these pigments are not present in the system, so they must be added by hand by the opeator afterwhile 
    "\npigments to be refilled before dispensing:{}. ({}/3)\n": "조색하기전, \n 조색제를 충진해야 합니다 {}. ({}/3)\n", # pigment are missing in canisters, operator has to refill : 
    "\nwithout printing barcodes": "\n 바코드 출력없이 수행",
    "action 01 (head 1 or A)": "1번 모듈 동작 일람(Head 1 or A)",
    "action 02 (head 1 or A)": "1번 모듈 동작 일람(Head 1 or A)",
    "action 03 (head 3 or B)": "3번 모듈 동작 일람(Head 3 or B)",
    "action 04 (head 5, 6 or C, D)": "5번,6번 모듈 동작 일람(Head 5,6 or C,D)",
    "action 05 (head 5, 6 or C, D)": "5번,6번 모듈 동작 일람(Head 5,6 or C,D)",
    "action 06 (head 6 or D)": "6번 모듈 동작 일람(Head 6 or D)",
    "action 07 (head 4 or E)": "4번 모듈 동작 일람(Head 4 or E)",
    "action 08 (head 2 or F)": "2번 모듈 동작 일람(Head 2 or F)",
    "action 09 (head 2 or F)": "2번 모듈 동작 일람(Head 2 or F)",
    "action 10 (head 2 or F)": "2번 모듈 동작 일람(Head 2 or F)",
    "back to home page": "홈 화면으로",
    "barcode": "바코드",
    "barcode:{} has status {}.\n": "{} 바코드의 상태가 {}.\n",
    "barcode:{} not found.\nPlease, remove the can.\n": "{}바코드를 찾을 수 없습니다. \n 캔을 제거해주세요.", # the barcode reader has read a barcode not present in database, it cannot be handled 
    "carousel is paused.": "자동 작업이 멈춤.", 
    "cloned order:{} \n from:{}.": "기존에 있는 오더를 복사하였습니다",
    "confirm creating order from file (file will be deleted):\n '{}'?\n": "\n파일로부터 오더를 생성하시겠습니까?(파일은 삭제됨):\n '{}'",
    "confirm deleting file\n '{}' ?": "\n {} 파일을 삭제하시겠습니까?",
    "confirm deleting jar\n '{}' ?": "\n {} 캔을 삭제하시겠습니까?",
    "confirm deleting order '{}' and related jars?": "{} 오더를 삭제하고, 어뎁터를 제거하시겠습니까?",
    "confirm discarding changes?": "변경 사항을 취소하시겠습니까?",
    "confirm freezing carousel?": "기기를 정지 하시겠습니까?",
    "confirm printing {} barcodes?": "{}바코드를 출력하시겠습니까?",
    "confirm saving changes": "수정된 데이터로 저장하시겠습니까?",
    "confirm unfreezing carousel?": "자동 운전 상태로 전환하시겠습니까?",
    "copy": "복사",
    "created order:{}.": "{} 오더를 생성하였습니다",
    "create order": "오더를 생산하였습니다",
    "date_created:{}\n": "{}\n 데이터가 생성되었습니다",
    "delete": "삭제",
    "description:{}\n": "개요 {}\n",
    "discard changes": "변경 사항을 취소",
    "do you want to print barcode:\n {} ?": "\n {} 바코드 출력 하시겠습니까?",
    "duplicate {} in jar position list!": "{} 위치에 어뎁터가 중복되었습니다!",
    "edit": "수정",
    "edit or add item:": "항목을 수정하거나 추가",
    "file name": "파일명",
    "file_name:{}": "파일명{}",
    "hit 'OK' to unfreeze it": "재시작하려면, OK를 눌러주세요",
    "loaded:": "로딩 완료",
    "loading:": "로딩중",
    "machine_head:{}\n": "모듈 {}\n",
    "move 00 01 ('feed')": "0번에서 1번으로 어뎁터 이동",
    "move 01 02 ('IN -> A')": "1번에서 2번으로(IN->A) 어뎁터 이동",
    "move 02 03 ('A -> B')": "2번에서 3번으로(A->B) 어뎁터 이동",
    "move 02 04 ('A -> C')": "2번에서 4번으로(A->C) 어뎁터 이동",
    "move 03 04 ('B -> C')": "3번에서 4번으로(B->C) 어뎁터 이동",
    "move 04 05 ('C -> UP')": "4번에서 5번으로(C->UP) 어뎁터 이동",
    "move 04 05 ('DOWN -> D')": "4번에서 5번으로 ('리프터 하단 -> D') 어뎁터 이동",
    "move 04 05 ('UP -> DOWN')": "4번에서 5번으로 (리프터 상단 -> 리프터 하단) 어뎁터 이동 ",
    "move 05 06 ('UP -> DOWN')": "5번에서 6번으로 ('리프터 상단 -> 리프터 하단') 어뎁터 이동",
    "move 06 07 ('DOWN -> D')": "6번에서 7번으로 (리프터 하단 -> D) 어뎁터 이동",
    "move 07 08 ('D -> E')": "7번에서 8번으로 (D -> E) 어뎁터 이동",
    "move 07 09 ('D -> F')": "7번에서 9번으로 (D -> F) 어뎁터 이동",
    "move 08 09 ('E -> F')": "8번에서 9번으로 (E -> F) 어뎁터 이동",
    "move 09 10 ('F -> DOWN')": "9번에서 하단 리프터로 이동",
    "move 10 11 ('DOWN -> UP')": "하단 리프테에서 상단으로 이동",
    "move 11 12 ('UP -> OUT')": "출구로 이동(UP -> OUT)",
    "move 12 00 ('deliver')": "캔을 바깥으로 이동",
    "n. of jars\nto add:": "n. 의 캔이 추가되었습니다",
    "new": "새로운",
    "no item selected. Please, select one to clone.": "어떤 항목도 선택되지 않았습니다, 복사하려는 항목을 선택해주세요",
    "order n.:": "오더 n.",
    "pigment:": "조색제",
    "pigments to be added for barcode:\n {}": "바코드:\n {} 을 위해, 조색제가 추가되어야 합니다",
    "please, remove completed cans from output roller": "배출구에서 완료된 캔을 제거해주세요",
    "position:{}\n": "{}\n 포지션",
    "print\nbarcodes?": "\n 바코드를 프린트하시겠습니까?",
    "properties:{}\n": "{}\n 조색제 특징",
    "quantity (gr):": "양(gr)",
    "remove\nselected": "선택된 \n을 삭제합니다",
    "save changes": "변경 사항을 저장합니다",
    "sorry, this help page is missing.": "죄송합니다, 해당 페이지는 소실되었습니다",
    "start load:": "적재 시작",
    "status:{}\n": "\n의 상태 :{}",
    "test alert message": "테스트 알림 메시지",
    "{} already in progress!": "{}은 이미 진행중입니다!",
    "{} Please, Check Pipe Levels: low_level_pipes:{}": "{} 캐니스터의 조색제 잔량을 확인해주세요",
    "{} RESETTING": "{}를 리셋중",
    "{} waiting for CRX_OUTPUTS_MANAGEMENT({}, {}) execution. crx_outputs_status:{}": "CRX_OUTPUTS_MANAGEMENT을 기다려주세요",
    "{} waiting for answer to cmd:{}": "cmd로 응답 대기중입니다",
    "{} waiting for {} to get unlocked.": "{}바코드가 풀리길 기다리고있습니다",
    '   OK   ': '   OK   ', 
    ' Cancel ': ' 취소 ',
    'Missing material for barcode {}.\n please refill pigments:{} on head {}.': 
        '{}바코드에 들어가는 조색제가 부족합니다. 모듈 {}에 있는 \n 조색제를 리필해주세요. \'조색제 부족으로 바코드 {}를 생산할 수 없습니다. 모듈 {}에 있는 \n 조색제를 리필해주세요',
    'Please, insert below the number of jars.': "몇 개의 바코드를 생성하시겠습니까?",
    'barcode:{} error in STEP {}. I will retry.': "바코드 {}가 {}단계에서 에러 상태입니다. 재시도하겠습니다",
    'modified.': "변경되었습니다",
    'output roller is busy.': '배출구 롤러에 이미 어뎁터가 있습니다',
    "order nr.": "오더 넘버",
    "status": "상태",
    'timeout expired!\n{} bit_name:{}, on:{}, status_levels:{}, timeout:{}.': "시간 초과되었습니다 ! \n{} bit_name:{}, on:{}, status_levels:{}, timeout:{}",
    'timeout expired!\n{} bit_name:{}, on:{}, timeout:{}.': "시간 초과되었습니다 ! \n{} bit_name:{}, on:{}, timeout:{}.",
    'timeout expired!\n{} on:{}, status_levels:{}, timeout:{}.': "시간 초과되었습니다 ! \n{} on:{}, status_levels:{}, timeout:{}",
    'waiting for input_roller available and stopped.': "투입구 롤러가 준비될때까지 대기중입니다",
    "view": "뷰",
    'waiting for load_lifter roller available and stopped.': "적재 리프터가 준비될때까지 준비중입니다",
    'waiting for unload lifter to be free, stopped.': "언로드 리프터가 준비될때까지 준비중입니다",
    'POWER_OFF': "전원 종료",
    'INIT': "응용 프로그램 스타트중",
    'IDLE': "응용 프로그램이 로딩중",
    'RESET': '리셋',
    'STANDBY': '준비 상태',
    'DISPENSING': '디스펜싱',
    'ALARM': '확인 필요',
    'DIAGNOSTIC': '진단 모드로',
    'POSITIONING': '어뎁터 이동중',
    'JUMP_TO_BOOT': '부팅을 넘김',
    'ROTATING': "턴 테이블 회전중",
    'AUTOTEST': "자동테스트",
    'JAR_POSITIONING': "어뎁터가 이동중",
    'NEW': '새로운',
    'PROGRESS': '진행중',
    'ERR': '에러',
    'ERROR': '에러',
    'DONE': '완료됨',
    'PARTIAL': '부분완료',
}


D.update(error_kr.D)
