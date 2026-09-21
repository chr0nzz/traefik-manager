"""A provider's error often quotes the request it failed to make, which puts the channel's
token or webhook URL into the delivery log and into the interface."""

import pytest

import core.notify_providers as providers


# --- a channel's own secrets never reach the log -----------------------------------------

@pytest.mark.parametrize('channel,err', [
    ({'kind': 'telegram', 'token': 'bot123456:AAHsupersecrettokenvalue', 'token2': '',
      'password': ''},
     'POST https://api.telegram.org/botbot123456:AAHsupersecrettokenvalue/sendMessage failed'),
    ({'kind': 'discord', 'url': 'https://discord.com/api/webhooks/12345678/abcdefghijklmnop'},
     'request to https://discord.com/api/webhooks/12345678/abcdefghijklmnop returned 401'),
    ({'kind': 'generic', 'url': 'https://hooks.example.com/t/verylongsecrettoken'},
     'connection to https://hooks.example.com/t/verylongsecrettoken refused'),
    ({'kind': 'gotify', 'token': 'AsecretGotifyToken123'},
     'server said: invalid token AsecretGotifyToken123'),
])
def test_a_provider_error_does_not_carry_the_channel_secret(channel, err):
    scrubbed = providers.scrub(channel, err)
    for field in providers.SECRET_FIELDS:
        value = channel.get(field)
        if value:
            assert value not in scrubbed, f'{field} survived into the error text'
    url = channel.get('url', '')
    if url and channel['kind'] in providers.SECRET_URL_KINDS:
        assert url not in scrubbed, 'the webhook URL is the credential and must be masked'
    assert '***' in scrubbed, 'something should have been replaced'


def test_scrubbing_leaves_an_ordinary_error_alone():
    channel = {'kind': 'telegram', 'token': 'bot123456:AAHsupersecrettokenvalue'}
    assert providers.scrub(channel, 'timed out after 5s') == 'timed out after 5s'


def test_send_scrubs_before_it_returns():
    channel = {'kind': 'unknown-kind-that-does-not-exist', 'token': 'AsecretTokenValue123'}
    ok, err = providers.send(channel, 'info', 't', 'm', 'ts')
    assert not ok and 'AsecretTokenValue123' not in err


