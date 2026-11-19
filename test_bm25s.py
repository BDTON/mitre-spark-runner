import bm25s

texts = ["test document one", "test document two"]
tok = bm25s.tokenize(texts)
print("Type:", type(tok))
print("IDs:", tok.ids)
print("Vocab:", tok.vocab)

retriever = bm25s.BM25()
retriever.index(tok.ids)
print("Indexing with ids worked!")

q = bm25s.tokenize(["test"])
results = retriever.retrieve(q.ids[0], k=5)
print("Query results:", results)
