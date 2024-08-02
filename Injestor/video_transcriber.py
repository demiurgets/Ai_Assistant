import os
import json
import moviepy.editor as mp
import whisper
from transformers import pipeline

settings = {
    'openAi_assistant': 'asst_PfhKQbC3NCCnTVpw8osZjXeq',
    'openAi_key': '53Mu7zXn59m0dgxQRU7kT3BlbkFJgvRmEEpP907IMakf8FSc',
    'chunk_size': 500
}

model = whisper.load_model("base")

def transcribe_video(video_path):
    video = mp.VideoFileClip(video_path)
    audio_path = "temp_audio.wav"
    video.audio.write_audiofile(audio_path)

    transcription = model.transcribe(audio_path)
    os.remove(audio_path)
    return transcription['text']
\

def split_document(content, chunk_size=500):
    sentences = content.split('. ')
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "
        else:
            current_chunk += sentence + ". "

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

def main():
    video_path = "path_to_your_video.mp4"  
    transcription = transcribe_video(video_path)
    
    doc_chunks = split_document(transcription, settings['chunk_size'])
    all_chunks = []
    for i, chunk in enumerate(doc_chunks):
        all_chunks.append({
            "title": os.path.basename(video_path),
            "content": chunk,
            "chunk_id": i,
            "link": None 
        })

    current_directory = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(current_directory, 'document_chunks.json')

    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            existing_chunks = json.load(f)
    else:
        existing_chunks = []

    existing_chunks.extend(all_chunks)

    with open(output_path, 'w') as f:
        json.dump(existing_chunks, f, indent=4)

if __name__ == "__main__":
    main()
