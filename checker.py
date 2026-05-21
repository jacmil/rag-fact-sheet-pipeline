import chromadb
client = chromadb.PersistentClient(path="data/chromadb")
col = client.get_collection("tpi_vectors")
results = col.get(where={"company": "AGL"}, include=["documents", "metadatas"])
for doc, meta in zip(results["documents"], results["metadatas"]):
    print(meta)
    print(doc[:500])
    print("---")