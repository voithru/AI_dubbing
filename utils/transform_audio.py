from tqdm import tqdm
from utils.transform_subtitle import tts_to_file_polly, time_stretch_with_ssml
import pysrt
import librosa
import os
from pydub import AudioSegment

def text_to_speech(new_subtitles, lec):
    for i, subtitle_list in tqdm(enumerate(new_subtitles)):
        if i==0:
            continue
        start_tc = subtitle_list[0].start
        end_tc = subtitle_list[-1].end
        text = ' '.join([line.text for line in subtitle_list])
        if text.endswith('[~]'):
            text = text[:-3].strip() + '?'
        text = text.replace('[~]','<break strength="none" />')

        tts_to_file_polly(text, i, lec) # output tts/index.wav

        tc_length = (end_tc - start_tc).seconds + (end_tc - start_tc).milliseconds * 1e-3
        audio, sr = librosa.load(f'/dubbing/content/tts/{lec}_{i}.wav',sr=44100)
        audio_length = len(audio) / sr

        speed = audio_length / tc_length

        if speed > 1.:
            if i+1 < len(new_subtitles) and new_subtitles[i+1][0].start - end_tc > pysrt.SubRipTime(0,0,0,50):
                end_tc = new_subtitles[i+1][0].start - pysrt.SubRipTime(0,0,0,50)
                tc_length = (end_tc - start_tc).seconds + (end_tc - start_tc).milliseconds * 1e-3
                speed = audio_length / tc_length

        input_path = f'/dubbing/content/tts/{lec}_{i}.wav'
        output_path = f'/dubbing/content/final/{lec}_{i}.wav'

        time_stretch_with_ssml(tts_to_file_polly, text.replace('//','<break time="5ms" />').replace('#','<break time="25ms" />'), i, lec, (round(speed+0.1,2) if speed > 1.1 else 1.1), '/dubbing/content/final') # final/index.wav


        orig_audio_data, sr = librosa.load(input_path, sr=44100)
        speed = (len(orig_audio_data) / sr) / tc_length
        for k in range(5):
            audio_data, sr = librosa.load(output_path, sr=44100)
            audio_length = len(audio_data) / sr
            speed_check = audio_length / tc_length

            if k==4:
                raise RuntimeError(f'audio length : {audio_length}, tc length : {tc_length}')
            if speed_check > 1.:
                speed += 0.05
                time_stretch_with_ssml(tts_to_file_polly, text.replace('//','<break time="5ms" />').replace('#','<break time="25ms" />'), i, lec, speed, '/dubbing/content/final')
            else:
                break



def merge_audio_files(new_subtitles, lec, silent_audio_path):
    background = AudioSegment.from_wav(silent_audio_path)
    f = lambda x : (3600*x.hours + 60*x.minutes + x.seconds)*1000 + x.milliseconds

    dubbed_audio = background

    for ids, subtitle_list in tqdm(enumerate(new_subtitles), desc = '음성 합성'):
        # 1번 자막그룹 작업 X
        if ids== 0: continue
        start = f(subtitle_list[0].start)
        
        voice = AudioSegment.from_wav(f'/dubbing/content/final/{lec}_{ids}.wav')
        dubbed_audio = dubbed_audio.overlay(voice, position=start)

    file_name_with_ext = os.path.basename(silent_audio_path)
    file_name = os.path.splitext(file_name_with_ext)[0].replace('_silent_audio', '')
    
    # 완성 파일 출력 시작
    if dubbed_audio.channels ==1:
        stereo_audio = dubbed_audio.set_channels(2)
        stereo_audio.export(f'/dubbing/output/raw/{file_name}_en.wav', 'wav')
    else:
        dubbed_audio.export(f'/dubbing/output/raw/{file_name}_en.wav', 'wav')
    # 완성 파일 출력 완료