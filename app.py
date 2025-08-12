from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc
from sqlalchemy.sql import func
from PIL import Image
import base64
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import requests
from flask_cors import CORS
import pytesseract
import difflib
import re
from datetime import datetime
import os
import sqlite3
from geopy.distance import geodesic

#웹크롤링 chrome driver
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time

from webdriver_manager.chrome import ChromeDriverManager


app = Flask(__name__)
CORS(app)

#### ORM(SQLAlchemy) 설정
# SQLAlchemy 데이터베이스 설정
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:0987@127.0.0.1:3306/libgo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLAlchemy 초기화
db = SQLAlchemy(app)

# 데이터 모델
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # AUTO_INCREMENT ID
    username = db.Column(db.String(50), nullable=False)  # 이름
    id = db.Column(db.String(50), unique=True, nullable=False)  # 아이디
    password = db.Column(db.String(50), nullable=False)  # 비밀번호
    age = db.Column(db.Integer, nullable=False)  # 나이
    email = db.Column(db.String(50), unique=True, nullable=False)  # 이메일

class Library(db.Model):
    __tablename__ = 'libraries'
    library_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 도서관 고유 ID
    library_name = db.Column(db.String(100), nullable=False, unique=True)  # 도서관 이름

class UserRecord(db.Model):
    __tablename__ = 'user_record'
    record_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 고유 기록 ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete="CASCADE"), nullable=False)  # 사용자 ID (참조)
    library_id = db.Column(db.Integer, db.ForeignKey('libraries.library_id', ondelete="CASCADE"), nullable=False)  # 도서관 ID (참조)
    isbn = db.Column(db.String(13), nullable=False)  # 읽은 책 ISBN
    highlight = db.Column(db.Text, nullable=True)  # 인상 깊은 글귀
    memo = db.Column(db.Text, nullable=True)  # 메모
    likes = db.Column(db.Integer, default=0)  # 좋아요 수
    visit_date = db.Column(db.DateTime, default=db.func.now())  # 방문 날짜/시간
    
    def to_dict(self):
    #객체의 모든 속성을 딕셔너리로 변환합니다.
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "library_id": self.library_id,
            "isbn": self.isbn,
            "highlight": self.highlight,
            "memo": self.memo,
            "likes": self.likes,
            "visit_date": self.visit_date.isoformat() if self.visit_date else None
        }

class UserLibraryPoints(db.Model):
    __tablename__ = 'user_library_points'
    point_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete="CASCADE"), nullable=False)
    library_id = db.Column(db.Integer, db.ForeignKey('libraries.library_id', ondelete="CASCADE"), nullable=False)
    visit_count = db.Column(db.Integer, default=0)
    record_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)
    
     # MySQL 계산된 열 (읽기 전용)
    total_points = db.column_property(
        visit_count * 100 + record_count * 10 + like_count * 3
    )

class LikesRecord(db.Model):
    __tablename__ = 'likes_record'
    like_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 고유 ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete="CASCADE"), nullable=False)  # 사용자 ID
    record_id = db.Column(db.Integer, db.ForeignKey('user_record.record_id', ondelete="CASCADE"), nullable=False)  # 공감한 기록 ID
    
    # 중복 방지를 위한 Unique Constraint 설정
    __table_args__ = (db.UniqueConstraint('user_id', 'record_id', name='unique_user_record_like'),)

    def to_dict(self):
        #객체를 딕셔너리로 변환합니다. 필요에 따라 커스터마이징 가능.
        
        return {
            "like_id": self.like_id,
            "user_id": self.user_id,
            "record_id": self.record_id
        }
    
class LibraryTotalPoints(db.Model):
    __tablename__ = 'library_total_points'
    library_id = db.Column(db.Integer, primary_key=True)
    total_points = db.Column(db.Integer, default=0)
    db.ForeignKeyConstraint(['library_id'], ['libraries.library_id'], ondelete='CASCADE')

# 주문 및 결제 관련 테이블 모델 추가
class Order(db.Model):
    __tablename__ = 'orders'
    order_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 주문 ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)  # 사용자 ID
    address = db.Column(db.String(255), nullable=False)  # 배송 주소
    created_at = db.Column(db.DateTime, default=db.func.now())  # 주문 생성 시간

class OrderDetails(db.Model):
    __tablename__ = 'order_details'
    order_details_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 주문 상세 ID
    order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id', ondelete='CASCADE'), nullable=False)  # 주문 ID 참조
    book_title = db.Column(db.String(255), nullable=False)  # 책 제목
    author = db.Column(db.String(255))  # 저자
    library = db.Column(db.String(255))  # 소장 도서관
    image_url = db.Column(db.String(255))  # 이미지 URL
    loan_status = db.Column(db.String(50), default="배송중")  # 대출 상태 (대출중, 배달중, 수거중, 반납완료)

# 데이터베이스 테이블 생성
with app.app_context():
    db.create_all()


#### ISBN 13자리 추출 -> 네이버 도서 API     
NAVER_CLIENT_ID = 'd7DlZNovTgPbb0lkS_RU'
NAVER_CLIENT_SECRET = 'WEe8ii5Jqg'

# ISBN 인식 및 책 정보 조회 함수
def get_book_info(isbn):
    url = "https://openapi.naver.com/v1/search/book.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": isbn}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        items = response.json().get("items")
        if items:
            data = items[0]
            return {
                "title": data.get("title"),
                "link": data.get("link"),
                "image": data.get("image"),
                "author": data.get("author"),
                "publisher": data.get("publisher"),
                "isbn": data.get("isbn"),
            }
    else:
        print(f"네이버 API 요청 실패: {response.status_code}")
    return None

# 바코드 인식 함수
def extract_isbn_from_image(image):
    barcodes = decode(image)
    for barcode in barcodes:
        barcode_data = barcode.data.decode('utf-8')
        barcode_type = barcode.type
        if barcode_type == 'EAN13' and len(barcode_data) == 13:
            return barcode_data
    return None

