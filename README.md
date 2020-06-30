# Text Summarization and TTS
경희대학교 2020학년도 1학기 학부 연구에서 진행한 프로젝트입니다. 네이버 뉴스 링크를 받아와 요약하고, 키워드와 주요 문장을 한국어 음성으로 출력합니다.


## TextRank
TextRank 알고리즘을 활용하여 문자 배열에서 키워드와 주요 문장을 추출합니다.
코드 속에 있는 TextRank 관련 함수는 lovit/textrank 패키지의 소스코드 내용을 사용하였습니다.
제가 직접 작성하지 않은 코드의 경우 주석으로 Source Code 표시를 해두었습니다.
TextRank 소스 코드와 내용에 대해 자세히 알고 싶으시다면 아래 두 페이지를 방문해주시길 바랍니다.

<li>TextRank 설명글 블로그 링크입니다.<li>
https://lovit.github.io/nlp/2019/04/30/textrank/

<li>패키지 GitHub 링크입니다.<li>
https://github.com/lovit/textrank/


## Crawling
크롬 드라이버를 활용하여 네이버 뉴스 기사의 url의 기사 제목과 본문 내용을 크롤링했습니다.
html tag name을 이용하여 제목과 본문만을 가져와 result1.txt라는 이름으로 저장합니다.

<li>selenium 패키지 설치 및 크롬 드라이버 이용 방법은 아래의 블로그를 참고하였습니다.<li>
https://m.blog.naver.com/jsk6824/221763151860


## TTS
MS의 SAPI에 내장된 SpVoice를 사용하였습니다.
win32com.client를 import하고, tts = win32com.client.Dispatch("SAPI.SpVoice")로 선언하여 Speak함수를 이용해 문자열(str)을 음성으로 출력합니다.
이를 위해 앞서 사용한 textrank 결과물을 str으로 변환하고, "/n"을 제거하고, "."에서 줄바꿈을 해주는 등의 전처리 과정을 거쳤습니다.
자세한 코드는 업로드된 코드를 참고하시길 바랍니다.
