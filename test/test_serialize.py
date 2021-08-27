from datetime import datetime as dt
from moulinette.interface import JSONExtendedEncoder


def test_json_extended_encoder(caplog):
    encoder = JSONExtendedEncoder()

    assert encoder.default(set([1, 2, 3])) == [1, 2, 3]

    assert encoder.default(dt(1917, 3, 8)) == "1917-03-08T00:00:00+00:00"

    assert encoder.default(None) == "None"
    for message in caplog.messages:
        assert "cannot properly encode in JSON" in message
