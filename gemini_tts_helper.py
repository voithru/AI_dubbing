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
import tempfile
import pydub
from typing import Optional
from dotenv import load_dotenv
from token_tracker import get_token_tracker

# 글로벌 클라이언트 인스턴스
_global_client: Optional['GeminiTTSClient'] = None

class GeminiTTSClient:
    """Gemini TTS 클라이언트"""
    
    def __init__(self, api_key: Optional[str] = None, verbose: bool = True):
        """
        Gemini TTS 클라이언트를 초기화합니다.
        
        Args:
            api_key (str, optional): Google API 키. 
                                   기본값은 .env 파일 또는 환경변수 GOOGLE_API_KEY
            verbose (bool): 초기화 메시지 출력 여부
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
        if verbose:
            print("✅ Gemini TTS 클라이언트가 초기화되었습니다.")

    def synthesize_speech(
        self,
        text: str,
        voice: Optional[str] = None, # voice 매개변수는 현재 API에서 직접 사용되지 않을 수 있습니다.
        model: Optional[str] = None,
        max_retries: int = 10,
        video_name: Optional[str] = None  # 비용 추적을 위한 영상 이름
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
            voice = os.getenv('GEMINI_TTS_VOICE')
            if not voice:
                raise ValueError(
                    "GEMINI_TTS_VOICE가 설정되지 않았습니다.\n"
                    ".env 파일에 GEMINI_TTS_VOICE=Kore (또는 다른 음성) 설정을 추가하세요."
                )
        if model is None:
            model = os.getenv('GEMINI_TTS_MODEL')
            if not model:
                raise ValueError(
                    "GEMINI_TTS_MODEL이 설정되지 않았습니다.\n"
                    ".env 파일에 GEMINI_TTS_MODEL=gemini-2.5-pro-preview-tts 설정을 추가하세요."
                )
        
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
                
                # 토큰 사용량 추적
                if video_name and hasattr(response, 'usage_metadata'):
                    try:
                        # Gemini API에서 토큰 사용량 정보 추출
                        usage_metadata = response.usage_metadata
                        input_tokens = getattr(usage_metadata, 'prompt_token_count', 0)
                        output_tokens = getattr(usage_metadata, 'candidates_token_count', 0)
                        
                        # 출력 토큰이 없는 경우 텍스트 길이 기반으로 추정
                        if output_tokens == 0:
                            # TTS의 경우 오디오 생성이므로 텍스트 길이 기반으로 추정
                            output_tokens = max(1, len(text) // 4)  # 대략적인 추정
                        
                        # 토큰 추적기에 기록
                        tracker = get_token_tracker()
                        tracker.add_token_usage(
                            video_name=video_name,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            model=model,
                            text_length=len(text)
                        )
                    except Exception as token_error:
                        print(f"⚠️ 토큰 사용량 추적 실패: {token_error}")
                
                # 응답에서 오디오 데이터 추출 (안전한 방식)
                try:
                    # 첫 번째 방법: response.parts에서 직접 추출
                    if hasattr(response, 'parts') and response.parts and len(response.parts) > 0:
                        part = response.parts[0]
                        if hasattr(part, 'inline_data') and hasattr(part.inline_data, 'data'):
                            return part.inline_data.data
                    
                    # 두 번째 방법: response.candidates에서 추출
                    if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                        candidate = response.candidates[0]
                        print(f"🔍 candidate 타입: {type(candidate)}")
                        
                        if hasattr(candidate, 'content'):
                            content = candidate.content
                            print(f"🔍 content 타입: {type(content)}")
                            print(f"🔍 hasattr(content, 'parts'): {hasattr(content, 'parts')}")
                            
                            if hasattr(content, 'parts') and content.parts:
                                print(f"🔍 content.parts 길이: {len(content.parts)}")
                                if len(content.parts) > 0:
                                    part = content.parts[0]
                                    print(f"🔍 part 타입: {type(part)}")
                                    print(f"🔍 hasattr(part, 'inline_data'): {hasattr(part, 'inline_data')}")
                                    
                                    if hasattr(part, 'inline_data') and part.inline_data:
                                        print(f"🔍 inline_data 타입: {type(part.inline_data)}")
                                        print(f"🔍 hasattr(inline_data, 'data'): {hasattr(part.inline_data, 'data')}")
                                        
                                        if hasattr(part.inline_data, 'data'):
                                            return part.inline_data.data
                    
                    # 디버깅을 위한 응답 구조 출력
                    print(f"🔍 디버그: API 응답 구조 분석")
                    print(f"   - response 타입: {type(response)}")
                    print(f"   - hasattr(response, 'parts'): {hasattr(response, 'parts')}")
                    print(f"   - hasattr(response, 'candidates'): {hasattr(response, 'candidates')}")
                    
                    if hasattr(response, 'parts'):
                        print(f"   - response.parts 길이: {len(response.parts) if response.parts else 0}")
                    if hasattr(response, 'candidates'):
                        print(f"   - response.candidates 길이: {len(response.candidates) if response.candidates else 0}")
                    
                    raise ValueError("응답에서 오디오 데이터를 찾을 수 없습니다.")
                    
                except (IndexError, AttributeError) as extract_error:
                    print(f"🔍 오디오 데이터 추출 오류: {extract_error}")
                    print(f"   응답 타입: {type(response)}")
                    raise ValueError(f"오디오 데이터 추출 실패: {extract_error}")

            except Exception as e:
                if attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f"Gemini TTS 요청 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                    print(f"  에러 타입: {type(e).__name__}")
                    print(f"  텍스트 길이: {len(text)} 문자")
                    print(f"  모델: {model}")
                    print(f"  음성: {voice}")
                    print(f"{sleep_time:.1f}초 후 재시도...")
                    time.sleep(sleep_time)
                else:
                    print(f"❌ Gemini TTS 요청이 {max_retries}번 모두 실패했습니다.")
                    print(f"   최종 에러: {e}")
                    print(f"   에러 타입: {type(e).__name__}")
                    print(f"   텍스트: '{text[:100]}...' ({len(text)} 문자)")
                    raise Exception(f"Gemini TTS 요청이 {max_retries}번 모두 실패했습니다: {e}")

    def synthesize_to_file(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        target_sample_rate: int = 44100,
        video_name: Optional[str] = None
    ):
        """
        텍스트를 음성으로 변환하여 파일로 저장합니다.
        
        Args:
            text (str): 변환할 텍스트
            output_path (str): 출력 파일 경로
            voice (str, optional): 음성 스타일 (기본값은 .env의 GEMINI_TTS_VOICE_STYLE)
            model (str, optional): TTS 모델 (기본값은 .env의 GEMINI_TTS_MODEL)
            target_sample_rate (int): 목표 샘플레이트 (기본값: 44100)
        """
        try:
            wav_data = self.synthesize_speech(text, voice, model, video_name=video_name)
            
            if target_sample_rate == 24000:
                # 24kHz 그대로 저장
                with wave.open(output_path, "wb") as wf:
                    wf.setnchannels(1)       # 모노 채널
                    wf.setsampwidth(2)        # 16-bit 샘플
                    wf.setframerate(24000)    # 24kHz 샘플레이트
                    wf.writeframes(wav_data)
            else:
                # 샘플레이트 변환 필요
                import tempfile
                import pydub
                from io import BytesIO
                
                # 임시 24kHz WAV 파일 생성
                with tempfile.NamedTemporaryFile(suffix='.wav') as tmp_wav:
                    with wave.open(tmp_wav.name, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(wav_data)
                    
                    # pydub으로 샘플레이트 변환
                    audio_segment = pydub.AudioSegment.from_file(tmp_wav.name, format='wav')
                    audio_segment = audio_segment.set_frame_rate(target_sample_rate)
                    audio_segment.export(output_path, format='wav')
            
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


def get_gemini_tts_client(api_key: Optional[str] = None, force_new: bool = False) -> GeminiTTSClient:
    """
    Gemini TTS 클라이언트를 생성하거나 기존 클라이언트를 반환합니다.
    
    Args:
        api_key (str, optional): Google API 키
        force_new (bool): True면 새 클라이언트를 강제로 생성
        
    Returns:
        GeminiTTSClient: 초기화된 클라이언트
    """
    global _global_client
    
    if _global_client is None or force_new:
        try:
            verbose = _global_client is None  # 최초 생성시에만 메시지 출력
            _global_client = GeminiTTSClient(api_key, verbose=verbose)
            
            if verbose:
                # 최초 생성시 설정 정보 출력
                load_dotenv()
                tts_model = os.getenv('GEMINI_TTS_MODEL')
                tts_voice = os.getenv('GEMINI_TTS_VOICE')
                
                if not tts_model:
                    raise ValueError(
                        "GEMINI_TTS_MODEL이 설정되지 않았습니다.\n"
                        ".env 파일에 GEMINI_TTS_MODEL=gemini-2.5-pro-preview-tts 설정을 추가하세요."
                    )
                if not tts_voice:
                    raise ValueError(
                        "GEMINI_TTS_VOICE가 설정되지 않았습니다.\n"
                        ".env 파일에 GEMINI_TTS_VOICE=Kore 설정을 추가하세요."
                    )
                
                print(f"🎵 TTS 모델: {tts_model}")
                print(f"🗣️  TTS 음성: {tts_voice}")
                
        except Exception as e:
            print(f"Gemini TTS 클라이언트 생성 실패: {e}")
            raise
    
    return _global_client


def reset_gemini_client():
    """글로벌 클라이언트를 리셋합니다."""
    global _global_client
    _global_client = None

# 음성 옵션 상수 (참고용)
class VoiceOptions:
    """사용 가능한 Gemini TTS 음성 옵션들 (참고용 - 실제로는 .env 파일에서 설정)"""
    
    # 사용 가능한 음성들 (참고용)
    KORE = "Kore"
    PUCK = "Puck"
    # 주의: 실제 사용시에는 .env 파일의 GEMINI_TTS_VOICE 설정을 사용합니다

# 모델 옵션 (참고용)
class ModelOptions:
    """사용 가능한 TTS 모델들 (참고용 - 실제로는 .env 파일에서 설정)"""
    
    # 사용 가능한 모델들 (참고용)
    GEMINI_2_5_PRO_TTS = "gemini-2.5-pro-preview-tts"
    # 주의: 실제 사용시에는 .env 파일의 GEMINI_TTS_MODEL 설정을 사용합니다
