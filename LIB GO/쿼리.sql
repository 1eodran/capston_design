-- 사용자 --
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,  -- 디비에서 관리되는 순차적인 ID
    username VARCHAR(50) NOT NULL,              -- 이름
    id VARCHAR(50) NOT NULL UNIQUE,   -- 아이디 (중복 불가)
    password VARCHAR(50) NOT NULL,         -- 비밀번호
    age INT NOT NULL,                       -- 나이
    email VARCHAR(50) NOT NULL UNIQUE      -- 이메일 (중복 불가)
);


-- 도서관 --

CREATE TABLE libraries (
    library_id INT AUTO_INCREMENT PRIMARY KEY,  -- 도서관 고유 ID
    library_name VARCHAR(100) NOT NULL UNIQUE   -- 도서관 이름
);

-- 초기 데이터 삽입
INSERT INTO libraries (library_name) VALUES
    ("국립창원대도서관"), ("경남대표도서관"), ("상남도서관"), ("성산도서관"), 
    ("진해도서관"), ("진해기적의도서관"), ("동부도서관"), ("마산회원도서관"), 
    ("최윤덕도서관"), ("내서도서관"), ("고향의봄도서관"), ("중리초등복합시설도서관"), 
    ("명곡도서관"), ("마산합포도서관"), ("창원중앙도서관");


UPDATE library_total_points
SET total_points = total_points + 5000
WHERE library_id = 3;

SELECT *
FROM libraries
SELECT *
FROM library_total_points
SELECT *
FROM user_library_points
SELECT *
FROM user_record
SELECT * 
FROM users

DELETE FROM user_record
WHERE record_id IN ('71','72');

DELETE FROM users
WHERE id IN ('user6');

DELETE FROM library_total_points;


-- 사용자 독서기록(도서관별) --
CREATE TABLE user_record (
    record_id INT AUTO_INCREMENT PRIMARY KEY,    -- 고유 기록 ID
    user_id INT NOT NULL,                        -- 사용자 ID (users 테이블 참조)
    library_id INT NOT NULL,                     -- 도서관 ID (libraries 테이블 참조)
    isbn VARCHAR(13) NOT NULL,                   -- 읽은 책 ISBN
    highlight TEXT,                              -- 인상깊은 글귀
    memo TEXT,                                   -- 메모
    likes INT DEFAULT 0,                         -- 좋아요 수
    visit_date DATETIME DEFAULT CURRENT_TIMESTAMP, -- 방문 날짜/시간
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (library_id) REFERENCES libraries(library_id) ON DELETE CASCADE
);

TRUNCATE TABLE your_table;

SET FOREIGN_KEY_CHECKS = 0;  -- 외래 키 제약 조건 비활성화
TRUNCATE TABLE user_record; -- 테이블 데이터 삭제 및 AUTO_INCREMENT 초기화
SET FOREIGN_KEY_CHECKS = 1;  -- 외래 키 제약 조건 다시 활성화

SET FOREIGN_KEY_CHECKS = 0;  -- 외래 키 제약 조건 비활성화
TRUNCATE TABLE user_library_points; -- 테이블 데이터 삭제 및 AUTO_INCREMENT 초기화
SET FOREIGN_KEY_CHECKS = 1;  -- 외래 키 제약 조건 다시 활성화

SET FOREIGN_KEY_CHECKS = 0;  -- 외래 키 제약 조건 비활성화
TRUNCATE TABLE order_details; -- 테이블 데이터 삭제 및 AUTO_INCREMENT 초기화
SET FOREIGN_KEY_CHECKS = 1;  -- 외래 키 제약 조건 다시 활성화


SELECT *
FROM user_library_points

-- 사용자  point --
CREATE TABLE user_library_points (
    point_id INT AUTO_INCREMENT PRIMARY KEY,  -- 고유 포인트 ID
    user_id INT NOT NULL,                     -- 사용자 ID (users 테이블 참조)
    library_id INT NOT NULL,                  -- 도서관 ID (libraries 테이블 참조)
    visit_count INT DEFAULT 0,                -- 방문 횟수
    record_count INT DEFAULT 0,               -- 독서 기록 횟수
    like_count INT DEFAULT 0,                 -- 좋아요 수
    total_points INT AS (visit_count * 100 + record_count * 10 + like_count * 3) STORED, -- 총 포인트
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (library_id) REFERENCES libraries(library_id) ON DELETE CASCADE
);

CREATE TABLE library_total_points (
    library_id INT PRIMARY KEY,       -- 도서관 ID (libraries 테이블 참조)
    total_points INT DEFAULT 0,       -- 해당 도서관의 총 포인트
    FOREIGN KEY (library_id) REFERENCES libraries(library_id) ON DELETE CASCADE
);

SELECT *
FROM library_total_points

INSERT INTO library_total_points (library_id, total_points)
SELECT library_id, 0
FROM libraries;






-- 도서관별 총 포인트 계산 및 삽입
INSERT INTO library_total_points (library_id, total_points)
SELECT 
    library_id,
    SUM(total_points) AS total_points
FROM user_library_points
GROUP BY library_id
ON DUPLICATE KEY UPDATE total_points = VALUES(total_points);



-- 1레벨: 0 ~ 999 포인트
-- 2레벨: 1000 ~ 2999 포인트
-- 3레벨: 3000 ~ 5999 포인트
-- 4레벨: 6000 ~ 9999 포인트
-- 5레벨: 10000 포인트 이상

