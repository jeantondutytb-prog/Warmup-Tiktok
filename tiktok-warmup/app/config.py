import yaml


def load_accounts(path: str) -> list[dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["accounts"]


def load_devices(path: str) -> dict[str, dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["devices"]


def load_comments(path: str) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {}
    current_category = None
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("# "):
                current_category = line[2:].strip()
                categories[current_category] = []
            elif line.strip() and current_category is not None:
                categories[current_category].append(line)
    return categories


def load_keywords(path: str) -> dict[str, list[str]]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["keywords"]
