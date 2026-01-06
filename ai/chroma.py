import chromadb
import json

def main():
    chroma_client = chromadb.Client()  # Initialize ChromaDB client
    collection = chroma_client.create_collection(name="kang_collection")
    collection.add(
        ids=["id1", "id2", "id3"],
        documents=[
            "This is a document about pineapple id1",
            "This is a document about oranges id2",
            "坦克是没有后视镜的· id3"
        ]
    )
    results = collection.query(
        query_texts=["谁坦克没有后视镜"], # Chroma will embed this for you
        n_results=1 # how many results to return
    )
    print(results)
    json_str = json.dumps(results, indent=2, ensure_ascii=False)
    print(type(json_str))
    print(json_str)


if __name__ == '__main__':
    main()

