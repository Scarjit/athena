import os
import sounddevice as sd
import numpy as np
import pvporcupine

picovoice_key = ""
openai_key = ""

def load_env():
    # Using python-dotenv to load environment variables from .env file
    from dotenv import load_dotenv
    load_dotenv()
    # Set the environment variables
    global picovoice_key, openai_key
    picovoice_key = os.getenv("PICOVOICE_KEY")
    openai_key = os.getenv("OPENAI_KEY")

def init_porcupine():
    ppn_file_de = "./ppn/athena_de_linux_v3_0_0.ppn"
    ppn_file_en = "./ppn/athena_en_linux_v3_0_0.ppn"
    pv_file_de = "./ppn/porcupine_params_de.pv"

    pv_de = pvporcupine.create(access_key=picovoice_key, keyword_paths=[ppn_file_de], model_path=pv_file_de)
    pv_en = pvporcupine.create(access_key=picovoice_key, keyword_paths=[ppn_file_en])

    return [pv_de, pv_en]

def detect_wake_word(porcupine_engines):
    # Audio Stream Configuration
    sample_rate = porcupine_engines[0].sample_rate
    frames_per_buffer = porcupine_engines[0].frame_length

    with sd.InputStream(channels=1, samplerate=sample_rate, blocksize=frames_per_buffer, dtype='int16') as stream:
        print("Listening for wake word...")
        while True:
            pcm = stream.read(frames_per_buffer)[0]
            pcm = np.frombuffer(pcm, dtype=np.int16)
            for i, porcupine in enumerate(porcupine_engines):
                keyword_index = porcupine.process(pcm)
                if keyword_index >= 0:
                    print(f"Detected wake word using engine {i}!")
                    return



def main():
    load_env()
    porcupine_engines = init_porcupine()
    while True:
        detect_wake_word(porcupine_engines)


if __name__ == "__main__":
    main()
