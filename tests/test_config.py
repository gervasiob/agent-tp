from local_data_agent.config import ConfigStore, LocalConnection, mask_database_uri


def test_mask_database_uri_hides_password() -> None:
    assert mask_database_uri("postgresql://user:secret@localhost/db") == "postgresql://user:***@localhost/db"


def test_config_store_roundtrip(tmp_path) -> None:
    store = ConfigStore(tmp_path)
    connection = LocalConnection(type="folder", name="Docs", folder_path="/tmp/docs")
    store.save_connection(connection)
    loaded = store.load_connection()
    assert loaded == connection
    assert loaded.public_dict()["folder_path"] == "docs"
