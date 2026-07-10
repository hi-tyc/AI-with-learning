import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.endpoints.materials import router


def test_material_file_route_accepts_head_for_document_viewer_preflight():
    route = next(
        route for route in router.routes
        if getattr(route, "path", "") == "/{material_id}/file"
    )

    assert {"GET", "HEAD"}.issubset(route.methods)
