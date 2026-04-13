from src.persistence.DatabaseLogger import DatabaseLogger


def run_test_job(param):
    logger = DatabaseLogger()

    logger.log_info("Writing to log from test_service.py")
