import os
from pathlib import Path
from src.vectorstore import VectorEmbeddings
from src.chunker import header_chunks, forum_chunks, read_text_file
import src.config as config

vr = VectorEmbeddings()

if config.remake_embeddings or vr.count() == 0:
    all_chunks = []
    # Docs
    for path in Path("data/docs").glob("*.md"):
        text = read_text_file(path)
        all_chunks.extend(header_chunks(text, path.name, source_type="docs"))

    # Blogs
    for path in Path("data/blogs").glob("*.md"):
        text = read_text_file(path)
        all_chunks.extend(header_chunks(text, path.name, source_type="blog"))

    # Forums
    for path in Path("data/forums").glob("*.md"):
        text = read_text_file(path)
        all_chunks.extend(forum_chunks(text, path.name))
    vr.reset()
    vr.add_chunks(all_chunks)
    print(f"Embedded {vr.count()} chunks")
else:
    print(f"Using existing {vr.count()} chunks")

