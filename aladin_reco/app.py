# ==============================================================================
# AI 북 큐레이터 Streamlit 애플리케이션 (v2 - 리팩토링 및 개선 버전)
# ==============================================================================
#
# 주요 개선 사항:
# 1. 리팩토링 및 구조화: 설정(CONFIG), API 로직, UI 로직 분리.
# 2. 독스트링 및 타입 힌트: 모든 함수에 명세 추가로 가독성 및 유지보수성 향상.
# 3. 에러 처리 강화: 사용자 정의 예외를 통한 명확한 오류 처리.
# 4. 로깅 설정: 애플리케이션 동작 및 오류 추적을 위한 로그 기록.
#
# ==============================================================================

import streamlit as st
import requests
import xml.etree.ElementTree as ET
import google.generativeai as genai
import time
import base64
import os
import logging
from typing import List, Dict, Optional, Any

# --- 1. 기본 설정: 로깅 및 환경 변수 ---

# 로거 설정: 터미널에 시간, 로그 레벨, 메시지를 출력합니다.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

# 사용자 정의 예외 클래스
class BookSearchError(Exception):
    """알라딘 책 검색 API 호출 실패 시 발생하는 예외"""
    pass

class RecommendationError(Exception):
    """Gemini 추천 생성 실패 시 발생하는 예외"""
    pass

# --- 2. 설정(Configuration) 관리 ---

# API 키 및 설정을 환경 변수에서 로드 (보안 강화)
ALADIN_TTBKEY = os.getenv("ALADIN_TTBKEY")
GENAI_API_KEY = os.getenv("GENAI_API_KEY")

# API 관련 상수 및 프롬프트를 CONFIG로 그룹화
CONFIG = {
    "aladin": {
        "search_url": "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx",
        "lookup_url": "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx",
    },
    "gemini": {
        "model": "gemini-1.5-flash",
        "prompt": """당신은 사용자의 상황과 감정을 깊이 이해하고 공감해주는 전문 북 큐레이터입니다.
사용자의 요청: "{user_query}"

아래는 이 요청과 관련하여 찾은 책 목록입니다.
--- 책 목록 ---
{book_list_str}
--- 책 목록 끝 ---

사용자의 요청에 가장 잘 맞는 책을 단 한 권만 골라주세요.
추천하는 이유를 사용자가 따뜻한 위로와 공감을 얻을 수 있도록 150자 내외의 진심 어린 문장으로 설명해주세요.
출력 형식은 반드시 아래와 같이 맞춰주세요:

추천 도서: [책 제목]
추천 이유: [당신의 추천사]"""
    }
}

# --- 3. API 호출 및 데이터 처리 함수 ---

def get_book_detail(item_id: str, item_id_type: str = 'ISBN13') -> Optional[Dict[str, str]]:
    """
    알라딘 상품 조회 API로 특정 책의 별점 정보를 가져옵니다.

    Args:
        item_id (str): 조회할 상품의 ID (ISBN, ISBN13 등).
        item_id_type (str): 상품 ID의 종류.

    Returns:
        Optional[Dict[str, str]]: 별점 정보가 담긴 딕셔너리 또는 실패 시 None.
    """
    params = {
        'ttbkey': ALADIN_TTBKEY,
        'itemId': item_id,
        'ItemIdType': item_id_type,
        'output': 'xml',
        'Version': '20131101',
        'OptResult': 'ratingInfo'
    }
    try:
        response = requests.get(CONFIG["aladin"]["lookup_url"], params=params)
        response.raise_for_status()
        response.encoding = 'utf-8'
        root = ET.fromstring(response.text)
        ns = {'': 'http://www.aladin.co.kr/ttb/apiguide.aspx'}
        item = root.find('item', ns)
        
        if item is None:
            return None

        star_rating = "별점 정보 없음"
        sub_info = item.find('subInfo', ns)
        if sub_info is not None:
            rating_info = sub_info.find('ratingInfo', ns)
            if rating_info is not None:
                score_elem = rating_info.find('ratingScore', ns)
                if score_elem is not None and score_elem.text and float(score_elem.text) > 0:
                    star_rating = f"{score_elem.text} / 10.0"
                    return {'star_rating': star_rating}
        
        review_rank_elem = item.find('customerReviewRank', ns)
        if review_rank_elem is not None and review_rank_elem.text and int(review_rank_elem.text) > 0:
            star_rating = f"{int(review_rank_elem.text)} / 10"
        
        return {'star_rating': star_rating}

    except requests.exceptions.RequestException as e:
        logging.warning(f"알라딘 상세 정보 조회 실패 (ItemID: {item_id}): {e}")
        return None
    except ET.ParseError as e:
        logging.warning(f"알라딘 상세 정보 XML 파싱 실패 (ItemID: {item_id}): {e}")
        return None

