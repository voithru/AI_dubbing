# 자막 파일을 ai더빙한 데이터를 받아와서
# wav 파일로 변환
import boto3
import pysrt
import os
import librosa
from tqdm import tqdm
from io import BytesIO
import pydub

def text_to_audio(subtitles, idx):
    data_ = []
    for ids, subtitle in tqdm(enumerate(subtitles), total=len(subtitles), bar_format="{l_bar}{bar} | {n_fmt}/{total_fmt} [{percentage:.2f}%]"):

        text = subtitle.text
        # if text.endswith('[~]'):
        #     text = text[:-3] + '?'

        time_stretch_with_ssml(
            tts_func=tts_to_file_polly,
            text=text.replace('[~]','').replace('[!]',''),
            index=ids,
            idx=idx,
            speed=1.1
            )

        audio, sr = librosa.load(f'/dubbing/content/tts/{idx}_{ids}.wav', sr=44100)

        data_.append([subtitle.index, subtitle.start, subtitle.end, len(audio) / sr, subtitle.text])
    return data_

def tts_to_file_polly(text, index, idx, output_dir='/dubbing/content/tts'):
    if text.endswith('#'):
        text = text[:-1]

    AWS_ACCESS_KEY_ID = '' # aws key
    AWS_SECRET_ACCESS_KEY = '' # aws secret
    client = boto3.client(service_name='polly',aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY,region_name='ap-northeast-2')

    response = client.synthesize_speech(
        Text=f"""<speak>{text.replace('//','<break time="20ms" />').replace('#','<break time="50ms" />')}</speak>""",
        LanguageCode=('en-US'), # 언어에 따라 변경 필요
        Engine='neural',
        TextType='ssml',
        OutputFormat='mp3', # wav 파일로 저장됨
        VoiceId=('Matthew'), # 언어에 따라 변경 필요
        SampleRate='22050'
    )

    # 임시 파일에 mp3 데이터를 저장
    wav_file_path = f"{output_dir}/{idx}_{index}.wav"

    pydub.AudioSegment\
        .from_file(BytesIO(b''.join(response.get('AudioStream'))))\
        .set_frame_rate(44100)\
        .export(f'{wav_file_path}',format='wav')

def time_stretch_with_ssml(tts_func, text, index, idx, speed, output_dir='/dubbing/content/tts'):
    speed = int('{:.2f}'.format(speed).split('.')[-1])
    text = f"""<prosody rate="+{speed}%">{text}</prosody>"""
    tts_func(text, index, idx, output_dir)

def remove_dir(output_dir='./tts'):
    for filename in os.listdir(f'{output_dir}/'):
        os.remove(f'{output_dir}/{filename}')


def merge_subtitles(data, subtitles, interval=50):
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
            prev_tc_end = subtitle_list[-1].end
            if sub.start - prev_tc_end <= pysrt.SubRipTime(0,0,0,interval) and sub.text[-1] != '.': # interval = 자막 사이의 간격 n
                subtitle_list.append(sub)
            else:
                new_subtitles.append(subtitle_list)
                subtitle_list = [sub]

    if subtitle_list:
        new_subtitles.append(subtitle_list)

    return new_subtitles

def make_new_subtitles (data_, subtitles, lec, UPPERBOUND):
    interval = 50
    for _ in range(10):
        interval += 50
        new_subtitles = merge_subtitles(data_, subtitles, interval)
        flag = True

        for i, subtitle_list in enumerate(new_subtitles):
            tc_length = (subtitle_list[-1].end - subtitle_list[0].start).seconds + (subtitle_list[-1].end - subtitle_list[0].start).milliseconds * 1e-3
            total_audio_length = 0
            for line in subtitle_list:
                audio, sr = librosa.load(f'/dubbing/content/tts/{lec}_{line.index-1}.wav',sr=44100)
                total_audio_length += len(audio) / sr

            if total_audio_length/tc_length > UPPERBOUND:
                flag=False

            if not flag:
                break

        if flag:
            print(interval)
            for i, subtitle_list in enumerate(new_subtitles):
                tc_length = (subtitle_list[-1].end - subtitle_list[0].start).seconds + (subtitle_list[-1].end - subtitle_list[0].start).milliseconds * 1e-3
                total_audio_length = 0
                for line in subtitle_list:
                    audio, sr = librosa.load(f'/dubbing/content/tts/{lec}_{line.index-1}.wav',sr=44100)
                    total_audio_length += len(audio) / sr
            break
    return new_subtitles
