from akeyless_agentcore_rta.ara import (
    CUSTOM_MCP_TARGET_TYPE,
    build_ara_list_items_body,
    is_ara_db_producer_type,
    is_ara_remote_producer_type,
    is_ara_service_producer_type,
    is_ara_supported_producer_type,
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

    def test_remote_types_match_go_ara_remote_producer_types(self):
        for kind in ("ssh", "windows", "rdp", "ldap", "linked", "SSH"):
            assert is_ara_remote_producer_type(kind)
            assert is_ara_supported_producer_type(kind)
        assert not is_ara_remote_producer_type("aws")
        assert not is_ara_service_producer_type("ssh")


class TestBuildListBody:
    def test_ara_only_true_by_default(self):
        body = build_ara_list_items_body("t-test")
        assert body["token"] == "t-test"
        assert body["ara-only"] is True
        assert body["type"] == ["dynamic-secret", "rotated-secret", "static-secret", "ssh-cert-issuer"]
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


class TestMapRemoteItems:
    def test_lists_remote_rotated_and_dynamic_secrets(self):
        def rotated(name, target):
            return {
                "item_name": name,
                "item_type": "ROTATED_SECRET",
                "client_permissions": ["ara_allow_access"],
                "item_targets_assoc": [{"target_type": target}],
            }

        def dynamic(name, producer):
            return {
                "item_name": name,
                "item_type": "DYNAMIC_SECRET",
                "client_permissions": ["ara_allow_access"],
                "item_general_info": {"dynamic_secret_producer_details": {"producer_type": producer}},
            }

        mapped = map_ara_secrets(
            [
                rotated("/r/ssh", "ssh"),
                rotated("/r/windows", "windows"),
                rotated("/r/ldap", "ldap"),
                rotated("/r/linked", "linked"),
                dynamic("/d/rdp", "rdp"),
                dynamic("/d/ldap", "ldap"),
                rotated("/r/unsupported", "vault"),
            ]
        )
        assert [(s.name, s.secret_type, s.target_type) for s in mapped] == [
            ("/d/ldap", "dynamic-secret", "ldap"),
            ("/d/rdp", "dynamic-secret", "rdp"),
            ("/r/ldap", "rotated-secret", "ldap"),
            ("/r/linked", "rotated-secret", "linked"),
            ("/r/ssh", "rotated-secret", "ssh"),
            ("/r/windows", "rotated-secret", "windows"),
        ]

    def test_lists_ssh_cert_issuers_on_ssh_target_type(self):
        mapped = map_ara_secrets(
            [
                {
                    "item_name": "/ssh/prod-ca",
                    "item_type": "SSH_CERT_ISSUER",
                    "item_metadata": "prod hosts",
                    "client_permissions": ["ara_allow_access"],
                },
                {"item_name": "/ssh/no-ara", "item_type": "SSH_CERT_ISSUER", "client_permissions": ["read"]},
            ]
        )
        assert [s.to_dict() for s in mapped] == [
            {
                "name": "/ssh/prod-ca",
                "secret_type": "ssh-cert-issuer",
                "target_type": "ssh",
                "description": "prod hosts",
            }
        ]
