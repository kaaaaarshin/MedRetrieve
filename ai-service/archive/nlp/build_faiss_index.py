import pickle

import faiss
import numpy as np

from app.services.nlp.bioclinicalbert import embed_text
from app.services.nlp.icd_parser import parse_icd_xml


ICD_XML = "/Users/karshin/Downloads/icd102019en.xml"

INDEX_PATH = "data/icd.index"
METADATA_PATH = "data/icd_metadata.pkl"


def main():

    print("Loading ICD XML...")

    records = parse_icd_xml(ICD_XML)
    records = records[:100]

    print(f"Loaded {len(records)} ICD codes")

    embeddings = []

    for i, record in enumerate(records, start=1):

        vec = embed_text(
            record["description"]
        )

        embeddings.append(vec)

        if i % 100 == 0:
            print(f"Embedded {i}/{len(records)}")

    embeddings = np.array(
        embeddings,
        dtype=np.float32,
    )

    faiss.normalize_L2(
        embeddings
    )

    dim = embeddings.shape[1]

    index = faiss.IndexFlatIP(
        dim
    )

    index.add(
        embeddings
    )

    faiss.write_index(
        index,
        INDEX_PATH,
    )

    with open(
        METADATA_PATH,
        "wb",
    ) as f:
        pickle.dump(
            records,
            f,
        )

    print("FAISS index saved")
    print(INDEX_PATH)
    print(METADATA_PATH)


if __name__ == "__main__":
    main()

print("before loop")

for i, record in enumerate(records, start=1):

    print(f"record {i}")

    vec = embed_text(
        record["description"]
    )

    print("embedded")