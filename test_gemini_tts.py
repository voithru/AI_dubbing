#!/usr/bin/env python3
"""
Gemini TTS 테스트 스크립트
"""

import os
from dotenv import load_dotenv
from gemini_tts_helper import get_gemini_tts_client, VoiceOptions, ModelOptions

def test_gemini_tts():
    """Gemini TTS 기본 기능 테스트"""
    
    print("🔍 Gemini TTS 테스트 시작...")
    
    try:
        # 클라이언트 생성
        print("\n1. Gemini TTS 클라이언트 생성 중...")
        client = get_gemini_tts_client()
        
        # 간단한 테스트 텍스트
        test_text = "안녕하세요, 여러분. 이번시간에는 LLM의 tts 기능을 이용한 음성생성에 대해 알아보겠습니다."
        print(f"\n2. 테스트 텍스트: '{test_text}'")
        
        # .env 파일 또는 환경변수에서 모델과 음성 가져오기
        model_to_use = os.getenv('GEMINI_TTS_MODEL', ModelOptions.DEFAULT)
        voice_to_use = os.getenv('GEMINI_TTS_VOICE', VoiceOptions.DEFAULT)

        # 음성 합성 및 파일 저장
        print(f"\n3. 음성 합성 중 ('{voice_to_use}' 음성, '{model_to_use}' 모델)...")
        output_file = "test_gemini_output.wav"
        
        client.synthesize_to_file(
            text=test_text,
            output_path=output_file,
            voice=voice_to_use,
            model=model_to_use
        )
        
        print(f"✅ 음성 합성 성공! 파일 저장: {output_file}")
        
        # 파일 크기 확인
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"📏 생성된 오디오 파일 크기: {file_size} bytes")
        
        print("\n🎉 모든 테스트 완료!")
        print(f"\n💡 생성된 파일을 재생해서 음성을 확인해보세요:")
        print(f"   - {output_file} ('{voice_to_use}' 음성)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        print("\n🔧 해결 방법:")
        print("1. Google API 키가 올바른지 확인")
        print("2. 환경변수 GOOGLE_API_KEY가 설정되었는지 확인:")
        print("   export GOOGLE_API_KEY='your-api-key-here'")
        print("3. Google AI 프로젝트에 TTS API가 활성화되어 있는지 확인")
        print("4. API 사용량 한도를 초과하지 않았는지 확인")
        return False

if __name__ == "__main__":
    load_dotenv()
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if api_key:
        print(f"🔑 API 키 발견: {api_key[:5]}...{api_key[-4:]}")
    else:
        print("⚠️  GOOGLE_API_KEY가 설정되지 않았습니다.")
        print("다음 방법 중 하나를 사용하세요:")
        print("1. .env 파일에 GOOGLE_API_KEY=your-key-here 추가")
        print("2. 환경변수로 설정: export GOOGLE_API_KEY='your-key-here'")
        print("\nGoogle AI Studio (https://aistudio.google.com/app/apikey)에서 API 키를 생성할 수 있습니다.")
    
    tts_model = os.getenv('GEMINI_TTS_MODEL', ModelOptions.DEFAULT)
    tts_voice = os.getenv('GEMINI_TTS_VOICE', VoiceOptions.DEFAULT)
    print(f"🎵 TTS 모델: {tts_model}")
    print(f"🗣️  TTS 음성: {tts_voice}")
    
    test_gemini_tts()