@app.route('/scan-barcode', methods=['POST'])
def scan_barcode():
    # 업로드된 이미지 파일 처리
    data = request.get_json()
    image_data = data.get('image')
    if not image_data:
        return jsonify({"error": "이미지가 제공되지 않았습니다."}), 400

    # Base64 이미지를 OpenCV로 디코딩
    image_data = image_data.split(",")[1]
    npimg = np.frombuffer(base64.b64decode(image_data), np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    # --- 캡처된 이미지 저장 --- 
    capture_path = "captured_barcode_image.jpg"
    cv2.imwrite(capture_path, img)
    print(f"이미지 저장 완료: {capture_path}")

    # ISBN 추출
    isbn = extract_isbn_from_image(img)
    print("인식된 ISBN:", isbn)  # 디버깅용 출력
    if isbn:
        book_info = get_book_info(isbn)
        print("네이버 API 응답:", book_info)  # 디버깅용 출력
        if book_info:
            # 책 정보를 HTML로 렌더링
            rendered_html = render_template('bookInfo.html', book_info=book_info)
            return jsonify({"book_info": book_info, "html": rendered_html})
        else:
            return jsonify({"error": "책 정보를 찾을 수 없습니다."}), 404
    else:
        return jsonify({"error": "ISBN을 인식하지 못했습니다."}), 400

# ISBN 직접 입력 라우트
@app.route('/submit-isbn', methods=['POST'])
def submit_isbn():
    isbn = request.form.get("isbn")
    if not isbn:
        return render_template("insertisbn.html", error="ISBN을 입력해주세요.")

    # ISBN으로 책 정보 조회
    book_info = get_book_info(isbn)
    if book_info:
        return render_template("bookInfo.html", book_info=book_info)
    else:
        return render_template("insertbookinfo.html", error="책 정보를 찾을 수 없습니다.\n도서 정보를 입력해주세요.")



#### Tesseract ocr - 도서관 이름 스캔
# Tesseract 설치 경로 설정
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 도서관 이름 리스트
library_names = [
    "국립창원대도서관", "경남대표도서관", "상남도서관", "성산도서관",
    "진해도서관", "진해기적의도서관", "동부도서관", "마산회원도서관", "최윤덕도서관",
    "내서도서관", "고향의봄도서관", "중리초등복합시설도서관", "명곡도서관", "마산합포도서관",
    "창원중앙도서관", "의창도서관", "창원시립도서관"
]

# 텍스트 정규화 함수
def normalize_text(text):
    text = re.sub(r'[^가-힣\s]', '', text)
    return text.replace(" ", "").strip()

# 유사한 도서관 이름 찾기 함수
def find_closest_library_name(normalized_text, threshold=0.6):
    closest_match = None
    highest_similarity = 0
    for name in library_names:
        similarity = difflib.SequenceMatcher(None, normalized_text, name).ratio()
        if similarity > highest_similarity and similarity >= threshold:
            highest_similarity = similarity
            closest_match = name
    return closest_match

# 이미지 전처리 함수
def preprocess_image(image):
    # 노이즈 제거 및 블러링
    blurred = cv2.bilateralFilter(image, d=9, sigmaColor=75, sigmaSpace=75)
    # 그레이스케일 변환
    gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
    # 이진화 (Thresholding)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


# 도서관 이름 추출 함수
def extract_library_name(image):
    # 이미지 전처리
    processed_image = preprocess_image(image)
    # 전처리된 이미지를 PIL 이미지로 변환
    pil_img = Image.fromarray(processed_image)
    # OCR로 텍스트 추출 (한국어 인식)
    text = pytesseract.image_to_string(pil_img, lang='kor', config='--psm 6')
    print(f"인식된 텍스트: {text}")
    
    # 텍스트 정규화
    normalized_text = normalize_text(text)
    print(f"정규화된 텍스트: {normalized_text}")
    
    # 유사한 도서관 이름 찾기
    detected_library = find_closest_library_name(normalized_text)
    
    if detected_library:
        print(f"인식된 도서관 이름: {detected_library}")
        return detected_library
    else:
        print("도서관 이름을 인식할 수 없습니다.")
        return None


@app.route('/scan-library', methods=['POST'])
def scan_library():
    # 클라이언트에서 전송된 데이터 확인
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"error": "이미지가 전송되지 않았습니다."}), 400

    try:
        # Base64 이미지를 디코딩하여 OpenCV 이미지로 변환
        base64_string = data['image'].split(',')[1]
        image_data = np.frombuffer(base64.b64decode(base64_string), np.uint8)
        image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)

        # --- 디버깅: 캡처된 이미지를 서버에 저장 ---
        cv2.imwrite("captured_image.jpg", image)  # 캡처된 이미지를 저장하여 확인
        print("이미지 저장 완료: captured_image.jpg")

        # 도서관 이름 추출
        library_name = extract_library_name(image)
        if library_name=="의창도서관" or library_name=="창원시립도서관":
            library_name="창원중앙도서관"
        if library_name:
            return jsonify({"library_name": library_name}), 200
        else:
            return jsonify({"error": "도서관 이름을 인식하지 못했습니다."}), 400

    except Exception as e:
        print(f"도서관 이름 추출 중 오류 발생: {str(e)}")
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500


#### 도서관 혼잡도, 방문 유저 채크인
# 도서관 위치 데이터
libraries = [
    {"position": {"lat": 35.2460769, "lng": 128.6910017}, "content": "국립창원대도서관"},
    {"position": {"lat": 35.249278, "lng": 128.682592}, "content": "경남대표도서관"},
    {"position": {"lat": 35.2138254, "lng": 128.6953575}, "content": "상남도서관"},
    {"position": {"lat": 35.2021394, "lng": 128.7077471}, "content": "성산도서관"},
    {"position": {"lat": 35.2334942, "lng": 128.6790201}, "content": "창원중앙도서관"},
    {"position": {"lat": 35.1524669, "lng": 128.6675415}, "content": "진해도서관"},
    {"position": {"lat": 35.1561894, "lng": 128.7063156}, "content": "진해기적의도서관"},
    {"position": {"lat": 35.1000314, "lng": 128.8171678}, "content": "동부도서관"},
    {"position": {"lat": 35.2246279, "lng": 128.573569}, "content": "최윤덕도서관"},
    {"position": {"lat": 35.2327253, "lng": 128.5012807}, "content": "내서도서관"},
    {"position": {"lat": 35.3227295, "lng": 128.5798893}, "content": "최윤덕도서관"},
    {"position": {"lat": 35.2566599, "lng": 128.6184846}, "content": "고향의봄도서관"},
    {"position": {"lat": 35.2556674, "lng": 128.5202443}, "content": "중리초등복합시설도서관"},
    {"position": {"lat": 35.25321, "lng": 128.6484426}, "content": "명곡도서관"},
    {"position": {"lat": 35.183104, "lng": 128.5628597}, "content": "마산합포도서관"}
]

