from utils.retry import is_retryable_exception


def test_rate_limit_runtime_error_is_retryable():
    exc = RuntimeError("Tencent Docs API failed: code=400007 message=Requests Over Limit. Please Retry Later.")
    assert is_retryable_exception(exc) is True


def test_non_retryable_runtime_error():
    exc = RuntimeError("Tencent Docs API failed: code=400001 message=invalid param")
    assert is_retryable_exception(exc) is False
