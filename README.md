# 프로젝트 제목
```
AladinGemini — Aladin API를 이용한 Gemini 책 추천 서비스
```

# 프로젝트 설명
```
AladinGemini는 읽고 싶은 책에 대한 키워드를 입력하면,
Aladin API를 통해서 책을 검색한 후 Google Gemini AI로 분석해 책을 추천
```

# 가상환경 설정
```
conda create -n aladin_reco python=3.9
```

# API_KEY 설정
```
export ALADIN_TTBKEY=""
export GENAI_API_KEY=""
```

# 라이브러리 설치
```
pip install -r requirements.txt
```

# 앱 실행
```
./run.sh
```

# 웹 구성
<p align="center">
  <img src="https://github.com/user-attachments/assets/c4afad51-218e-4db7-b2c4-4664bd57650a" width="700">
  <img src="https://github.com/user-attachments/assets/619d516b-0975-420a-b58e-95937cbf9ee8" width="700">
  <img src="https://github.com/user-attachments/assets/6bd9063e-f828-4b85-b074-5f772efc9c6c" width="700">
  <img src="https://github.com/user-attachments/assets/000f7de5-8ece-4092-ad89-b4da0d210df2" width="700">
</p>

# Ngrok
(로컬 서버 => 공개 서버로 전환)
```
<Mac M1 설치 기준>
https://ngrok.com/downloads/mac-os
brew install ngrok
ngrok config add-authtoken <token>
ngrok http 80
```

# Ngrok log
<p align="center">
  <img src="https://github.com/user-attachments/assets/5ca755c3-d8f8-4088-b3b4-1b735945d351" width="700">
</p>

# Ngrok(공개 서버 접속)
[Ngrok 공개 서버 접속](https://c83c0967a9dd.ngrok-free.app/)<br>

# Ngrok 참고 문서
[위키독스](https://cordcat.tistory.com/105)<br>

# Make requirements.txt
```
pip install pipreqs
```

# pipreqs 참고 문서
[PyPI pipreqs](https://pypi.org/project/pipreqs/)<br>

# Gemini 참고 문서
[위키독스](https://wikidocs.net/254713)<br>

# 알라딘 OpenAPI 참고 문서
[알라딘 OpenAPI 안내](https://blog.aladin.co.kr/openapi/popup/6695306)<br>
[알라딘 OpenAPI 매뉴얼](https://docs.google.com/document/d/1mX-WxuoGs8Hy-QalhHcvuV17n50uGI2Sg_GHofgiePE/edit?tab=t.0#heading=h.npqn2iowpse8)<br>