# 사용자 위치 데이터 (user_id와 함께 관리)
user_locations = {}

@app.route('/check-congestion', methods=['POST'])
def check_congestion():
    data = request.get_json()
    user_lat = data.get('lat')
    user_lng = data.get('lng')
    user_id = data.get('user_id')  # 고유 사용자 ID
    library_name = data.get('library_name')  # 필터링할 도서관 이름

    if not user_lat or not user_lng or not user_id:
        return jsonify({"error": "위치 정보와 사용자 ID가 제공되지 않았습니다."}), 400

    # 사용자 위치 업데이트
    user_locations[user_id] = {"lat": user_lat, "lng": user_lng}

    # 특정 도서관 혼잡도 계산
    congestion_data = []

    for library in libraries:
        if library_name and library['content'] != library_name:
            continue  # 필터링된 도서관이 아닌 경우 건너뛰기

        library_location = (library['position']['lat'], library['position']['lng'])
        nearby_users = 0

        # 도서관 범위 안에 있는 사용자 수 계산
        to_remove = []
        for uid, user_location in user_locations.items():
            distance = geodesic((user_location['lat'], user_location['lng']), library_location).meters
            if distance <= 100:
                nearby_users += 1
            else:
                to_remove.append(uid)  # 범위를 벗어난 사용자 추적

        # 범위를 벗어난 사용자 제거
        for uid in to_remove:
            del user_locations[uid]

        # 혼잡도 수준 결정
        if nearby_users > 50:
            congestion_level = "높음"
        elif nearby_users > 25:
            congestion_level = "보통"
        elif nearby_users >= 0:
            congestion_level = "쾌적"
        

        congestion_data.append({
            "name": library['content'],
            "nearby_users": nearby_users,
            "congestion_level": congestion_level
        })

    return jsonify(congestion_data)

