from utils.transform_video import extract_silent_video_and_silent_audio, merge_video_audio
from utils.transform_subtitle import text_to_audio, make_new_subtitles, remove_dir
from utils.transform_audio import text_to_speech, merge_audio_files
from pathlib import Path
import pysrt
import torch

############################## gpu 연결 ##############################
device = 'cuda:0' if torch.cuda.is_available() else 'cpu'

# 입력 파일 경로
source_folder_path = Path('/dubbing/source')
source_video_paths = sorted(list(source_folder_path.glob('*.mp4')), key=lambda x: x.name)
source_caption_paths = sorted(list(source_folder_path.glob('*.srt')), key=lambda x: x.name)
output_folder_path = Path('/dubbing/output')


############################## 무음 영상, 무음 wav 추출 ##############################
silent_folder_path = Path('/dubbing/content/silent')
for idx, source_video_path in enumerate(source_video_paths):
    extract_silent_video_and_silent_audio(source_video_path, silent_folder_path)
print('silent video extract complete')

silent_audio_paths = sorted(list(silent_folder_path.glob('*.wav')), key=lambda x: x.name)
silent_video_paths = sorted(list(silent_folder_path.glob('*.mp4')), key=lambda x: x.name)

# ############################## 자막 전처리 ##############################

for lec, source_caption_path in enumerate(source_caption_paths):

    # 소스 자막 파일 읽기
    subtitles = pysrt.open(source_caption_path, encoding='utf-8-sig')

    # 소스 자막파일의 index 갯수대로 tts 파일 만들기,
    # content/tts: 자막 조각들, data_: tts 조각에 대한 정보 (index, start, end, audio_length, text)
    data_ = text_to_audio(subtitles, lec+1)

    # 자막조각의 합으로 이루어진 list 만들기 [[자막1, 자막2],[자막3],[자막4, 자막5, 자막6]]
    new_subtitles = make_new_subtitles(data_, subtitles, lec+1, UPPERBOUND=1.3)
    
    # 기존 tts 파일 삭제
    remove_dir('/dubbing/content/tts')

    # new_subtitle 기반으로 다시 content/tts에 저장하고, 배속 걸어야 하는 구간을 다시 체크하여, 다시 tts 돌려서 final에 저장
    text_to_speech(new_subtitles, lec+1)

    # 오디오 파일을 new_subtitles의 각 [자막그룹]의 첫번째 자막의 start 타임 위치에 올리기
    # output/raw에 완성 파일 저장  / lec단위
    merge_audio_files(new_subtitles, lec+1, silent_audio_paths[lec])

    # 저장된 합성 오디오 파일 경로 읽기
    tmp_audio_folder_path = output_folder_path / 'raw'
    output_audio_file_paths = sorted(list(tmp_audio_folder_path.glob('*_en.wav')),key=lambda x: x.name)

    # 음성과 영상 합성
    merge_video_audio(source_video_paths[lec],output_audio_file_paths[lec], output_folder_path)