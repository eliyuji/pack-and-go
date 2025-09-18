from typing import List

def chunking_text(text: str, max_tok: int=400, overlap: int=50) -> List[str]:
    words = text.split()
    chunks = []
    startInt = 0
    while startInt <len(words):
        end = min(startInt+ max_tok, len(words))
        chunk = " ".join(words[startInt:end])
        chunks.append(chunk)
        startInt +=max_tok -overlap
    return chunks