def search_books_by_title(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    알라딘 API로 책을 검색하여 상세 정보가 포함된 리스트로 반환합니다.

    Args:
        query (str): 검색할 키워드.
        max_results (int): 최대 검색 결과 수.

    Returns:
        List[Dict[str, Any]]: 검색된 책 정보 딕셔너리의 리스트.
    
    Raises:
        BookSearchError: API 호출 또는 데이터 처리 중 오류 발생 시.
    """
    logging.info(f"'{query}'에 대한 알라딘 책 검색을 시작합니다.")
    params = {
        'ttbkey': ALADIN_TTBKEY, 'QueryType': 'Keyword', 'MaxResults': str(max_results),
        'SearchTarget': 'Book', 'output': 'xml', 'Query': query, 'Version': '20131101', 'Cover': 'MidBig'
    }
    try:
        response = requests.get(CONFIG["aladin"]["search_url"], params=params)
        response.raise_for_status()
        response.encoding = 'utf-8'
        root = ET.fromstring(response.text)
        ns = {'': 'http://www.aladin.co.kr/ttb/apiguide.aspx'}
        items = root.findall('item', ns)

        if not items:
            logging.warning(f"'{query}'에 대한 검색 결과가 없습니다.")
            return []

        book_list = []
        for item in items:
            isbn13 = item.find('isbn13', ns).text if item.find('isbn13', ns) is not None else None
            star_rating = "별점 정보 없음"
            if isbn13:
                details = get_book_detail(isbn13)
                if details:
                    star_rating = details.get('star_rating', '별점 정보 없음')
            
            book_list.append({
                'title': item.find('title', ns).text if item.find('title', ns) is not None else "제목 없음",
                'author': item.find('author', ns).text if item.find('author', ns) is not None else "저자 없음",
                'description': item.find('description', ns).text if item.find('description', ns) is not None else "설명 없음",
                'cover_url': item.find('cover', ns).text,
                'star_rating': star_rating,
            })
        logging.info(f"총 {len(book_list)}권의 책을 찾았습니다.")
        return book_list

    except requests.exceptions.RequestException as e:
        logging.exception("알라딘 API 요청 중 네트워크 오류가 발생했습니다.")
        raise BookSearchError(f"알라딘 서버와 통신 중 오류가 발생했습니다: {e}")
    except ET.ParseError as e:
        logging.exception("알라딘 API 응답 XML 파싱 중 오류가 발생했습니다.")
        raise BookSearchError(f"알라딘 서버의 응답을 처리하는 데 실패했습니다: {e}")

def get_gemini_recommendation(user_query: str, book_list: List[Dict[str, Any]]) -> str:
    """
    Gemini API를 호출하여 책 추천사와 제목을 받습니다.

    Args:
        user_query (str): 사용자의 원본 요청.
        book_list (List[Dict[str, Any]]): 알라딘에서 검색된 책 리스트.

    Returns:
        str: Gemini가 생성한 추천 텍스트.

    Raises:
        RecommendationError: Gemini API 호출 중 오류 발생 시.
    """
    logging.info("Gemini에게 책 추천을 요청합니다.")
    book_list_str = ""
    for i, book in enumerate(book_list):
        book_list_str += (
            f"\n{i+1}. 제목: {book['title']}\n"
            f"   저자: {book['author']}\n"
            f"   소개: {book['description']}\n"
            f"   별점: {book['star_rating']}\n"
        )
    
    prompt = CONFIG["gemini"]["prompt"].format(user_query=user_query, book_list_str=book_list_str)

    try:
        model = genai.GenerativeModel(CONFIG["gemini"]["model"])
        response = model.generate_content(prompt)
        logging.info("Gemini로부터 추천 응답을 받았습니다.")
        return response.text.strip()
    except Exception as e:
        logging.exception("Gemini API 호출 중 심각한 오류가 발생했습니다.")
        raise RecommendationError(f"AI 추천 생성 중 오류가 발생했습니다: {e}")

def parse_recommended_book_title(gemini_response: str) -> Optional[str]:
    """Gemini 응답 텍스트에서 '추천 도서:' 라인을 파싱하여 제목을 추출합니다."""
    try:
        for line in gemini_response.splitlines():
            if line.startswith("추천 도서:"):
                return line.replace("추천 도서:", "").strip()
    except Exception:
        return None
    return None

# --- 4. Streamlit UI 헬퍼 및 메인 로직 ---

@st.cache_data
def get_base64_of_bin_file(file_path: str) -> str:
    """로컬 파일을 읽어 Base64 문자열로 변환합니다. (Streamlit 캐시 적용)"""
    with open(file_path, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def set_page_background(file_path: str):
    """지정된 이미지를 웹페이지 배경으로 설정합니다."""
    try:
        bin_str = get_base64_of_bin_file(file_path)
        st.markdown(f'''
            <style>
            .stApp {{
                background-image: url("data:image/jpg;base64,{bin_str}");
                background-size: cover;
            }}
            </style>
        ''', unsafe_allow_html=True)
    except FileNotFoundError:
        logging.warning(f"배경 이미지 파일 '{file_path}'을 찾을 수 없습니다.")
        st.info("ℹ️ 배경 이미지를 찾을 수 없어 기본 배경으로 표시됩니다.")

def display_recommendation_card(book_data: Dict[str, Any], gemini_response: str):
    """최종 추천 결과를 카드 형태로สวยงาม하게 표시합니다."""
    st.balloons()
    st.markdown("""
        <style>
        .result-container {
            background-color: rgba(255, 255, 255, 0.9); border-radius: 15px; padding: 25px;
            box-shadow: 0 6px 12px rgba(0,0,0,0.15); border: 1px solid #eee;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="result-container">', unsafe_allow_html=True)
        st.header("✨ 당신을 위한 추천 도서 ✨")
        col1, col2 = st.columns([1, 2])

        with col1:
            if book_data['cover_url']:
                st.image(book_data['cover_url'], use_container_width=True)
        
        with col2:
            st.subheader(book_data['title'])
            st.write(f"**✍️ 저자:** {book_data['author']}")
            st.write(f"**⭐ 알라딘 별점:** {book_data['star_rating']}")
            reason = "\n".join(gemini_response.splitlines()[1:]).replace('추천 이유:', '').strip()
            st.markdown(f"**💬 AI의 추천사:** *{reason}*")

        with st.expander("📖 책 소개 더 보기"):
            st.write(book_data['description'])
        
        st.markdown('</div>', unsafe_allow_html=True)

def run_recommendation_workflow(user_query: str):
    """
    사용자 입력을 받아 책 추천의 전체 과정을 실행하고 결과를 표시합니다.
    """
    progress_bar = st.progress(0, text="AI가 당신의 마음을 읽고 있어요...")
    try:
        # 1. 책 검색
        found_books = search_books_by_title(user_query)
        if not found_books:
            st.error(f"'{user_query}'(와)과 관련된 책을 찾지 못했습니다. 다른 키워드로 다시 시도해주세요.")
            return

        # 2. Gemini 추천 생성
        progress_bar.progress(33, text="관련 도서를 찾았어요. 이제 가장 좋은 책을 고를게요...")
        gemini_result = get_gemini_recommendation(user_query, found_books)
        recommended_title = parse_recommended_book_title(gemini_result)
        
        # 3. 추천된 책 정보 매칭
        progress_bar.progress(66, text="거의 다 됐어요! 추천 결과를 예쁘게 꾸미는 중...")
        recommended_book = None
        if recommended_title:
            for book in found_books:
                if recommended_title in book['title'] or book['title'] in recommended_title:
                    recommended_book = book
                    break
        
        time.sleep(1)
        progress_bar.progress(100, text="짠! 당신을 위한 책이 도착했어요.")
        
        # 4. 결과 표시
        if recommended_book:
            display_recommendation_card(recommended_book, gemini_result)
        else:
            st.error("추천 결과를 처리하는 중 문제가 발생했습니다. AI의 추천 도서를 목록에서 찾을 수 없습니다.")
            st.write("**🤖 AI 원문 응답:**")
            st.code(gemini_result, language=None)

    except (BookSearchError, RecommendationError) as e:
        st.error(f"오류가 발생했습니다: {e}")
    finally:
        # 작업 완료 후 프로그레스바 숨기기
        time.sleep(0.5)
        progress_bar.empty()

def main():
    """메인 스트림릿 애플리케이션 함수"""
    # --- 키 유효성 검사 ---
    if not ALADIN_TTBKEY:
        st.error("❌ 알라딘 TTBKey가 설정되지 않았습니다. 환경 변수 `ALADIN_TTBKEY`를 설정해주세요.")
        st.stop()
    if not GENAI_API_KEY:
        st.error("❌ Gemini API 키가 설정되지 않았습니다. 환경 변수 `GENAI_API_KEY`를 설정해주세요.")
        st.stop()
    try:
        genai.configure(api_key=GENAI_API_KEY)
    except Exception as e:
        st.error(f"❌ Gemini API 키 설정 중 오류가 발생했습니다: {e}")
        st.stop()

    # --- UI 렌더링 ---
    set_page_background('background1.jpg')
    st.title("📚 AI 북 큐레이터")
    st.info(f"Aladin API and Gemini {CONFIG['gemini']['model']}", icon="ℹ️")
    st.markdown("---")

    with st.form("recommendation_form"):
        user_input = st.text_input("어떤 책을 추천해 드릴까요?", placeholder="키워드로 입력해주세요. 예: 사랑, 행복, 우주...")
        submit_button = st.form_submit_button("나만을 위한 책 추천받기")

    if submit_button:
        if user_input:
            run_recommendation_workflow(user_input)
        else:
            st.warning("추천받고 싶은 책에 대한 내용을 입력해주세요!")

if __name__ == "__main__":
    main()