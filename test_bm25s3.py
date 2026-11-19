import bm25s

texts = ["test document nile", "test document pharaoh", "test document nile pharaoh"]
tok = bm25s.tokenize(texts)
print("Tokenized IDs:", tok.ids)

retriever = bm25s.BM25()
retriever.index(tok.ids)

q = bm25s.tokenize(["nile"])
results = retriever.retrieve(q, k=2)
print("Results type:", type(results))
print("Results:", results)
if isinstance(results, tuple):
    print("Len:", len(results))
    for i, r in enumerate(results):
        print(f"  [{i}] type={type(r)}, shape={getattr(r, 'shape', 'N/A')}, value={r}")
