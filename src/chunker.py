from langchain_text_splitters import RecursiveCharacterTextSplitter

def read_text_file(file_path: str):
    """Read content from a text file"""
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()
    
def header_chunk(text: str, source_id: str) -> list[dict]:
    """Split documents into chunks on ## headers"""
    chunks = []
    sentences = text.split('##')

    fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )

    for section in sentences:
        header = section.split('\n')[0].strip('# ')

        # if a section is less than 1000 chars, keep as one chuck
        # Otherwise if section is long, make sub chunks
        if len(section) < 1000:
            chunks.append({
                'text': section,
                'source': "docs",
                'source_id': source_id,
                "metadata": {"header": header}
            })
        else:
            sub_chunks = fallback_splitter.split_text(section)
            for i, sub in enumerate(sub_chunks):
                chunks.append({
                    "text": sub,
                    "source": "docs",
                    "source_id": source_id,
                    "metadata": {"header": header, "sub_chunk": i}
                })
    return chunks

def forum_chunks(text: str, source_id: str) -> list[dict]:
    posts = [p.strip() for p in text.split('---') if p.strip()]

    return [
        {
            "text": post,
            "source": "forum",
            "source_id": source_id,
            "metadata": {"post_index": i}
        }
        for i, post in enumerate(posts)
    ]