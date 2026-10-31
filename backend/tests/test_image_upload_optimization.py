import io
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import admin as admin_module
from app.main import app
from app.models.puzzle import Cell, Clue, Puzzle
from app.services.limits import get_limits


def png_bytes(width: int, height: int):
    image = Image.effect_noise((width, height), 100).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId="source-puzzle",
        title="Test",
        width=1,
        height=1,
        cells=[
            Cell(
                row=0,
                col=0,
                type="white",
                number=1,
                startsAcross=True,
                startsDown=False,
            )
        ],
        clues=[
            Clue(
                clueId="A1",
                number=1,
                direction="across",
                text="Clue",
                answerLength=1,
            )
        ],
    )


def decoded_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def test_create_room_compresses_stored_image(monkeypatch):
    captured: dict[str, bytes | str] = {}

    def fake_process(image_bytes: bytes) -> Puzzle:
        captured["original"] = image_bytes
        return make_puzzle()

    def fake_publish_image(room_id, image_bytes, content_type="image/jpeg"):
        captured["stored"] = image_bytes
        captured["content_type"] = content_type

    monkeypatch.setattr(admin_module, "process_image", fake_process)
    monkeypatch.setattr(
        admin_module,
        "_resolve_admin",
        lambda request: SimpleNamespace(
            playerId="admin", displayName="admin@example.com", role="admin"
        ),
    )
    monkeypatch.setattr(
        admin_module.firestore_publisher, "publish_room_image", fake_publish_image
    )

    original = png_bytes(1600, 1200)

    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/admin/rooms",
            content=original,
            headers={"Content-Type": "application/octet-stream"},
            params={"title": "Compressed"},
        )

    assert response.status_code == 201, response.text
    assert captured["original"] == original

    stored = captured["stored"]
    assert isinstance(stored, bytes)
    assert captured["content_type"] == "image/jpeg"
    assert stored[:2] == b"\xff\xd8"
    assert len(stored) < len(original)
    assert max(decoded_size(stored)) <= get_limits().max_stored_image_dimension
