# 자막 파일을 ai더빙한 데이터를 받아와서
# wav 파일로 변환
import boto3
import botocore
from botocore.config import Config
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

def text_to_audio(subtitles, idx, max_workers=5):
    data_ = []

    def process_subtitle(subtitle, ids):
        text = subtitle.text
        time_stretch_with_ssml(
            tts_func=tts_to_file_polly,
            text=text,
            index=ids,
            idx=idx,
            speed=1.1
        )
        audio, sr = librosa.load(f'{base_dir}/content/tts/{idx}_{ids}.wav', sr=44100)
        return [subtitle.index, subtitle.start, subtitle.end, len(audio) / sr, subtitle.text]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_subtitle, subtitle, ids): ids for ids, subtitle in enumerate(subtitles)}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing subtitles"):
            data_.append(future.result())

    return data_

def tts_to_file_polly(text, index, idx, output_dir=None):
    if output_dir is None:
        output_dir = f'{base_dir}/content/tts'
    # 환경 변수에서 AWS 키 가져오기
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID_polly')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY_polly')

    # RetryConfig 설정
    retry_config = Config(
        retries={
            'max_attempts': 10,  # 최대 재시도 횟수
            'mode': 'standard'   # 재시도 모드 ('standard' 또는 'adaptive')
        },
        connect_timeout=10,
        read_timeout=60
    )

    client = boto3.client(
        service_name='polly',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name='ap-northeast-2',
        config=retry_config  # RetryConfig 적용
    )

    for attempt in range(10):  # 최대 10번 재시도
        try:
            response = client.synthesize_speech(
                Text=f"""<speak>{text.replace("&","N")}</speak>""",
                LanguageCode=('en-US'),
                Engine='neural',
                TextType='ssml',
                OutputFormat='mp3',
                VoiceId=('Ruth'),
                SampleRate='22050'
            )
            # 성공 시 루프 탈출
            break
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                # 지수 백오프 적용
                sleep_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(sleep_time)
            else:
                raise  # 다른 오류는 다시 발생시킴

    # 임시 파일에 mp3 데이터를 저장
    wav_file_path = f"{output_dir}/{idx}_{index}.wav"

    pydub.AudioSegment\
        .from_file(BytesIO(b''.join(response.get('AudioStream'))))\
        .set_frame_rate(44100)\
        .export(f'{wav_file_path}', format='wav')

def time_stretch_with_ssml(tts_func, text, index, idx, speed, output_dir='/Users/p-156/dev/dubbing/content/tts'):
    speed = int('{:.2f}'.format(speed).split('.')[-1])
    text = f"""<prosody rate="+{speed}%">{text}</prosody>"""
    tts_func(text, index, idx, output_dir)

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