from local_data_agent.exports import export_rows


def test_export_rows_csv(tmp_path) -> None:
    path = export_rows([{"a": 1, "b": "x"}], "csv", tmp_path)
    assert path.exists()
    assert "a,b" in path.read_text(encoding="utf-8")
