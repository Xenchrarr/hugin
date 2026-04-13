from src.api.powershell_runner.script_runner import test_script, run_generic_script


def run_test_script():
    test_script()


def run_script(script_name: str, user_params: dict):
    run_generic_script(script_name=script_name, params=user_params)