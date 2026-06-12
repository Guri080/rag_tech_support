import os
from pathlib import Path
from src.vectorstore import VectorEmbeddings
from src.chunker import header_chunk, forum_chunks, read_text_file

all_chunks = []
vr = VectorEmbeddings()
vr.reset()
# Docs
for path in Path("data/docs").glob("*.md"):
    text = read_text_file(path)
    all_chunks.extend(header_chunk(text, path.name, source_type="docs"))

# Blogs
for path in Path("data/blogs").glob("*.md"):
    text = read_text_file(path)
    all_chunks.extend(header_chunk(text, path.name, source_type="blog"))

# Forums
for path in Path("data/forums").glob("*.md"):
    text = read_text_file(path)
    all_chunks.extend(forum_chunks(text, path.name))

vr.add_chunks(all_chunks)

# text = chunker.read_text_file(text_path)

# myChunks = chunker.forum_chunks(text, "1")

# print(myChunks)
# print(len(myChunks))

# print(f"Total chunks: {len(all_chunks)}")
