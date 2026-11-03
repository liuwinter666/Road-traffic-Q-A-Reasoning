"""Nạp ontology ``traffic_law.owl`` vào một ``World`` riêng của owlready2.

Mỗi vụ việc nên dùng một World riêng (``load_world()``) để cá thể của các phiên tư vấn
không lẫn vào nhau.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from owlready2 import World

from src.config import ONTOLOGY_DIR

ONTOLOGY_FILE = ONTOLOGY_DIR / "traffic_law.owl"


def load_world(path: Path = ONTOLOGY_FILE):
    """Trả về ``(world, onto)`` với ontology đã nạp từ ``path``."""
    if not path.exists():
        raise FileNotFoundError(f"{path} chưa có — chạy: python -m src.kb.build_ontology")
    world = World()
    onto = world.get_ontology(str(path.resolve())).load()
    logger.debug("Nạp ontology {} ({} lớp)", path.name, len(list(onto.classes())))
    return world, onto
