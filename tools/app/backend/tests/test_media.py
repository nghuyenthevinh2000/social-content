import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from tools.app.backend.media import MediaStore, MAX_MEDIA_BYTES


def test_media_save_and_owner_isolation():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        store = MediaStore(db_path=base / "media.db", media_dir=base / "media")
        
        # User 1 saves profile image
        data = b"\xff\xd8\xff\xe0testjpegcontent"
        m1 = store.save_media(user_id="user_1", kind="profile", raw_bytes=data, mime_type="image/jpeg")
        assert m1["id"] is not None
        assert m1["kind"] == "profile"
        assert Path(m1["path"]).exists()
        
        # User 2 cannot access user 1's media
        assert store.get_media(user_id="user_2", media_id=m1["id"]) is None
        assert store.delete_media(user_id="user_2", media_id=m1["id"]) is False
        assert Path(m1["path"]).exists()
        
        # User 1 can access and list
        assert store.get_media(user_id="user_1", media_id=m1["id"]) is not None
        items = store.list_media(user_id="user_1")
        assert len(items) == 1
        assert items[0]["id"] == m1["id"]
        
        # Replacing profile image removes old profile image
        m2 = store.save_media(user_id="user_1", kind="profile", raw_bytes=b"newprofile", mime_type="image/jpeg")
        assert not Path(m1["path"]).exists()
        assert Path(m2["path"]).exists()
        
        # Context images can be multiple
        c1 = store.save_media(user_id="user_1", kind="context", raw_bytes=b"ctx1", mime_type="image/png")
        c2 = store.save_media(user_id="user_1", kind="context", raw_bytes=b"ctx2", mime_type="image/webp")
        ctx_items = store.list_media(user_id="user_1", kind="context")
        assert len(ctx_items) == 2
        
        # Delete media
        assert store.delete_media(user_id="user_1", media_id=c1["id"]) is True
        assert not Path(c1["path"]).exists()
        assert len(store.list_media(user_id="user_1", kind="context")) == 1

def test_media_validation():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        store = MediaStore(db_path=base / "media.db", media_dir=base / "media")
        
        # Invalid kind
        with pytest.raises(ValueError, match="Invalid kind"):
            store.save_media("u1", "avatar", b"data", "image/jpeg")
            
        # Invalid mime
        with pytest.raises(ValueError, match="Unsupported media type"):
            store.save_media("u1", "profile", b"data", "application/pdf")
            
        # Too large
        with pytest.raises(ValueError, match="File too large"):
            store.save_media("u1", "profile", b"0" * (MAX_MEDIA_BYTES + 1), "image/jpeg")
            
        # Empty
        with pytest.raises(ValueError, match="Empty file"):
            store.save_media("u1", "profile", b"", "image/jpeg")
