import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services" / "research-discovery"))

from service import _paper_metadata


def test_paper_metadata_maps_client_dict_and_strips_et_al_placeholder():
    client_dict = {
        "id": 3, "title": "A Study of X", "authors": ["Alice Smith", "Bob Jones", "et al."],
        "year": 2022, "venue": "Journal of Examples", "citations": 12,
        "doi": "10.1000/xyz", "link": "https://doi.org/10.1000/xyz",
        "source": "OpenAlex", "has_abstract": True, "abstract": "This study examines X.",
    }
    meta = _paper_metadata(client_dict)
    assert meta.id == 3
    assert meta.authors == ["Alice Smith", "Bob Jones"]
    assert meta.doi == "10.1000/xyz"
    assert meta.has_abstract is True
    assert meta.abstract == "This study examines X."
