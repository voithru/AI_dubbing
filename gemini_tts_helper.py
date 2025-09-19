"""
Gemini TTS 헬퍼 모듈
Google Gemini의 Text-to-Speech API를 사용하여 텍스트를 음성으로 변환합니다.
"""

import google.generativeai as genai
from google.generativeai import types
import os
import time
import random
import wave
from typing import Optional
from dotenv import load_dotenv

class GeminiTTSClient:
    """Gemini TTS 클라이언트"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Gemini TTS 클라이언트를 초기화합니다.
        
        Args:
            api_key (str, optional): Google API 키. 
                                   기본값은 .env 파일 또는 환경변수 GOOGLE_API_KEY
        """
        load_dotenv()
        
        if api_key is None:
            api_key = os.getenv('GOOGLE_API_KEY')
            
        if not api_key:
            raise ValueError(
                "Google API 키가 필요합니다.\n"
                "다음 방법 중 하나를 사용하세요:\n"
                "1. .env 파일에 GOOGLE_API_KEY=your-key-here 추가\n"
                "2. 환경변수 GOOGLE_API_KEY 설정\n"
                "3. api_key 매개변수로 직접 전달\n\n"
                "Google AI Studio (https://aistudio.google.com/app/apikey)에서 API 키를 생성할 수 있습니다."
            )
        
        genai.configure(api_key=api_key)
        self.client = genai
        print("✅ Gemini TTS 클라이언트가 초기화되었습니다.")

    def synthesize_speech(
        self,
        text: str,
        voice: Optional[str] = None, # voice 매개변수는 현재 API에서 직접 사용되지 않을 수 있습니다.
        model: Optional[str] = None,
        max_retries: int = 10
    ) -> bytes:
        """
        텍스트를 음성으로 변환합니다.
        
        Args:
            text (str): 변환할 텍스트
            voice (str, optional): 음성 이름 (예: 'Kore').
                                 기본값은 .env의 GEMINI_TTS_VOICE 또는 "Kore"
            model (str, optional): TTS 모델
                                 기본값은 .env의 GEMINI_TTS_MODEL 또는 "models/gemini-2.5-pro-preview-tts"
            max_retries (int): 최대 재시도 횟수
            
        Returns:
            bytes: WAV 형식의 음성 데이터
        """
        if voice is None:
            voice = os.getenv('GEMINI_TTS_VOICE', VoiceOptions.DEFAULT)
            print(f"🗣️  TTS 음성: {voice}")
        if model is None:
            model = os.getenv('GEMINI_TTS_MODEL', ModelOptions.DEFAULT)
            print(f"🎵 TTS 모델: {model}")
        
        # 프롬프트 엔지니어링 대신 텍스트를 직접 사용합니다.
        prompt = text

        for attempt in range(max_retries):
            try:
                tts_model = self.client.GenerativeModel(model)
                
                # 사용자의 샘플 코드를 기반으로 generation_config를 재구성합니다.
                # 이 preview 모델은 특별한 요청 구조가 필요합니다.
                generation_config = {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {
                                "voice_name": voice
                            }
                        }
                    }
                }

                response = tts_model.generate_content(
                    contents=[prompt],
                    generation_config=generation_config
                )
                
                # 응답에서 오디오 데이터 추출
                if response.parts:
                    return response.parts[0].inline_data.data
                elif response.candidates:
                    return response.candidates[0].content.parts[0].inline_data.data
                else:
                    raise ValueError("응답에서 오디오 데이터를 찾을 수 없습니다.")

            except Exception as e:
                if attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f"Gemini TTS 요청 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                    print(f"{sleep_time:.1f}초 후 재시도...")
                    time.sleep(sleep_time)
                else:
                    raise Exception(f"Gemini TTS 요청이 {max_retries}번 모두 실패했습니다: {e}")

    def synthesize_to_file(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        텍스트를 음성으로 변환하여 파일로 저장합니다.
        
        Args:
            text (str): 변환할 텍스트
            output_path (str): 출력 파일 경로
            voice (str, optional): 음성 스타일 (기본값은 .env의 GEMINI_TTS_VOICE_STYLE)
            model (str, optional): TTS 모델 (기본값은 .env의 GEMINI_TTS_MODEL)
        """
        try:
            wav_data = self.synthesize_speech(text, voice, model)
            
            with wave.open(output_path, "wb") as wf:
                wf.setnchannels(1)       # 모노 채널
                wf.setsampwidth(2)        # 16-bit 샘플
                wf.setframerate(24000)    # 24kHz 샘플레이트
                wf.writeframes(wav_data)
            
        except Exception as e:
            print(f"Gemini TTS 파일 저장 실패: {e}")
            raise

    def synthesize_multispeaker_speech(
        self,
        text: str,
        speaker_voices: list[dict[str, str]],
        model: Optional[str] = None,
        max_retries: int = 10
    ) -> bytes:
        """
        다중 화자 텍스트를 음성으로 변환합니다.
        
        Args:
            text (str): 변환할 대화 텍스트
            speaker_voices (list[dict[str, str]]): 화자와 음성 매핑 리스트. 
                                                   예: [{'speaker': 'Joe', 'voice': 'Kore'}]
            model (str, optional): TTS 모델. 기본값은 .env의 GEMINI_TTS_MODEL
            max_retries (int): 최대 재시도 횟수
            
        Returns:
            bytes: WAV 형식의 음성 데이터
        """
        if model is None:
            model = os.getenv('GEMINI_TTS_MODEL', ModelOptions.DEFAULT)
        
        prompt = text

        speaker_voice_configs = []
        for item in speaker_voices:
            speaker_voice_configs.append({
                "speaker": item['speaker'],
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": item['voice']
                    }
                }
            })

        for attempt in range(max_retries):
            try:
                tts_model = self.client.GenerativeModel(model)
                
                generation_config = {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "multi_speaker_voice_config": {
                            "speaker_voice_configs": speaker_voice_configs
                        }
                    }
                }

                response = tts_model.generate_content(
                    contents=[prompt],
                    generation_config=generation_config
                )
                
                if response.parts:
                    return response.parts[0].inline_data.data
                elif response.candidates:
                    return response.candidates[0].content.parts[0].inline_data.data
                else:
                    raise ValueError("응답에서 오디오 데이터를 찾을 수 없습니다.")

            except Exception as e:
                if attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f"Gemini 다중 화자 TTS 요청 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                    print(f"{sleep_time:.1f}초 후 재시도...")
                    time.sleep(sleep_time)
                else:
                    raise Exception(f"Gemini 다중 화자 TTS 요청이 {max_retries}번 모두 실패했습니다: {e}")

    def synthesize_multispeaker_to_file(
        self,
        text: str,
        output_path: str,
        speaker_voices: list[dict[str, str]],
        model: Optional[str] = None
    ):
        """
        다중 화자 텍스트를 음성으로 변환하여 파일로 저장합니다.
        
        Args:
            text (str): 변환할 대화 텍스트
            output_path (str): 출력 파일 경로
            speaker_voices (list[dict[str, str]]): 화자와 음성 매핑 리스트.
            model (str, optional): TTS 모델.
        """
        try:
            wav_data = self.synthesize_multispeaker_speech(text, speaker_voices, model)
            
            with wave.open(output_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(wav_data)
            
        except Exception as e:
            print(f"Gemini 다중 화자 TTS 파일 저장 실패: {e}")
            raise


def get_gemini_tts_client(api_key: Optional[str] = None) -> GeminiTTSClient:
    """
    Gemini TTS 클라이언트를 생성합니다.
    
    Args:
        api_key (str, optional): Google API 키
        
    Returns:
        GeminiTTSClient: 초기화된 클라이언트
    """
    try:
        return GeminiTTSClient(api_key)
    except Exception as e:
        print(f"Gemini TTS 클라이언트 생성 실패: {e}")
        raise

# 음성 옵션 상수
class VoiceOptions:
    """사용 가능한 Gemini TTS 음성 옵션들"""
    
    # 사용자의 샘플을 기반으로 음성 이름 설정
    KORE = "Kore"
    PUCK = "Puck"
    
    DEFAULT = KORE

# 모델 옵션
class ModelOptions:
    """사용 가능한 TTS 모델들"""
    
    # 사용자가 제공한 TTS 프리뷰 모델
    GEMINI_2_5_PRO_TTS = "models/gemini-2.5-pro-preview-tts" 
    
    DEFAULT = GEMINI_2_5_PRO_TTS