# 도서관 방문시 포인트(위치기반)
@app.route('/check_visit', methods=['POST'])
def check_visit():
    data = request.get_json()
    user_id = data.get('user_id')
    library_id = data.get('library_id')

    if not user_id or not library_id:
        return jsonify({"error": "user_id와 library_id는 필수입니다."}), 400

    try:
        # 포인트 레코드 조회 또는 생성
        points_record = UserLibraryPoints.query.filter_by(user_id=user_id, library_id=library_id).first()
        is_new_record = False

        if not points_record:
            # 새 사용자 포인트 레코드 생성 (방문 카운트는 여기서 증가하지 않음)
            points_record = UserLibraryPoints(
                user_id=user_id,
                library_id=library_id,
                visit_count=1, #첫 방문 시 바로 1로
                record_count=0,
                like_count=0,
            )
            db.session.add(points_record)
            db.session.commit()  # 먼저 커밋하여 초기 상태 저장
            is_new_record = True

        # 오늘 날짜 확인
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # 오늘 해당 도서관에 이미 방문했는지 확인
        visit_record = UserRecord.query.filter(
            UserRecord.user_id == user_id,
            UserRecord.library_id == library_id,
            UserRecord.visit_date.between(today_start, today_end)
        ).first()

        # 오늘 이미 방문한 경우 포인트 업데이트 중단 (204 상태 반환)
        if visit_record:
            return '', 204

        # 새로운 방문 기록 추가
        new_visit = UserRecord(
            user_id=user_id,
            library_id=library_id,
            isbn="",
            highlight="",
            memo="도서관 방문 기록"
        )
        db.session.add(new_visit)

        # 포인트 업데이트: 기존 레코드일 때만 포인트 증가
        if not is_new_record:
            points_record.visit_count += 1

        # 최종 커밋
        db.session.commit()

        # 사용자 이름과 도서관 이름 가져오기
        user = User.query.filter_by(user_id=user_id).first()
        library = Library.query.filter_by(library_id=library_id).first()

        return jsonify({
            "message": f"{user.username} 사용자 {library.library_name} 방문 +100 points",
            "visit_count": points_record.visit_count,
            "total_points": points_record.total_points
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error occurred: {e}")
        return jsonify({"error": "방문 확인 중 오류가 발생했습니다."}), 500


#### 회원가입, 로그인 데이터처리
# 회원가입 데이터 처리 라우트
@app.route('/join_done', methods=['POST'])
def join_done():
    data = request.get_json()  # JSON 데이터 받기
    username = data.get('username')  # 이름
    user_id = data.get('id')  # 아이디
    password = data.get('password')  # 비밀번호
    age = data.get('age')  # 나이
    email = data.get('email')  # 이메일

    # 데이터 검증
    if not username or not user_id or not password or not age or not email:
        return jsonify({"error": "모든 필드를 입력해야 합니다."}), 400

    try:
        # 사용자 데이터 추가
        new_user = User(username=username, id=user_id, password=password, age=age, email=email)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "회원가입이 완료되었습니다."}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error occurred: {e}")
        return jsonify({"error": "회원가입에 실패했습니다."}), 500

# 로그인 처리
@app.route('/login_action', methods=['POST'])
def login_action():
    data = request.get_json()
    id = data.get('id')
    password = data.get('password')
    user_id = User.query.filter_by(id=id).first()

    print(data)  # 요청 데이터 확인
    
    # 입력값 검증
    if not id or not password:
        return jsonify({"error": "아이디와 비밀번호를 모두 입력하세요."}), 400

    try:
        # 데이터베이스에서 사용자 조회
        user = User.query.filter_by(id=id).first()
        if user and user.password == password:
            return jsonify({"message": "로그인 성공!","id": id, "user_id":user_id.user_id, "token": "example_token"}), 200
        else:
            return jsonify({"error": "아이디 또는 비밀번호가 잘못되었습니다."}), 401
    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500

# 사용자 아이디 중복 확인
@app.route('/check_id_duplicate', methods=['POST'])
def check_id_duplicate():
    data = request.get_json()
    user_id = data.get('id')

    if not user_id:
        return jsonify({"error": "아이디를 입력해주세요."}), 400

    # 데이터베이스에서 해당 아이디가 존재하는지 확인
    user = User.query.filter_by(id=user_id).first()
    if user:
        return jsonify({"is_duplicate": True, "message": "이미 사용 중인 아이디입니다."}), 200
    else:
        return jsonify({"is_duplicate": False, "message": "사용 가능한 아이디입니다."}), 200


#### 독서기록 및 게시판 - contentwrite.html, board.html
# 사용자가 제출한 책 정보를 처리, 다음 페이지로 데이터를 전달
@app.route('/submit-bookinfo', methods=['POST'])
def submit_bookinfo():
    # POST 요청으로 전달된 데이터 받기
    isbn = request.form.get('isbn')
    title = request.form.get('title')
    author = request.form.get('author')
    publisher = request.form.get('publisher')

    # 데이터 확인 (디버그용 출력)
    print(f"ISBN: {isbn}")
    print(f"Title: {title}")
    print(f"Author: {author}")
    print(f"Publisher: {publisher}")

    # contentwrite.html로 데이터 전달
    return render_template('contentwrite.html', isbn=isbn, title=title, author=author, publisher=publisher)

# 책 정보와 이미지를 포함한 데이터를 받고 contentwrite.html로 전달
@app.route('/contentwrite', methods=['POST'])
def contentwrite():
    title = request.form.get('title')
    author = request.form.get('author')
    publisher = request.form.get('publisher')
    image = request.form.get('image')
    link = request.form.get('link')
    isbn = request.form.get('isbn')
    
    return render_template('contentwrite.html', title=title, author=author, publisher=publisher, image=image, link=link, isbn=isbn)
 
# 사용자 독서 기록 추가
@app.route('/user_records', methods=['POST'])
def add_user_record():
    data = request.get_json()
    if not data:
        return jsonify({"error": "요청 데이터가 비어 있습니다."}), 400
    print(data)  # 요청 데이터를 확인
    
    user_id = data.get('user_id')
    library_id = data.get('library_id')
    isbn = data.get('isbn')
    highlight = data.get('highlight', '')
    memo = data.get('memo', '')

    try:
        new_record = UserRecord(
            user_id=user_id,  
            library_id=library_id,
            isbn=isbn,
            highlight=highlight,
            memo=memo
        )
        db.session.add(new_record)
        db.session.commit()
        
        # 새로 추가된 기록의 record_id 반환
        most_recent_record = UserRecord.query.order_by(desc(UserRecord.visit_date)).first()
        if not most_recent_record:
            return jsonify({"error": "기록이 존재하지 않습니다."}), 404

        return jsonify({
            "message": "독서 기록이 성공적으로 추가되었습니다.",
            "record_id": most_recent_record.record_id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error occurred: {e}")
        return jsonify({"error": "독서 기록 추가에 실패했습니다."}), 500

# 독서 기록 목록 추출
@app.route('/board')
def board():
    
    # user_id 가져오기
    user_id = request.args.get('user_id')  # URL에서 user_id 가져오기
    print('user_id:'+user_id)
    if not user_id:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    # user_id로 user_record 테이블에서 해당 데이터 가져오기
    records = UserRecord.query.filter_by(user_id=user_id).all()
    records_data = [record.to_dict() for record in records]

    
    # 책 정보를 담을 리스트
    records_bookinfos_data = []

    # records_data를 순회하며 ISBN으로 책 정보 조회
    for record in records_data:
        isbn = record.get("isbn")
        
        if isbn:
            book_info = get_book_info(isbn)  # 네이버 API 호출
            if book_info:
                # 기존 기록 데이터와 책 정보를 병합하여 리스트에 추가
                record_with_info = {**record, **book_info}
                records_bookinfos_data.append(record_with_info)

            # user 테이블에서 user_id에 해당하는 사용자 정보 가져오기
    user = User.query.filter_by(user_id=user_id).first()
    id_from_user_table = user.id if user else None  # 사용자 아이디 가져오기
    
    # 결과를 HTML로 렌더링
    return render_template('board.html', records_bookinfos_data=records_bookinfos_data, id=id_from_user_table)


#### 독서기록 상세조회 및 수정
# 특정 독서 기록 상세 조회 - 10,11 나중에 통합
@app.route('/boardcontent10', methods=['GET'])
def board_content():
    # 쿼리 파라미터에서 record_id 가져오기
    record_id = request.args.get('record_id')  # GET 요청에서는 request.args 사용

    if not record_id:
        return jsonify({"error": "record_id가 제공되지 않았습니다."}), 400

    # record_id로 user_record에서 데이터 가져오기
    record = UserRecord.query.filter_by(record_id=record_id).first()
    if not record:
        return jsonify({"error": "해당 record_id에 대한 데이터를 찾을 수 없습니다."}), 404

        # ISBN으로 책 정보 조회
    book_info = get_book_info(record.isbn)
    if not book_info:
        return jsonify({"error": "해당 ISBN에 대한 책 정보를 찾을 수 없습니다."}), 404

    # record와 책 정보를 병합
    record_with_info = {
        **record.to_dict(),  # 기존 record 정보를 딕셔너리로 변환
        **book_info          # 책 정보 추가
    }

    # 결과를 HTML로 렌더링
    return render_template('boardcontent10.html', record=record_with_info)

@app.route('/boardcontent11', methods=['GET'])
def board_content11():
    # 쿼리 파라미터에서 record_id 가져오기
    record_id = request.args.get('record_id')  # GET 요청에서는 request.args 사용

    if not record_id:
        return jsonify({"error": "record_id가 제공되지 않았습니다."}), 400

    # record_id로 user_record에서 데이터 가져오기
    record = UserRecord.query.filter_by(record_id=record_id).first()
    if not record:
        return jsonify({"error": "해당 record_id에 대한 데이터를 찾을 수 없습니다."}), 404

        # ISBN으로 책 정보 조회
    book_info = get_book_info(record.isbn)
    if not book_info:
        return jsonify({"error": "해당 ISBN에 대한 책 정보를 찾을 수 없습니다."}), 404

    # record와 책 정보를 병합
    record_with_info = {
        **record.to_dict(),  # 기존 record 정보를 딕셔너리로 변환
        **book_info          # 책 정보 추가
    }

    # 결과를 HTML로 렌더링
    return render_template('boardcontent11.html', record=record_with_info)

# 독서기록 수정 페이지
@app.route('/boardupdate10')
def board_update():
    # 쿼리 파라미터에서 record_id 가져오기
    record_id = request.args.get('record_id')  # GET 요청에서는 request.args 사용

    if not record_id:
        return jsonify({"error": "record_id가 제공되지 않았습니다."}), 400

    # record_id로 user_record에서 데이터 가져오기
    record = UserRecord.query.filter_by(record_id=record_id).first()
    if not record:
        return jsonify({"error": "해당 record_id에 대한 데이터를 찾을 수 없습니다."}), 404

        # ISBN으로 책 정보 조회
    book_info = get_book_info(record.isbn)
    if not book_info:
        return jsonify({"error": "해당 ISBN에 대한 책 정보를 찾을 수 없습니다."}), 404

    # record와 책 정보를 병합
    record_with_info = {
        **record.to_dict(),  # 기존 record 정보를 딕셔너리로 변환
        **book_info          # 책 정보 추가
    }

    # 결과를 HTML로 렌더링
    return render_template('boardupdate10.html', record=record_with_info)

# 독서기록 수정한거 업데이트
@app.route('/update_record/<int:record_id>', methods=['POST'])
def update_record(record_id):
    data = request.get_json()
    highlight = data.get('highlight')
    memo = data.get('memo')

    record = UserRecord.query.filter_by(record_id=record_id).first()
    if not record:
        return jsonify({"error": "Record not found"}), 404

    record.highlight = highlight
    record.memo = memo
    db.session.commit()

    return jsonify({"message": "Record updated successfully"}), 200

# 독서기록 삭제
@app.route('/delete_record/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    # 데이터베이스에서 해당 record_id의 데이터를 삭제
    record = UserRecord.query.filter_by(record_id=record_id).first()
    if not record:
        return jsonify({"error": "Record not found"}), 404

    # 삭제 처리
    try:
        db.session.delete(record)
        db.session.commit()
        return jsonify({"message": "Record deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
#### 포인트 관련 기능
# 사용자 포인트 업데이트
@app.route('/update_points', methods=['POST'])
def update_points():
    data = request.get_json()
    print("Received Points Update Data:", data)  # 요청 데이터 출력

    print(data)  # 요청 데이터 확인
    
    user_id = data.get('user_id')
    library_id = data.get('library_id')
    visit_increment = data.get('visit_increment', 0)
    record_increment = data.get('record_increment', 0)
    like_increment = data.get('like_increment', 0)
    

    if not user_id or not library_id:
        return jsonify({"error": "user_id와 library_id는 필수입니다."}), 400

    try:
        # 포인트 레코드 조회 또는 생성
        points_record = UserLibraryPoints.query.filter_by(user_id=user_id, library_id=library_id).first()
        if not points_record:
            points_record = UserLibraryPoints(
                user_id=user_id,
                library_id=library_id,
                visit_count=0,
                record_count=0,
                like_count=0,
            )
            db.session.add(points_record)

        # 오늘 날짜 생성
        today = datetime.now().date()
        print(today)
        
        # user_record에서 library_id와 오늘 날짜가 같은 레코드 존재 여부 확인
        record_count = UserRecord.query.filter(
            UserRecord.library_id == library_id,
            UserRecord.user_id == user_id,
            UserRecord.visit_date.cast(db.DATE) == today  # visit_date를 DATE 형식으로 변환하여 비교
        ).count()

        print(record_count)
        
        # None 값을 기본값 0으로 초기화
        points_record.visit_count = points_record.visit_count or 0
        points_record.record_count = points_record.record_count or 0
        points_record.like_count = points_record.like_count or 0

        if record_count <2: #먼저 등록을 하고 count를 하기 때문에 2로 설정
            # 포인트 값 업데이트
            points_record.visit_count += 1
            points_record.record_count += record_increment
            points_record.like_count += like_increment

            db.session.commit()
            
        else:
            points_record.visit_count += visit_increment
            points_record.record_count += record_increment
            points_record.like_count += like_increment
            db.session.commit()
        #
        # library_total_points 업데이트
        library_total_points = LibraryTotalPoints.query.filter_by(library_id=library_id).first()
        if not library_total_points:
            library_total_points = LibraryTotalPoints(
                library_id=library_id,
                total_points=0
            )
            db.session.add(library_total_points)

        # 해당 도서관의 total_points 재계산
        total_points = db.session.query(
            func.sum(UserLibraryPoints.total_points)
        ).filter(UserLibraryPoints.library_id == library_id).scalar()

        library_total_points.total_points = total_points or 0
        db.session.commit()


        return jsonify({
            "message": "포인트가 성공적으로 업데이트되었습니다.",
            "user_id": user_id,
            "library_id": library_id,
            "total_points": points_record.total_points,
            "library_total_points": library_total_points.total_points
        }), 200


    except Exception as e:
        db.session.rollback()
        print(f"Error occurred: {e}")
        return jsonify({"error": "포인트 업데이트에 실패했습니다."}), 500
    
# 독서 공감(좋아요) 처리   
@app.route('/update_likes', methods=['POST'])
def update_likes():
    data = request.get_json()
    record_id = data.get('record_id')
    user_id = data.get('user_id')  # 요청 데이터에서 user_id 가져오기

    # 요청 데이터 검증
    if not record_id or not user_id:
        return jsonify({"error": "record_id와 user_id를 제공해주세요."}), 400

    try:
        # 이미 공감한 기록인지 확인
        existing_like = LikesRecord.query.filter_by(user_id=user_id, record_id=record_id).first()
        if existing_like:
            return jsonify({"error": "이미 공감한 기록입니다."}), 400

        # 공감할 기록 조회
        record = UserRecord.query.filter_by(record_id=record_id).first()
        if not record:
            return jsonify({"error": "해당 기록을 찾을 수 없습니다."}), 404

        # 공감 수 증가
        record.likes += 1

        # 공감 기록 추가
        new_like = LikesRecord(user_id=user_id, record_id=record_id)
        db.session.add(new_like)
        db.session.commit()  # DB에 반영

        # `/update_points` API 호출을 통한 포인트 업데이트
        response = app.test_client().post('/update_points', json={
            "user_id": user_id,
            "library_id": record.library_id,
            "like_increment": 1  # 공감 증가
        })

        if response.status_code != 200:
            db.session.rollback()  # 문제가 생기면 롤백
            return jsonify({"error": "포인트 업데이트 중 문제가 발생했습니다."}), 500

        # 결과 데이터 파싱
        response_data = response.get_json()
        return jsonify({
            "message": "공감이 반영되었습니다.(상대 사용자 +3points)",
            "likes": record.likes,
            "total_points": response_data.get("total_points", 0)
        }), 2001

    except Exception as e:
        db.session.rollback()
        print(f"Error occurred: {e}")
        return jsonify({"error": f"서버 에러: {str(e)}"}), 500

# 특정 사용자의 해당 도서관 내 랭킹을 계산하는 함수
def get_user_rank(user_id, library_id):
    # 해당 도서관의 랭킹 데이터를 가져오기 (총 포인트 기준 정렬)
    ranking_data = UserLibraryPoints.query.filter_by(library_id=library_id).order_by(desc(UserLibraryPoints.total_points)).all()

    # 랭킹을 계산하기 위한 리스트 생성
    rank_list = []
    for idx, record in enumerate(ranking_data):
        rank_list.append({
            "rank": idx + 1,
            "user_id": record.user_id,
            "points": record.total_points
        })

    # 현재 사용자의 순위를 찾아 반환
    user_rank = next((item["rank"] for item in rank_list if item["user_id"] == user_id), None)

    return user_rank if user_rank else len(rank_list) + 1  # 사용자가 리스트에 없으면 마지막 순위 부여


#### 도서관별 랭킹 페이지 - rank.html
# 도서관별 사용자 랭킹
@app.route('/rank', methods=['GET'])
def rank_page():
    library_name = request.args.get('library', None)
    user_id = request.args.get('user_id')  # 로그인한 사용자의 user_id (쿼리스트링으로 전달)

    if not library_name:
        return jsonify({"error": "도서관 이름이 제공되지 않았습니다."}), 400

    # 도서관 이름으로 library_id 찾기
    library = Library.query.filter_by(library_name=library_name).first()
    if not library:
        return jsonify({"error": "해당 도서관 이름이 존재하지 않습니다."}), 404

    library_id = library.library_id

     # 도서관 총 포인트 가져오기
    library_total_points = LibraryTotalPoints.query.filter_by(library_id=library_id).first()
    total_points = library_total_points.total_points if library_total_points else 0

     # 레벨 및 Progress Bar 계산
    levels = [(0, 1000), (1001, 3000), (3001, 6000), (6001, 10000), (10001, float('inf'))]
    level = next(idx + 1 for idx, (min_p, max_p) in enumerate(levels) if min_p <= total_points <= max_p)
    current_level_min = levels[level - 1][0]
    next_level_max = levels[level - 1][1]
    
    
    # 현재 레벨에서의 포인트 범위 계산
    current_level_min = levels[level - 1][0]
    max_points_in_level = levels[level - 1][1]
    
    progress_percent = ((total_points - current_level_min) / (next_level_max - current_level_min)) * 100

    # 랭킹 데이터를 가져오기
    ranking_data = UserLibraryPoints.query.filter_by(library_id=library_id).order_by(desc(UserLibraryPoints.total_points)).all()
    # user_id로 users 테이블에서 아이디(id) 가져오기

    
    # 랭킹 데이터 준비
    rank_list = []

    for idx, record in enumerate(ranking_data):
        # user 테이블에서 user_id에 해당하는 사용자 정보 가져오기
        user = User.query.filter_by(user_id=record.user_id).first()
        user_id_from_user_table = user.id if user else None  # 사용자 아이디 가져오기
        user_obj = User.query.filter_by(user_id=record.user_id).first()
        # 랭킹 데이터 구성
        rank_list.append({
            "rank": idx + 1,
            "user_id": record.user_id,
            "id": user_id_from_user_table,  # 사용자 테이블의 아이디 (또는 None)
            "points": record.total_points,
            "username": user_obj.username,         # 사용자 이름
        })

    # 해당 도서관의 모든 서평 가져오기
    user_records = UserRecord.query.filter_by(library_id=library_id).all()
    all_user_records_data = [record.to_dict() for record in user_records]

    # 책 정보 포함된 데이터 준비
    all_user_records_bookinfos_data = []
    for record in all_user_records_data:
        isbn = record.get("isbn")
        user_id = record.get("user_id")  # user_id 가져오기
    
        # user_id로 users 테이블에서 아이디(id) 가져오기
        user = User.query.filter_by(user_id=user_id).first()
        user_id_from_user_table = user.id if user else None  # 아이디 가져오기

        if isbn:
            book_info = get_book_info(isbn)  # 책 정보를 가져오는 함수
            if book_info:
                record_with_info = {**record, **book_info, "id": user_id_from_user_table}
                all_user_records_bookinfos_data.append(record_with_info)
    
    # 현재 사용자의 랭킹 가져오기
    user_rank = get_user_rank(int(user_id), library_id) if user_id else None

    # 로그인한 사용자의 순위와 포인트 조회 (computed column total_points 사용)
    user_points = 0
    user_rank = None
    user_name = None
    if user_id:
        try:
            user_rank = next((item["rank"] for item in rank_list if item["user_id"] == int(user_id)), None)
            user_points_record = UserLibraryPoints.query.filter_by(user_id=int(user_id), library_id=library_id).first()
            if user_points_record:
                user_points = user_points_record.total_points

            # user_id로 사용자 이름 조회 (users 테이블의 username)
            user_obj = User.query.filter_by(user_id=int(user_id)).first()
            if user_obj:
                user_name = user_obj.username
        except Exception as e:
            print(f"사용자 포인트 조회 중 오류 발생: {e}")

    return render_template(
        'rank.html',
        library_name=library.library_name,
        level=level,
        total_points=total_points,
        max_points_in_level=max_points_in_level,
        progress_percent=int(progress_percent),
        rank_list=rank_list,
        all_user_records_bookinfos_data=all_user_records_bookinfos_data,
        user_rank=user_rank,  # 현재 사용자의 랭킹 추가
        user_points=user_points,
        user_id=user_id,  # 템플릿에 로그인한 user_id도 넘김
        user_name=user_name  # 사용자 이름 (username)
    )

#### 도서관 혼잡도
# 도서관 포인트 지도 데이터 반환
@app.route('/update_points_json', methods=['GET'])
def update_points_json():
    # 기존 JSON 데이터
    new_points = [
        {"position": {"lat": 35.2460769, "lng": 128.6910017}, "content": "국립창원대도서관"},
        {"position": {"lat": 35.249278, "lng": 128.682592}, "content": "경남대표도서관"},
        {"position": {"lat": 35.2138254, "lng": 128.6953575}, "content": "상남도서관"},
        {"position": {"lat": 35.2021394, "lng": 128.7077471}, "content": "성산도서관"},
        {"position": {"lat": 35.2334942, "lng": 128.6790201}, "content": "창원중앙도서관"},
        {"position": {"lat": 35.1524669, "lng": 128.6675415}, "content": "진해도서관"},
        {"position": {"lat": 35.1561894, "lng": 128.7063156}, "content": "진해기적의도서관"},
        {"position": {"lat": 35.1000314, "lng": 128.8171678}, "content": "동부도서관"},
        {"position": {"lat": 35.2246279, "lng": 128.573569}, "content": "마산회원도서관"},
        {"position": {"lat": 35.2327253, "lng": 128.5012807}, "content": "내서도서관"},
        {"position": {"lat": 35.3227295, "lng": 128.5798893}, "content": "최윤덕도서관"},
        {"position": {"lat": 35.2566599, "lng": 128.6184846}, "content": "고향의봄도서관"},
        {"position": {"lat": 35.2556674, "lng": 128.5202443}, "content": "중리초등복합시설도서관"},
        {"position": {"lat": 35.25321, "lng": 128.6484426}, "content": "명곡도서관"},
        {"position": {"lat": 35.183104, "lng": 128.5628597}, "content": "마산합포도서관"},
    ]
    updated_points = []

    for point in new_points:
        library_name = point['content']

        # `libraries` 테이블에서 `library_id` 가져오기
        library = Library.query.filter_by(library_name=library_name).first()

        if library:
            library_id = library.library_id

            # `library_total_points` 테이블에서 `total_points` 가져오기
            total_points_record = LibraryTotalPoints.query.filter_by(library_id=library_id).first()
            total_points = total_points_record.total_points if total_points_record else 0

            # 기존 JSON에 `variable` 값을 `total_points`로 설정
            point['variable'] = total_points
            updated_points.append(point)
        else:
            # 도서관이 존재하지 않는 경우
            point['variable'] = None
            updated_points.append(point)

    # JSON 반환
    return jsonify(updated_points)

#### 도서관사업소 자료검색 웹크롤링
@app.route('/searchlibchangwon', methods=['GET', 'POST'])
def searchlibchangwon():
    if request.method == 'POST':
        search_query = request.form.get('search_query')  # 검색어
        selected_library = request.form.get('selected_library')  # 선택한 도서관

        # 디버깅: 입력값 출력
        print(f"검색어: {search_query}, 선택한 도서관: {selected_library}")

        if not search_query or not selected_library:
            return render_template('searchlibchangwon.html', error="검색어와 도서관을 모두 입력해주세요.")

        
            
        # Selenium 설정
        # 현재 설치된 크롬 버전에 맞는 chromedriver 자동 설치
        chromedriver_autoinstaller.install()
        #service = Service('C:/Users/ksh07/Desktop/capston_design/chromedriver.exe')  # Chromedriver 경로
        options = Options()
        options.add_argument('--headless')  # 브라우저 UI 숨김
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        #driver = webdriver.Chrome(service=service, options=options)
        
        # 자동 설치된 chromedriver로 실행
        driver = webdriver.Chrome(options=options)
        
       

        try:
            driver.get("https://lib.changwon.go.kr/cl/search/data.html")

            # iframe 확인 및 전환
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"Iframes: {len(iframes)}")  # Iframe 개수 확인
            if len(iframes) > 0:
                driver.switch_to.frame(iframes[0])  # 첫 번째 iframe으로 전환

            # 검색창 대기 및 입력
            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'searchWord'))
            )
            search_box.clear()
            search_box.send_keys(search_query)
            print("검색창 탐색 및 입력 성공")

            # 도서관 선택
            library_checkbox = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, selected_library))
            )
            if not library_checkbox.is_selected():
                library_checkbox.click()
            print("체크박스 선택 성공")

            # 검색 버튼 클릭
            search_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.btn.btn-search"))
            )
            search_button.click()
            print("검색 버튼 클릭 성공")

            time.sleep(5)  # 검색 결과 로드 대기

            # 페이지 소스 가져오기
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            print("HTML 페이지 소스 가져오기 성공")

            # 검색 결과 추출
            books = []
            for book_div in soup.select('.list'):
                try:
                    title = book_div.select_one('.ico-bk a').get_text(strip=True)
                    author = book_div.select_one('li strong:contains("저자") + span').get_text(strip=True)
                    library = book_div.select_one('.blue').get_text(strip=True)
                    status = book_div.select_one('.using1, .using2, .nonone').get_text(strip=True)
                    img_tag = book_div.select_one('img')
                    img_url = img_tag['src'] if img_tag else '이미지 없음'
                    books.append({
                        "title": title,
                        "author": author,
                        "library": library,
                        "status": status,
                        "image_url": img_url
                    })
                except AttributeError as e:
                    print(f"검색 결과 추출 중 오류 발생: {e}")
                    continue

            return render_template('searchlibchangwon.html', books=books, search_query=search_query)

        except Exception as e:
            print(f"Error during Selenium execution: {e}")
            return render_template('searchlibchangwon.html', error="검색 중 오류가 발생했습니다.")

        finally:
            driver.quit()

    return render_template('searchlibchangwon.html')

