# ragchat.py

import os
import sys
import faiss
import pickle
import hashlib
import tempfile
import requests
import numpy as np
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from sentence_transformers import SentenceTransformer
from ollama import Client

CACHE_DIR = Path("~/.rag_cache").expanduser()
CACHE_DIR.mkdir(exist_ok=True)

known_models = {
    'llama2': 'LLaMA 2',
    'llama3.1': 'LLaMA 3.1',
    'deepseek-r1:14b': 'Deepseek-r1 14B',
    'deepseek-r1:7b': 'Deepseek-r1 7B',
    'mixtral': 'Mixtral',
    'mistral': 'Mistral',
    'glm4-32b': 'GLM4 32B'
}

class RagChat:
    def __init__(self, model_name='mistral', ollama_host='http://localhost:11434'):
        self.client = Client(host=ollama_host)
        self.model_name = model_name
        self.embed_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.documents = {}
        self.chat_history = []

    def file_hash(self, filepath):
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            h.update(f.read())
        return h.hexdigest()

    def load_and_chunk(self, filepath, chunk_size=500, overlap=50):
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        chunks, start = [], 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def get_local_or_downloaded_text_path(self, input_str):
        if os.path.exists(input_str):
            return input_str

        parsed = urlparse(input_str)
        if parsed.scheme in ('http', 'https'):
            try:
                response = requests.get(input_str, timeout=10)
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '')
                _, temp_path = tempfile.mkstemp(suffix=".txt")
                with open(temp_path, 'w', encoding='utf-8') as f:
                    title = response.headers.get('Content-Disposition', '')
                    if title:
                        title = title.split('filename=')[-1].strip('"')
                        f.write(f"Title: {title}\n\n")
                    if 'html' in content_type:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        f.write(soup.get_text().strip())
                    else:
                        f.write(response.text)
                return temp_path
            except Exception as e:
                raise RuntimeError(f"Failed to download or process URL: {e}")
        else:
            raise ValueError("Input is neither a valid file path nor a URL.")

    def embed_chunks(self, chunks):
        return self.embed_model.encode(chunks, convert_to_numpy=True)

    def build_faiss_index(self, embeddings):
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings)
        return index

    def run_query(self, context, question):
        full_context = context + "\n\n" + "\n".join(self.chat_history) if self.chat_history else context
        prompt = f"""Use the following context and previous discussion to answer the question.

Context:
{full_context}

Question: {question}
Answer:"""
        response = self.client.generate(model=self.model_name, prompt=prompt)
        return response['response'].strip()

    def cache_paths(self, doc_hash):
        base = CACHE_DIR / doc_hash
        return {
            'chunks': base.with_suffix('.pkl'),
            'embeddings': base.with_suffix('.npy'),
            'faiss': base.with_suffix('.faiss')
        }

    def save_cache(self, paths, chunks, embeddings, index):
        with open(paths['chunks'], 'wb') as f:
            pickle.dump(chunks, f)
        np.save(paths['embeddings'], embeddings)
        faiss.write_index(index, str(paths['faiss']))

    def load_cache(self, paths):
        with open(paths['chunks'], 'rb') as f:
            chunks = pickle.load(f)
        embeddings = np.load(paths['embeddings'])
        index = faiss.read_index(str(paths['faiss']))
        return chunks, embeddings, index

    def prepare_document(self, text_file):
        doc_hash = self.file_hash(text_file)
        paths = self.cache_paths(doc_hash)

        if all(p.exists() for p in paths.values()):
            chunks, embeddings, index = self.load_cache(paths)
        else:
            chunks = self.load_and_chunk(text_file)
            embeddings = self.embed_chunks(chunks)
            index = self.build_faiss_index(np.array(embeddings))
            self.save_cache(paths, chunks, embeddings, index)

        return chunks, index

    def add_document(self, path_or_url):
        filepath = self.get_local_or_downloaded_text_path(path_or_url)
        chunks, index = self.prepare_document(filepath)
        self.documents[Path(filepath).name] = {'chunks': chunks, 'index': index}

    def chat(self):
        if not self.documents:
            print("No documents loaded.")
            return

        print("📚 Loaded documents:")
        for name in self.documents:
            print(f" - {name}")
        print("\n🧠 You can now chat. Type 'exit' to quit.\n")

        while True:
            question = input("❓ You: ").strip()
            if question.lower() in {'exit', 'quit'}:
                break

            all_matches = []
            query_embedding = self.embed_model.encode([question])

            for doc in self.documents.values():
                D, I = doc['index'].search(np.array(query_embedding), k=2)
                matches = [doc['chunks'][i] for i in I[0]]
                all_matches.extend(matches)

            retrieved = "\n\n".join(all_matches)
            answer = self.run_query(retrieved, question)
            model_pretty = known_models.get(self.model_name, self.model_name)
            print(f"\n🤖 {model_pretty}: {answer}\n")

            self.chat_history.append(f"Q: {question}")
            self.chat_history.append(f"A: {answer}")