ALTER TABLE library_total_points
ADD COLUMN level INT AS (
    CASE 
        WHEN total_points < 1000 THEN 1
        WHEN total_points < 3000 THEN 2
        WHEN total_points < 6000 THEN 3
        WHEN total_points < 10000 THEN 4
        ELSE 5
    END
) STORED;


-- Python/Flask에서 레벨 계산
-- 레벨 계산 함수를 조정합니다:
def calculate_library_level(total_points):
    if total_points < 1000:
        return 1
    elif total_points < 3000:
        return 2
    elif total_points < 6000:
        return 3
    elif total_points < 10000:
        return 4
    else:
        return 5

-- 이 함수를 사용해 데이터베이스에 레벨을 업데이트합니다:
def update_library_levels():
    libraries = library_total_points.query.all()
    for library in libraries:
        library.level = calculate_library_level(library.total_points)
    db.session.commit()



-----------------------
CREATE TABLE likes_record (
    like_id INT AUTO_INCREMENT PRIMARY KEY,  -- 고유 ID
    user_id INT NOT NULL,                    -- 사용자 ID (users 테이블 참조)
    record_id INT NOT NULL,                  -- 공감한 기록 ID (user_record 테이블 참조)
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (record_id) REFERENCES user_record(record_id) ON DELETE CASCADE,
    UNIQUE (user_id, record_id)              -- 중복 방지: 같은 사용자가 같은 기록에 공감 못함
);






-- 주문 테이블 생성
CREATE TABLE orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY, -- 주문 고유 ID
    user_id INT NOT NULL,                    -- 사용자 ID
    address VARCHAR(255) NOT NULL,           -- 배송 주소
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP -- 주문 생성 시간
);




DROP TABLE IF EXISTS orders;

CREATE TABLE order_details (
    order_details_id INT AUTO_INCREMENT PRIMARY KEY,  -- 주문 상세 ID
    order_id INT NOT NULL,                            -- 주문 ID (외래키)
    book_title VARCHAR(255) NOT NULL,                -- 책 제목
    author VARCHAR(255),                              -- 저자
    library VARCHAR(255),                             -- 소장 도서관
    image_url VARCHAR(255),                           -- 이미지 URL
    loan_status VARCHAR(50) DEFAULT '배송중',        -- 대출 상태 (대출중, 배달중, 수거중, 반납완료)
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);



SELECT *
FROM orders;

SELECT *
FROM order_details;




-- 방문횟수 업데이트 :  user_library_points.visit_count를 user_record에서 날짜별로 계산하여 업데이트합니다.
INSERT INTO user_library_points (user_id, library_id, visit_count, record_count, like_count)
SELECT 
    ur.user_id,
    ur.library_id,
    COUNT(DISTINCT DATE(ur.visit_date)) AS visit_count,
    0 AS record_count,
    0 AS like_count
FROM user_record ur
GROUP BY ur.user_id, ur.library_id
ON DUPLICATE KEY UPDATE
    visit_count = VALUES(visit_count);
    

-- 독서 기록 횟수 업데이트 : user_library_points.record_count는 user_record에서 사용자의 독서 기록 횟수를 계산하여 업데이트합니다.
UPDATE user_library_points ulp
SET record_count = (
    SELECT COUNT(*)
    FROM user_record ur
    WHERE ur.user_id = ulp.user_id
      AND ur.library_id = ulp.library_id
);

-- 좋아요 수 업데이트 : user_library_points.like_count는 user_record에서 사용자의 좋아요 수를 합산하여 업데이트합니다.
UPDATE user_library_points ulp
SET like_count = (
    SELECT SUM(ur.likes)
    FROM user_record ur
    WHERE ur.user_id = ulp.user_id
      AND ur.library_id = ulp.library_id
);

-- 전체 포인트 계산
-- total_points는 user_library_points 테이블의 계산된 값으로 자동 업데이트됩니다(AS 절로 정의된 계산된 열).


-- 방문 횟수 확인 로직 (pythonflask)
from datetime import date
from sqlalchemy import func

# 특정 도서관의 방문 횟수 계산
def update_visit_counts():
    visit_counts = (
        db.session.query(
            user_record.c.user_id,
            user_record.c.library_id,
            func.count(func.distinct(func.date(user_record.c.visit_date))).label("visit_count")
        )
        .group_by(user_record.c.user_id, user_record.c.library_id)
    )
    
    for user_id, library_id, visit_count in visit_counts:
        point_entry = user_library_points.query.filter_by(user_id=user_id, library_id=library_id).first()
        if point_entry:
            point_entry.visit_count = visit_count
        else:
            new_entry = user_library_points(
                user_id=user_id,
                library_id=library_id,
                visit_count=visit_count,
                record_count=0,
                like_count=0
            )
            db.session.add(new_entry)
    db.session.commit()

-- 도서관별 순위 : user_library_points.total_points를 기준으로 정렬하여 특정 도서관의 사용자 순위를 출력합니다.
SELECT u.username, ulp.total_points
FROM user_library_points ulp
JOIN users u ON ulp.user_id = u.user_id
WHERE ulp.library_id = 1 -- 특정 도서관
ORDER BY ulp.total_points DESC;






