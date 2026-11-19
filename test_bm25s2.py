import bm25s

texts = ["test document one", "test document two"]
tok = bm25s.tokenize(texts)

retriever = bm25s.BM25()
retriever.index(tok.ids)
print("Indexing worked!")

# Try querying with Tokenized object
q = bm25s.tokenize(["test"])
print("Query type:", type(q))
print("Query ids:", q.ids)
print("Query ids[0]:", q.ids[0])

# Try different retrieve call patterns
try:
    results = retriever.retrieve(q, k=5)
    print("retrieve(Tokenized) worked:", results)
except Exception as e:
    print("retrieve(Tokenized) failed:", e)

try:
    results = retriever.retrieve(q.ids, k=5)
    print("retrieve(ids) worked:", results)
except Exception as e:
    print("retrieve(ids) failed:", e)

try:
    results = retriever.retrieve(q.ids[0], k=2)
    print("retrieve(ids[0]) worked:", results)
except Exception as e:
    print("retrieve(ids[0]) failed:", e)
