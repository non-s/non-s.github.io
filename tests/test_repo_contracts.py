from scripts.check_repo_contracts import check_repo_contracts


def test_repo_contracts_pass_for_current_repo():
    root = __import__("pathlib").Path(__file__).resolve().parent.parent

    assert check_repo_contracts(root) == []
