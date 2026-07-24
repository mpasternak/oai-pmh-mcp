"""Testy warstwy serwera: parsowanie argumentów i rejestracja narzędzi."""

from oai_pmh_mcp import server

EXPECTED_TOOLS = {
    "identify",
    "list_metadata_formats",
    "list_sets",
    "list_identifiers",
    "list_records",
    "get_record",
    "harvest_records",
}


def test_parse_args_default_transport_is_stdio():
    args = server.parse_args([])
    assert args.transport == "stdio"


def test_parse_args_http_with_host_port():
    args = server.parse_args(["--transport", "http", "--host", "0.0.0.0", "--port", "9000"])
    assert args.transport == "http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000


async def test_build_server_registers_all_seven_tools():
    mcp = server.build_server()
    names = {t.name for t in await mcp.list_tools()}
    assert names == EXPECTED_TOOLS
