from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time

# 사용자 입력
search_keyword = input("검색어를 입력하세요: ").strip()
library_name = input("도서관 이름을 입력하세요 (예: 창원중앙도서관): ").strip()
library_ids = {
    "창원중앙도서관": "MA",
    "마산내서도서관": "MF",
    "진해도서관": "MJ",
    "동부도서관": "MK",
    "고향의봄도서관": "MC",
    "명곡도서관": "MM",
    "성산도서관": "MB",
    "상남도서관": "MD",
    "마산합포도서관": "MG",
    "마산회원도서관": "ME",
    "마산중리초등복합시설도서관": "MH",
    "진해기적의도서관": "MN",
    "최윤덕도서관": "MO"
}
if library_name not in library_ids:
    raise ValueError("유효하지 않은 도서관 이름입니다. 다시 실행해주세요.")


# ChromeDriver 설정
service = Service('C:/Users/ksh07/Desktop/capston_design/chromedriver.exe')  # chromedriver 경로
options = Options()
options.add_argument("--start-maximized")  # 브라우저 최대화 옵션
driver = webdriver.Chrome(service=service, options=options)

try:
    
    # 도서관 검색 페이지 열기
    driver.get("https://lib.changwon.go.kr/cl/search/data.html")

    # iframe 확인 및 전환
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    if len(iframes) > 0:
        driver.switch_to.frame(iframes[0])  # 첫 번째 iframe으로 전환
    
    # 검색창 대기 및 입력
    search_box = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, 'searchWord'))
    )
    search_box.clear()  # 기존 값 지우기
    search_box.send_keys(search_keyword)  # 검색어 입력

    # 도서관 체크박스 선택
    library_id = library_ids[library_name]
    library_checkbox = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, library_id))
    )
    if not library_checkbox.is_selected():
        library_checkbox.click()  # 체크박스 클릭

    # 검색 버튼 클릭
    search_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input.btn.btn-search"))
    )
    search_button.click()

    # 검색 결과 로드 대기
    time.sleep(5)

    # 페이지 소스 가져오기
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    # 검색 결과 추출
    books = []
    for book_div in soup.select('.list'):
        try:
            title = book_div.select_one('.ico-bk a').get_text(strip=True) # 책 제목목
            author = book_div.select_one('li strong:contains("저자") + span').get_text(strip=True) # 저자
            library = book_div.select_one('.blue').get_text(strip=True) # 도서관관
            status = book_div.select_one('.using1, .using2, .nonone').get_text(strip=True) # 대출상태
            # 이미지 URL 추출
            img_tag = book_div.select_one('img')
            img_url = img_tag['src'] if img_tag else '이미지 없음'
            books.append({
                "title": title,
                "author": author,
                "library": library,
                "status": status,
                "image_url": img_url
            })
        except AttributeError:
            continue

    # 결과 출력
    for idx, book in enumerate(books, start=1):
        print(f"{idx}. 제목: {book['title']}, 저자: {book['author']}, 도서관: {book['library']}, 상태: {book['status']}, 이미지: {book['image_url']}")

except Exception as e:
    print(f"오류 발생: {e}")
finally:
    # 브라우저 닫기
    driver.quit()
