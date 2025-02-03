import os
from pydub import AudioSegment
from moviepy.editor import VideoFileClip
from pathlib import Path
import subprocess
from configure import base_dir  # base_dir import 추가

def extract_silent_video_and_silent_audio(input_video_path, output_folder_path):
    input_video_path = Path(input_video_path)
    output_folder_path = Path(output_folder_path)

    clip = VideoFileClip(str(input_video_path))
    duration = clip.duration
    base_name = input_video_path.stem

    output_video_path = output_folder_path / f'{base_name}_silent_video.mp4'
    output_audio_path = output_folder_path / f'{base_name}_silent_audio.wav'

    print("무음 음성 추출 시작")
    # 무음 wav 파일 저장
    silent_audio = AudioSegment.silent(duration=duration*1000).set_frame_rate(44100)
    silent_audio.export(str(output_audio_path), format="wav")

    print("무음 영상 만들기 시작")

    video_command = [
        'ffmpeg',
        '-i', input_video_path,  # 입력 비디오 파일
        '-an',                   # 오디오 스트림 제거
        '-vcodec', 'copy',       # 비디오 스트림은 그대로 복사
        output_video_path        # 출력 비디오 파일
    ]
    subprocess.run(video_command, check=True)

def merge_video_audio(video_path, audio_path, output_folder_path):
    video_name_with_ext = os.path.basename(video_path)
    video_name = os.path.splitext(video_name_with_ext)[0]
    output_video_path = Path(f'{output_folder_path}/{video_name}_en.mp4')
    output_audio_path = Path(f'{output_folder_path}/{video_name}_en.wav')

    origin_background_audio = Path(f'{base_dir}/content/final_audio/{video_name}_0.wav')
    dubbed_muted_audio = Path(f'{base_dir}/content/final_audio/{video_name}_55.wav')

    # subprocess.run([
    #         "ffmpeg", 
    #         "-i", video_path,                # 입력 파일로 첫 번째 비디오 파일 지정
    #         "-ss", "0",                      # 시작 시간을 0초로 설정
    #         "-t", "5.5",                     # 5.5초 길이의 음성만 추출
    #         "-q:a", "0",                     # 오디오 퀄리티를 최대화 (원본 퀄리티 유지)
    #         "-map", "a",                     # 오디오 스트림만 선택
    #         origin_background_audio          # 출력 파일로 temp_audio.wav 지정
    #     ], check=True)

    subprocess.run([
            "ffmpeg", 
            "-ss", "0",                    # 시작 시간을 5.5초로 설정 (5.5초 이후의 음성 추출) --> 일반 영상은 0부터
            "-i", str(audio_path),           # 입력 파일로 두 번째 오디오 파일 지정 (wav 파일)
            "-q:a", "0",                     # 오디오 퀄리티를 최대화 (원본 퀄리티 유지)
            "-map", "0:a",
            "-c:a", "copy",
            # dubbed_muted_audio               # 출력 파일로 temp_combined_audio.wav 지정
            output_audio_path              #### 일반 영상 전용
        ], check=True)
    
    # subprocess.run([
    #     "ffmpeg",
    #     "-i", origin_background_audio,        # 첫 번째 입력 파일 지정
    #     "-i", dubbed_muted_audio,             # 두 번째 입력 파일 지정
    #     "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",  # 두 오디오 스트림 연결
    #     "-map", "[out]",                      # 필터 출력 스트림 선택
    #     output_audio_path                     # 출력 파일 지정
    # ], check=True)

    subprocess.run([
        "ffmpeg", 
        "-i", str(video_path),                 # 입력 파일로 비디오 파일 지정
        "-i", str(output_audio_path),          # 입력 파일로 합성된 오디오 파일 지정
        "-map", "0:v",                         # 첫 번째 입력에서 비디오 스트림 선택
        "-map", "1:a",                         # 두 번째 입력에서 오디오 스트림 선택
        "-c:v", "copy",                        # 비디오는 인코딩 없이 복사
        "-c:a", "aac",                         # 오디오는 AAC 코덱으로 인코딩
        "-shortest",                           # 비디오와 오디오 길이가 다를 때, 짧은 쪽에 맞춤
        str(output_video_path)                 # 최종 출력 파일 이름 지정
    ], check=True)

