from akeyless_agentcore_rta.ara import (
    CUSTOM_MCP_TARGET_TYPE,
    build_ara_list_items_body,
    is_ara_db_producer_type,
    is_ara_service_producer_type,
    map_ara_secrets,
)


class TestProducerTypes:
    def test_db_types(self):
        assert is_ara_db_producer_type("postgres")
        assert is_ara_db_producer_type("MySQL")
        assert not is_ara_db_producer_type("aws")

    def test_service_types(self):
        assert is_ara_service_producer_type("aws")
        assert is_ara_service_producer_type(CUSTOM_MCP_TARGET_TYPE)
        assert not is_ara_service_producer_type("postgres")


class TestBuildListBody:
    def test_ara_only_true_by_default(self):
        body = build_ara_list_items_body("t-test")
        assert body["token"] == "t-test"
        assert body["ara-only"] is True
        assert body["type"] == ["dynamic-secret", "rotated-secret", "static-secret"]
        assert "path" not in body

    def test_optional_path(self):
        body = build_ara_list_items_body("t-test", path="/folder")
        assert body["path"] == "/folder"


class TestMapAraSecrets:
    def test_filters_missing_permission_and_unsupported(self):
        items = [
            {
                "item_name": "/db/pg",
                "item_type": "DYNAMIC_SECRET",
                "client_permissions": ["ara_allow_access"],
                "item_general_info": {
                    "dynamic_secret_producer_details": {"producer_type": "postgres"}
                },
                "item_metadata": "prod db",
            },
            {
                "item_name": "/db/no-perm",
                "item_type": "dynamic-secret",
                "client_permissions": ["read"],
                "item_general_info": {
                    "dynamic_secret_producer_details": {"producer_type": "postgres"}
                },
            },
            {
                "item_name": "/svc/aws",
                "item_type": "dynamic-secret",
                "client_permissions": ["ara_allow_access"],
                "dynamic_secret_producer_details": {"producer_type": "aws"},
            },
            {
                "item_name": "/static/mcp",
                "item_type": "static-secret",
                "client_permissions": ["ara_allow_access"],
            },
            {
                "item_name": "/dyn/unsupported",
                "item_type": "dynamic-secret",
                "client_permissions": ["ara_allow_access"],
                "dynamic_secret_producer_details": {"producer_type": "chef"},
            },
        ]
        mapped = map_ara_secrets(items)
        names = [s.name for s in mapped]
        assert names == ["/db/pg", "/static/mcp", "/svc/aws"]
        by_name = {s.name: s for s in mapped}
        assert by_name["/db/pg"].target_type == "postgres"
        assert by_name["/db/pg"].description == "prod db"
        assert by_name["/svc/aws"].target_type == "aws"
        assert by_name["/static/mcp"].target_type == CUSTOM_MCP_TARGET_TYPE
        # Never include credential-like fields
        for s in mapped:
            assert "value" not in s.to_dict()
            assert "password" not in s.to_dict()
