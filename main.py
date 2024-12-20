import boto3
import os
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# S3 클라이언트 초기화
s3_client = boto3.client("s3")

def handler(event, context):
    # ChromeDriver 경로
    service = Service("/opt/chromedriver")  # 명시적으로 ChromeDriver 경로 설정

    # S3 이벤트에서 버킷 이름과 파일 키를 가져옴
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    file_key = event['Records'][0]['s3']['object']['key']

    # 로컬 임시 파일 경로 설정
    local_file_path = os.path.join(tempfile.gettempdir(), "encrypted_file.html")
    decrypted_file_path = os.path.join(tempfile.gettempdir(), "decrypted_file.html")

    # S3에서 암호화된 파일 다운로드
    s3_client.download_file(bucket_name, file_key, local_file_path)

    # Selenium 설정
    chrome_options = webdriver.ChromeOptions()
    chrome_options.binary_location = "/opt/chrome/chrome"
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko")
    chrome_options.add_argument('window-size=1392x1150')
    chrome_options.add_argument("disable-gpu")
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("driver", driver)

    try:
        # Selenium으로 HTML 파일 열기
        driver.get(f"file://{local_file_path}")
        print("get file")

        # 암호 입력 필드 대기
        wait = WebDriverWait(driver, 10)  # 최대 10초 대기
        password_input = wait.until(EC.presence_of_element_located((By.ID, "xem_pwd1")))

        # 비밀번호 입력 처리 (HTML ID에 따라 수정 필요)
        password_input = driver.find_element("id", "xem_pwd1")
        password_input.send_keys("password!!!!!!!!!!")  # 비밀번호 입력
        password_input.submit()
        print("password input")

        # 결과 가져오기
        time.sleep(2)
        decrypted_content = driver.page_source

        # UTF-8 HTML에 EUC-KR 헤더 추가
        """
        UTF-8 HTML에 <meta http-equiv="Content-Type" content="text/html; charset=euc-kr"> 태그를 추가
        """
        soup = BeautifulSoup(decrypted_content, "html.parser")

        # 기존 <meta> 태그를 모두 제거
        if soup.head:
            for meta_tag in soup.head.find_all("meta"):
                meta_tag.decompose()

            # <meta http-equiv="Content-Type" content="text/html; charset=euc-kr"> 추가
            new_meta_tag = soup.new_tag(
                "meta", **{"http-equiv": "Content-Type", "content": "text/html; charset=euc-kr"}
            )
            soup.head.insert(0, new_meta_tag)

        modified_content=str(soup)

        # 해독된 HTML 파일 저장
        with open(decrypted_file_path, "w", encoding="utf-8") as f:
            f.write(modified_content)

        # S3에 해독된파일 업로드
        base_folder = "/".join(file_key.split("/")[:-1])
        decrypted_key = f"{base_folder}/decrypted-{os.path.basename(file_key)}"

        s3_client.upload_file(decrypted_file_path, bucket_name, decrypted_key)

        print(f"Decrypted file uploaded to S3: {decrypted_key}")
        return {"statusCode": 200, "body": "File decrypted and uploaded successfully."}

    except Exception as e:
        print(f"Error during decryption: {e}")
        return {"statusCode": 500, "body": str(e)}
    finally:
        driver.quit()
