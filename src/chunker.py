import docx
import PyPDF2
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter

def read_text_file(file_path: str):
    """Read content from a text file"""
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()
    
def split_text(text: str, chunk_size: int = 500):
    """Split text into chunks while preserving sentence boundaries"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=100,
        chunk_overlap=20,
        length_function=len
        )
    chunks = text_splitter.split_text(long_text)
    sentences = text.replace('\n', ' ').split('. ')
    chunks = []
    current_chunk = []
    current_size = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # Ensure proper sentence ending
        if not sentence.endswith('.'):
            sentence += '.'

        sentence_size = len(sentence)

        # Check if adding this sentence would exceed chunk size
        if current_size + sentence_size > chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_size = sentence_size
        else:
            current_chunk.append(sentence)
            current_size += sentence_size

    # Add the last chunk if it exists
    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks
