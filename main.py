import os
from datetime import datetime
import toml
import openai
import sounddevice as sd
import soundfile as sf
import numpy as np
import pvporcupine
import io
import scipy.io.wavfile as wavfile
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

def record_question(sample_rate):
    print("Recording question...")
    duration = 5  # seconds
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    print("Recording complete.")
    chime.success()
    return recording.flatten()

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
            model="gpt-4",
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