####책 주문
@app.route('/submit_order', methods=['POST'])
def submit_order():
    data = request.get_json()

    if not data or 'selected_books' not in data or 'address' not in data or 'user_id' not in data:
        return jsonify({"error": "유효한 데이터가 아닙니다.", "received_data": data}), 400

    selected_books = data['selected_books']
    address = data['address']
    user_id = data['user_id']  # 클라이언트에서 받은 user_id

    try:
        # 주문 저장
        new_order = Order(user_id=user_id, address=address)  # user_id를 저장
        db.session.add(new_order)
        db.session.commit()  # 주문 ID 생성

        # 주문 상세 저장
        for book in selected_books:
            book_data = eval(book)  # JSON 데이터를 Python dict로 변환
            new_order_detail = OrderDetails(
                order_id=new_order.order_id,
                book_title=book_data['title'],
                author=book_data.get('author', 'N/A'),
                library=book_data.get('library', 'N/A'),
                image_url=book_data.get('image_url', '')
            )
            db.session.add(new_order_detail)

        db.session.commit()
        return jsonify({"message": "주문이 완료되었습니다.", "order_id": new_order.order_id}), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error saving order: {e}")
        return jsonify({"error": "주문 저장 중 오류가 발생했습니다."}), 500

#주문내역
@app.route('/get_orders', methods=['GET'])
def get_orders():
    user_id = request.args.get('user_id')  # 클라이언트에서 전달된 user_id 가져오기

    if not user_id:
        return jsonify({"error": "로그인이 필요합니다."}), 400

    try:
        # `orders` 테이블에서 해당 사용자의 주문만 조회
        orders = Order.query.filter_by(user_id=user_id).all()
        result = []

        for order in orders:
            # 해당 주문 ID의 세부 정보를 `order_details`에서 가져옴
            order_details = OrderDetails.query.filter_by(order_id=order.order_id).all()
            books = [
                {
                    "order_details_id": detail.order_details_id,
                    "title": detail.book_title,
                    "author": detail.author,
                    "library": detail.library,
                    "image_url": detail.image_url,
                    "loan_status": detail.loan_status
                }
                for detail in order_details
            ]

            # `orders`와 `order_details` 정보를 합침
            result.append({
                "order_id": order.order_id,
                "user_id": order.user_id,
                "address": order.address,
                "created_at": order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "books": books,
            })

        return jsonify({"orders": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/return_request', methods=['POST'])
def return_request():
    data = request.get_json()
    order_details_id = data.get('order_details_id')

    if not order_details_id:
        return jsonify({"error": "order_details_id가 필요합니다."}), 400

    # 숫자로 변환하여 검색
    try:
        order_details_id = int(order_details_id)  
    except ValueError:
        return jsonify({"error": "유효한 order_details_id가 아닙니다."}), 400

    # 주문 상세 레코드 조회
    order_detail = OrderDetails.query.filter_by(order_details_id=order_details_id).first()
    if not order_detail:
        return jsonify({"error": "해당 주문 상세 정보를 찾을 수 없습니다."}), 404

    # 대출 상태를 "수거중"으로 변경
    order_detail.loan_status = "수거중"
    db.session.commit()

    return jsonify({"message": "반납 신청이 완료되었습니다.", "loan_status": order_detail.loan_status}), 200


#### 1등 유저 건물 위에 띄워주기
# 1위 유저 정보 받기
@app.route('/get_top_user', methods=['GET'])
def get_top_user():
    library_name = request.args.get('library', None)
    if not library_name:
        return jsonify({"error": "도서관 이름이 제공되지 않았습니다."}), 400

    # 도서관 이름으로 library_id 찾기
    library = Library.query.filter_by(library_name=library_name).first()
    if not library:
        return jsonify({"error": "해당 도서관 이름이 존재하지 않습니다."}), 404

    library_id = library.library_id

    # 순위표에서 1위 유저 찾기
    top_user = UserLibraryPoints.query.filter_by(library_id=library_id).order_by(desc(UserLibraryPoints.total_points)).first()

    if not top_user:
        return jsonify({"message": "해당 도서관에 유저 데이터가 없습니다."}), 200

    # 유저의 상세 정보 가져오기
    user = User.query.filter_by(user_id=top_user.user_id).first()
    return jsonify({
        "user_id": user.id,
        "points": top_user.total_points,
    })



#### 화면 라우트
# HTML 렌더링
@app.route('/')
def index():
    return render_template('home.html')

# 로그인 화면 라우트
@app.route('/login')
def login():
    return render_template('login.html')

# 회원가입 화면 라우트
@app.route('/join')
def join():
    return render_template('join.html')

# /독서 기록 
@app.route('/rank')
def rank():
    return render_template('rank.html')  

@app.route('/barcode')
def barcode():
    return render_template('barcode.html')

# HTML 렌더링 라우트
@app.route('/library')
def library_page():
    return render_template('library.html')

# HTML 렌더링 라우트
@app.route('/insertisbn')
def insertisbn():
    return render_template('insertisbn.html')

# 도서관 사업소 웹크롤링링 기능
@app.route('/searchlibchangwon')
def searchlib():
    return render_template('searchlibchangwon.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5500, debug=True)
