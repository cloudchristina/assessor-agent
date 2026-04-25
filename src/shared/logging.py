"""Structured-JSON logger backed by aws-lambda-powertools."""
from aws_lambda_powertools import Logger


def get_logger(service: str) -> Logger:
    return Logger(service=service, level="INFO", use_rfc3339=True)
