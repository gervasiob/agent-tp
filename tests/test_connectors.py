from local_data_agent.connectors import DatabaseConnector, create_sqlite_demo


def test_database_connector_describes_demo_and_sums_iva(tmp_path) -> None:
    db_path = tmp_path / "demo.sqlite"
    create_sqlite_demo(db_path)
    connector = DatabaseConnector(f"sqlite:///{db_path}")
    context = connector.describe()
    assert context.kind == "database"
    assert context.details["tables"][0]["name"] == "invoices"
    rows = connector.run_readonly_query('SELECT SUM("iva") AS total_iva FROM "invoices"')
    assert rows[0]["total_iva"] == 903
