NORMALIZATION = {

    "pleural effusion": "pleural effusion",

    "pneumothorax": "pneumothorax",

    "hydropneumothorax": "hydropneumothorax",

    "atelectatic": "atelectasis",
    "atelectasis": "atelectasis",

    "airspace opacity": "consolidation",
    "consolidation": "consolidation",

    "ground glass": "ground glass opacity",

    "fibrosis": "pulmonary fibrosis",

    "cardiomegaly": "cardiomegaly",

    "pulmonary edema": "pulmonary edema",

    "pleural thickening": "pleural thickening",

    "pleural plaque": "pleural plaque",

    "bronchiectasis": "bronchiectasis",

    "mediastinal shift": "mediastinal shift",

    "lymphadenopathy": "lymphadenopathy",
}
def normalize(entities):

    normalized = []

    for entity in entities:

        entity = entity.lower()

        replaced = False

        for key, value in NORMALIZATION.items():

            if key in entity:

                normalized.append(value)

                replaced = True

                break

        if not replaced:
            normalized.append(entity)

    return list(dict.fromkeys(normalized))