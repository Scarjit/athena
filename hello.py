import os
from datetime import datetime

import openai
import sounddevice as sd
import soundfile as sf
import numpy as np
import pvporcupine
import io
import scipy.io.wavfile as wavfile
from openai import OpenAI
import chime

picovoice_key = ""
openai_key = ""

sample_rate = 16000
frames_per_buffer = 512

user_background = """
The user has not specified any background information.
Just a regular person asking questions.
"""

client: openai.Client | None = None

def load_env():
    # Using python-dotenv to load environment variables from .env file
    from dotenv import load_dotenv
    load_dotenv()
    # Set the environment variables
    global picovoice_key, openai_key
    picovoice_key = os.getenv("PICOVOICE_KEY")
    openai_key = os.getenv("OPENAI_KEY")

    # Load user_background.txt (if it exists)
    global user_background
    if os.path.exists("user_background.txt"):
        with open("user_background.txt", "r") as file:
            user_background = file.read()

def init_openai():
    global client
    client = OpenAI(api_key=openai_key)

def init_porcupine():
    ppn_file_de = "./ppn/athena_de_linux_v3_0_0.ppn"
    ppn_file_en = "./ppn/athena_en_linux_v3_0_0.ppn"
    pv_file_de = "./ppn/porcupine_params_de.pv"

    pv_de = pvporcupine.create(access_key=picovoice_key, keyword_paths=[ppn_file_de], model_path=pv_file_de)
    pv_en = pvporcupine.create(access_key=picovoice_key, keyword_paths=[ppn_file_en])

    # Audio Stream Configuration
    global sample_rate, frames_per_buffer
    sample_rate = pv_de.sample_rate
    frames_per_buffer = pv_de.frame_length

    return [pv_de, pv_en]

def detect_wake_word(porcupine_engines):

    with sd.InputStream(channels=1, samplerate=sample_rate, blocksize=frames_per_buffer, dtype='int16') as stream:
        print("Listening for wake word...")
        while True:
            pcm = stream.read(frames_per_buffer)[0]
            pcm = np.frombuffer(pcm, dtype=np.int16)
            for i, porcupine in enumerate(porcupine_engines):
                keyword_index = porcupine.process(pcm)
                if keyword_index >= 0:
                    chime.info()
                    print(f"Detected wake word using engine {i}!")
                    return

def record_question():
    print("Recording question...")
    # Record until silence is detected or max duration is reached
    # Implement silence detection or set a fixed duration
    duration = 5  # seconds
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    print("Recording complete.")

    # Play chime sound to indicate recording is complete
    chime.success()

    return recording


def transcribe_audio(audio_data):
    print("Transcribing audio...")
    # Convert numpy array to bytes
    audio_bytes = audio_data.tobytes()
    # Save to a BytesIO object
    audio_file = io.BytesIO()
    wavfile.write(audio_file, sample_rate, audio_data)
    audio_file.seek(0)

    # Set file format to WAV
    audio_file.name = "audio.wav"


    # Use OpenAI Whisper API
    transcription = client.audio.transcriptions.create(file=audio_file, model="whisper-1", language="en")
    return transcription.text


def get_answer(question):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": f"""
You are Athena, a virtual assistant that helps with answering questions. 
Your goal is to provide accurate, short answers to the user's questions.
Try to incorporate the user's background information into your responses, if relevant.
No matter the language of the question, you should always respond in English.
Remember to format your output in a way that is easy for a TTS engine to read.

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

def synthesize_audio(text):
    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        response_format="wav",
        input=text
    )

    # Generate random filename
    rand_name = os.urandom(8).hex()
    filename = f"/tmp/{rand_name}.wav"

    response.write_to_file(filename)
    return filename

def play_audio(filename):
    data, samplerate = sf.read(filename)
    sd.play(data, samplerate)
    sd.wait()

def main():
    load_env()
    init_openai()
    porcupine_engines = init_porcupine()
    #while True:
    detect_wake_word(porcupine_engines)
    question = record_question()
    now = datetime.now()
    question_text = transcribe_audio(question)
    print(f"Question: {question_text}")
    answer = get_answer(question_text)
    print(f"Answer: {answer}")
    filename = synthesize_audio(answer)
    print(f"Audio file: {filename}")
    elapsed = datetime.now() - now
    print(f"Time elapsed: {elapsed}")
    play_audio(filename)



if __name__ == "__main__":
    main()
