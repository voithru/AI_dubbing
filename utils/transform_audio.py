from tqdm import tqdm
from utils.transform_subtitle import tts_to_file_polly, time_stretch_with_ssml, save_speed_info
import pysrt
import librosa
import os
from pydub import AudioSegment
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from configure import base_dir  # base_dir import 추가

def text_to_speech(new_subtitles, lec, max_workers=15):
    def process_subtitle(i, subtitle_list):
        if i == 0:
            return
        start_tc = subtitle_list[0].start
        end_tc = subtitle_list[-1].end
        text = ' '.join([line.text for line in subtitle_list])

        tts_to_file_polly(text, i, lec)  # output tts/index.wav

        tc_length = (end_tc - start_tc).minutes * 60 + (end_tc - start_tc).seconds + (end_tc - start_tc).milliseconds * 1e-3
        audio, sr = librosa.load(f'{base_dir}/content/tts/{lec}_{i}.wav', sr=44100)
        audio_length = len(audio) / sr

        speed = audio_length / tc_length

        if speed > 1.:
            if i + 1 < len(new_subtitles) and new_subtitles[i + 1][0].start - end_tc > pysrt.SubRipTime(0, 0, 0, 50):
                end_tc = new_subtitles[i + 1][0].start - pysrt.SubRipTime(0, 0, 0, 50)
                tc_length = (end_tc - start_tc).minutes * 60 + (end_tc - start_tc).seconds + (end_tc - start_tc).milliseconds * 1e-3
                speed = audio_length / tc_length

        input_path = f'{base_dir}/content/tts/{lec}_{i}.wav'
        output_path = f'{base_dir}/content/final/{lec}_{i}.wav'

        time_stretch_with_ssml(tts_to_file_polly, text, i, lec, (round(speed + 0.1, 2) if speed > 1.0 else 1.0), f'{base_dir}/content/final')

        orig_audio_data, sr = librosa.load(input_path, sr=44100)
        speed = (len(orig_audio_data) / sr) / tc_length

        if speed > 1.0:
            applied_speed = min(speed, 1.99)
            time_stretch_with_ssml(tts_to_file_polly, text, i, lec, applied_speed, f'{base_dir}/content/final')

            if speed >= 1.5:
                save_speed_info(lec, subtitle_list[0].start, speed)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_subtitle, i, subtitle_list): i for i, subtitle_list in enumerate(new_subtitles)}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing subtitles"):
            future.result()

def merge_audio_files(new_subtitles, lec, silent_audio_path):
    background = AudioSegment.from_wav(silent_audio_path)
    f = lambda x: (3600*x.hours + 60*x.minutes + x.seconds)*1000 + x.milliseconds

    dubbed_audio = background

    # 모든 오디오 파일을 미리 로드
    audio_segments = []
    for ids, subtitle_list in enumerate(new_subtitles):
        if ids < 1: continue
        # 콜로소 더빙시 <= 1, 일반영상은 < 1
        voice_path = f'{base_dir}/content/final/{lec}_{ids}.wav'
        if os.path.exists(voice_path):
            voice = AudioSegment.from_wav(voice_path)
            start = f(subtitle_list[0].start)
            audio_segments.append((voice, start))

    # 오디오 파일을 한 번에 병합
    for voice, start in tqdm(audio_segments, desc='음성 합성'):
        dubbed_audio = dubbed_audio.overlay(voice, position=start)

    file_name_with_ext = os.path.basename(silent_audio_path)
    file_name = os.path.splitext(file_name_with_ext)[0].replace('_silent_audio', '')

    # 완성 파일 출력 시작
    if dubbed_audio.channels == 1:
        stereo_audio = dubbed_audio.set_channels(2)
        stereo_audio.export(f'{base_dir}/content/final_audio/{file_name}_en.wav', 'wav')
    else:
        dubbed_audio.export(f'{base_dir}/content/final_audio/{file_name}_en.wav', 'wav')
    # 완성 파일 출력 완료