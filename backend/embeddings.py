from openai import OpenAI

client = OpenAI()

def get_embedding(text:str, model: str = "text-embedding-3-small"):
    response = client.embeddings.create(
        model=model,
        input=text
    )
    return response.data[0].embedding