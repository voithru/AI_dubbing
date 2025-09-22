# 자막 파일을 ai더빙한 데이터를 받아와서
# wav 파일로 변환
import pysrt
import os
import librosa
from tqdm import tqdm
from io import BytesIO
import pydub
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
from pathlib import Path
from configure import base_dir  # base_dir import 추가
from gemini_tts_helper import get_gemini_tts_client, VoiceOptions  # Gemini TTS 헬퍼 추가

def text_to_audio(subtitles, idx, max_workers=5, video_name=None):
    data_ = []

    def process_subtitle(subtitle, ids):
        text = subtitle.text
        time_stretch(
            tts_func=tts_to_file_gemini,
            text=text,
            index=ids,
            idx=idx,
            speed=1.1,
            video_name=video_name
        )
        audio, sr = librosa.load(f'{base_dir}/content/tts/{idx}_{ids}.wav', sr=44100)
        return [subtitle.index, subtitle.start, subtitle.end, len(audio) / sr, subtitle.text]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_subtitle, subtitle, ids): ids for ids, subtitle in enumerate(subtitles)}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing subtitles"):
            data_.append(future.result())

    return data_

def tts_to_file_gemini(text, index, idx, output_dir=None, video_name=None):
    if output_dir is None:
        output_dir = f'{base_dir}/content/tts'
    
    # Gemini TTS 클라이언트 생성
    try:
        client = get_gemini_tts_client()
    except Exception as e:
        print(f"Gemini TTS 인증 오류: {e}")
        raise

    # 텍스트 정제 (SSML 태그 제거 및 순수 텍스트 추출)
    import re  # 정규식 모듈
    
    def clean_text_for_tts(input_text):
        # 모든 SSML/HTML 태그 제거
        clean_content = re.sub(r'<[^>]+>', '', input_text)
        
        # 특수문자 정제
        clean_content = clean_content.replace("&", "and")  # & 문자 처리
        clean_content = clean_content.replace("  ", " ")   # 연속 공백 제거
        
        return clean_content.strip()
    
    cleaned_text = clean_text_for_tts(text)
    
    print(f"🔧 텍스트 정제: '{text[:50]}...' → '{cleaned_text[:50]}...'")
    
    # 텍스트 길이 검증
    if len(cleaned_text) < 1:
        print(f"⚠️ 텍스트가 너무 짧습니다: '{cleaned_text}'")
        cleaned_text = "음성을 생성할 수 없습니다."
    
    try:
        # 출력 파일 경로
        wav_file_path = f"{output_dir}/{idx}_{index}.wav"
        
        # Gemini TTS API 호출하여 직접 파일로 저장 (순수 텍스트 전달)
        client.synthesize_to_file(
            text=cleaned_text,  # SSML 없는 순수 텍스트
            output_path=wav_file_path,
            voice=None,  # .env 파일의 GEMINI_TTS_VOICE 사용
            target_sample_rate=44100,
            video_name=video_name
        )
            
    except Exception as e:
        print(f"❌ Gemini TTS 음성 합성 실패: {e}")
        print(f"   실패한 텍스트: '{text[:100]}...'")
        print(f"   정제된 텍스트: '{cleaned_text[:100]}...'")
        
        # 실패시 빈 오디오 파일 생성 (처리 중단 방지)
        try:
            import wave
            import numpy as np
            
            # 1초간의 무음 파일 생성
            sample_rate = 44100
            duration = 1.0
            silence = np.zeros(int(sample_rate * duration), dtype=np.int16)
            
            with wave.open(wav_file_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(silence.tobytes())
            
            print(f"🔇 대체 무음 파일 생성: {wav_file_path}")
            
        except Exception as fallback_error:
            print(f"⚠️ 대체 파일 생성도 실패: {fallback_error}")
            raise e  # 원래 오류를 다시 발생

def time_stretch(tts_func, text, index, idx, speed, output_dir=f'{base_dir}/content/tts', video_name=None):
    # 순수 텍스트만 전달 (SSML 제거)
    # 속도 조절은 Gemini TTS 자체 기능이나 후처리에서 처리
    print(f"🎵 속도 조절: {speed}배속 (현재는 순수 텍스트로 처리)")
    tts_func(text, index, idx, output_dir, video_name=video_name)

def remove_dir(output_dir=None):
    if output_dir is None:
        output_dir = f'{base_dir}/content/tts'
    for filename in os.listdir(output_dir):
        os.remove(f'{output_dir}/{filename}')


def merge_subtitles(data, subtitles, interval):
    # 데이터가 시간 순서대로 정렬되었는지 확인
    data.sort(key=lambda x: x[1])  # 시작 시간을 기준으로 정렬

    new_subtitles = [[subtitles[0]]]
    subtitle_list = []

    for idx, start, end, audio_length, text in data:
        tc_length = (end - start).seconds + (end - start).milliseconds * 1e-3

        if audio_length < tc_length:
            m, s = divmod(audio_length, 60)
            s, ms = divmod(s, 1)
            audio_length = pysrt.SubRipTime(0, m, s, round(ms * 1e3, 1))
            end = start + audio_length

        sub = pysrt.SubRipItem(index=idx, start=start, end=end, text=text)

        if not subtitle_list:
            subtitle_list.append(sub)
        else:
            prev_end = subtitle_list[-1].end
            gap = (sub.start - prev_end).seconds + (sub.start - prev_end).milliseconds * 1e-3
            current_tc_length = (sub.end - subtitle_list[0].start).seconds + (sub.end - subtitle_list[0].start).milliseconds * 1e-3

            # 문장의 끝이 마침표, 물음표, 느낌표로 끝나면 그룹 종료
            if subtitle_list[-1].text.endswith(('.', '?', '!')):
                new_subtitles.append(subtitle_list)
                subtitle_list = [sub]
            # 마침표로 끝나지 않고, 타임코드의 합계가 7초가 되지 않으며, 간격이 interval초 미만이면 병합
            elif current_tc_length < 7 and gap < interval:
                subtitle_list.append(sub)
            else:
                new_subtitles.append(subtitle_list)
                subtitle_list = [sub]

    if subtitle_list:
        new_subtitles.append(subtitle_list)

    return new_subtitles

def make_new_subtitles(data_, subtitles, lec, UPPERBOUND):
    interval = 1.5  # 초기 간격을 1.5로 설정
    optimized_subtitles = None  # 최적화된 자막을 저장할 변수

    for _ in range(10):
        interval += 0.1  # 간격을 0.1초씩 증가
        new_subtitles = merge_subtitles(data_, subtitles, interval)
        flag = True

        for i, subtitle_list in enumerate(new_subtitles):
            tc_length = (subtitle_list[-1].end - subtitle_list[0].start).seconds + (subtitle_list[-1].end - subtitle_list[0].start).milliseconds * 1e-3
            total_audio_length = 0
            for line in subtitle_list:
                audio, sr = librosa.load(f'{base_dir}/content/tts/{lec}_{line.index-1}.wav', sr=44100)
                total_audio_length += len(audio) / sr

            if total_audio_length / tc_length > UPPERBOUND:
                flag = False
                break

        if flag:
            optimized_subtitles = new_subtitles  # 최적화된 자막을 저장
            break

    final_subtitles = optimized_subtitles if optimized_subtitles else new_subtitles
    save_subtitles_to_srt(final_subtitles, f'{base_dir}/output/{lec}_new.srt')

    return final_subtitles

def save_subtitles_to_srt(subtitles, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, subtitle_list in enumerate(subtitles):
            # 그룹 시작 주 추가
            f.write(f"### Group {i+1} Start ###\n")
            
            for sub in subtitle_list:
                f.write(f"{sub.text}\n")
            
            # 그룹 끝 주석 추가
            f.write(f"### Group {i+1} End ###\n\n")

def save_speed_info(lec, start_tc, speed):
    output_path = f'{base_dir}/output/speed_over.txt'
    
    with open(output_path, 'a') as f:
        # 파일이 비어있지 않다면 새 줄 추가
        f.seek(0, 2)  # 파일 끝으로 이동
        if f.tell() > 0:  # 파일이 비어있지 않으면
            f.write('\n')
        f.write(f'lec : {lec}\nstart tc : {start_tc}\nspeed : {speed}\n')

def save_log_video (video_path, output_log_path):
    video_name_with_ext = os.path.basename(video_path)
    video_name = os.path.splitext(video_name_with_ext)[0]

    with open(output_log_path, 'a') as f:
        # 파일이 비어있지 않다면 새 줄 추가
        f.seek(0, 2)  # 파일 끝으로 이동
        if f.tell() > 0:  # 파일이 비어있지 않으면
            f.write('\n')
        f.write(f'video name : {video_name}\n')