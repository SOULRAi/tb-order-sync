from config.settings import Settings
from cli.commands import has_required_runtime_config


def test_runtime_config_no_longer_requires_client_secret():
    settings = Settings(
        tencent_client_id="client-id",
        tencent_client_secret="",
        tencent_open_id="open-id",
        tencent_access_token="token",
        tencent_a_file_id="a-file",
        tencent_a_sheet_id="a-sheet",
        tencent_b_file_id="b-file",
        tencent_b_sheet_id="b-sheet",
    )

    assert has_required_runtime_config(settings) is True
