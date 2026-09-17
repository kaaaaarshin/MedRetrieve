import xml.etree.ElementTree as ET


def parse_icd_xml(xml_path: str):

    tree = ET.parse(xml_path)
    root = tree.getroot()

    icd_records = []

    for cls in root.iter("Class"):

        code = cls.attrib.get("code")
        kind = cls.attrib.get("kind")

        if kind != "category":
            continue

        texts = []

        for rubric in cls.findall("Rubric"):

            rubric_kind = rubric.attrib.get("kind")

            # ignore exclusions
            if rubric_kind == "exclusion":
                continue

            for label in rubric.findall("Label"):

                if label is not None and label.text:
                    texts.append(
                        label.text.strip()
                    )

        if texts:

            icd_records.append(
                {
                    "code": code,
                    "description": " ".join(texts),
                }
            )

    return icd_records