import collections
import os
import sys
from datetime import datetime
import toml
import openai
import sounddevice as sd
import soundfile as sf
import numpy as np
import pvporcupine
import io
import scipy.io.wavfile as wavfile
import webrtcvad
from openai import OpenAI
import chime

# Global configuration dictionary
config = {}

client: openai.Client | None = None

def load_config(config_path="config.toml"):
    global config
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file '{config_path}' not found.")
    with open(config_path, "r") as f:
        config = toml.load(f)
    print("Configuration loaded successfully.")

def init_openai():
    api_key = config['credentials']['openai_key']
    global client
    client = OpenAI(api_key=api_key)
    print("OpenAI initialized.")

def init_porcupine():
    porcupine_configs = config['porcupine']
    ppn_file_de = porcupine_configs['ppn_file_de']
    ppn_file_en = porcupine_configs['ppn_file_en']
    pv_file_de = porcupine_configs['pv_file_de']
    picovoice_key = config['credentials']['picovoice_key']

    # Create Porcupine engines for German and English
    pv_de = pvporcupine.create(
        access_key=picovoice_key,
        keyword_paths=[ppn_file_de],
        model_path=pv_file_de
    )
    pv_en = pvporcupine.create(
        access_key=picovoice_key,
        keyword_paths=[ppn_file_en]
    )

    # Audio Stream Configuration
    settings = config['settings']
    sample_rate = settings['sample_rate']
    frames_per_buffer = settings['frames_per_buffer']

    return [pv_de, pv_en], sample_rate, frames_per_buffer

def get_user_background():
    return config['user']['background']

def get_system_prompt():
    return config['system']['prompt']

def detect_wake_word(porcupine_engines, sample_rate, frames_per_buffer):
    with sd.InputStream(channels=1, samplerate=sample_rate, blocksize=frames_per_buffer, dtype='int16') as stream:
        print("Listening for wake word...")
        while True:
            pcm, _ = stream.read(frames_per_buffer)
            pcm = np.frombuffer(pcm, dtype=np.int16)
            for i, porcupine in enumerate(porcupine_engines):
                keyword_index = porcupine.process(pcm)
                if keyword_index >= 0:
                    chime.info()
                    print(f"Detected wake word using engine {i}!")
                    return

def record_question(sample_rate, vad_mode=1, frame_duration=30, padding_duration=300):
    """
    Records audio from the microphone until silence is detected.

    :param sample_rate: Sampling rate of the audio.
    :param vad_mode: Aggressiveness of the VAD (0-3).
    :param frame_duration: Duration of each frame in ms.
    :param padding_duration: Duration to wait before ending after silence is detected in ms.
    :return: Recorded audio as a NumPy array.
    """
    vad = webrtcvad.Vad(vad_mode)
    frame_size = int(sample_rate * frame_duration / 1000)  # Number of samples per frame
    padding_frames = int(padding_duration / frame_duration)
    ring_buffer = collections.deque(maxlen=padding_frames)
    triggered = False
    frames = []

    def callback(indata, frames_, time_, status):
        nonlocal triggered
        if status:
            print(status, file=sys.stderr)
        # Convert to mono and 16-bit PCM
        pcm = indata[:, 0].astype(np.int16).tobytes()
        is_speech = vad.is_speech(pcm, sample_rate)
        if is_speech:
            triggered = True
            frames.append(indata.copy())
            ring_buffer.clear()
        elif triggered:
            ring_buffer.append(indata.copy())
            frames.append(indata.copy())
            if len(ring_buffer) >= ring_buffer.maxlen:
                triggered = False

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16',
                        blocksize=frame_size, callback=callback):
        print("Recording... Speak now.")
        sd.sleep(1000)  # Wait a bit to allow the user to start speaking
        while True:
            sd.sleep(100)  # Sleep in short intervals to allow callback processing
            if not triggered and len(ring_buffer) == ring_buffer.maxlen:
                break

    print("Recording complete.")
    chime.success()

    # Concatenate all recorded frames
    audio = np.concatenate(frames, axis=0).flatten()
    return audio

def transcribe_audio(audio_data, sample_rate):
    print("Transcribing audio...")
    audio_file = io.BytesIO()
    wavfile.write(audio_file, sample_rate, audio_data)
    audio_file.seek(0)
    audio_file.name = "audio.wav"

    try:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=config['transcription']['language']
        )
        return transcription.text
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""

def get_answer(question):
    system_prompt = get_system_prompt()
    user_background = get_user_background()
    try:
        response = client.chat.completions.create(
            model=config['chat']['model'],
            messages=[
                {
                    "role": "system",
                    "content": f"""
{system_prompt}

Here is some background about the user: 
{user_background}
                    """
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error during getting answer: {e}")
        return "I'm sorry, I couldn't process your request."

def synthesize_audio(text):
    voice_config = config['voice']
    try:
        response = client.audio.speech.create(
            model=voice_config['model'],
            voice=voice_config['voice'],
            input=text,
            response_format="wav"
        )

        # Generate random filename
        rand_name = os.urandom(8).hex()
        filename = f"/tmp/{rand_name}.wav"

        response.write_to_file(filename)

        return filename
    except Exception as e:
        print(f"Error during audio synthesis: {e}")
        return ""

def play_audio(filename):
    try:
        data, samplerate = sf.read(filename)
        sd.play(data, samplerate)
        sd.wait()
    except Exception as e:
        print(f"Error during audio playback: {e}")

def main():
    load_config()
    init_openai()
    porcupine_engines, sample_rate, frames_per_buffer = init_porcupine()

    try:
        while True:
            detect_wake_word(porcupine_engines, sample_rate, frames_per_buffer)
            question_audio = record_question(sample_rate)
            now = datetime.now()
            question_text = transcribe_audio(question_audio, sample_rate)
            print(f"Question: {question_text}")
            if not question_text:
                print("No transcription available.")
                continue
            answer = get_answer(question_text)
            print(f"Answer: {answer}")
            filename = synthesize_audio(answer)
            if filename:
                print(f"Audio file: {filename}")
                play_audio(filename)
            elapsed = datetime.now() - now
            print(f"Time elapsed: {elapsed}")
    except KeyboardInterrupt:
        print("Exiting program.")
    finally:
        # Cleanup Porcupine engines
        for porcupine in porcupine_engines:
            porcupine.delete()

if __name__ == "__main__":
    main()
