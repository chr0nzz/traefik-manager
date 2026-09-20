import threading
import time

import jwt
from jwt import PyJWKClient

from core.env import logger

LEEWAY = 60
JWKS_CACHE_SECONDS = 600
HMAC_ALGS = ('HS256', 'HS384', 'HS512')
DEFAULT_ALGS = ('RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512', 'PS256', 'PS384', 'PS512')

_clients = {}
_lock = threading.Lock()


class IdTokenError(Exception):
    pass


def _jwks_client(jwks_uri: str) -> PyJWKClient:
    with _lock:
        client = _clients.get(jwks_uri)
        if client is None:
            client = PyJWKClient(jwks_uri, cache_keys=True, lifespan=JWKS_CACHE_SECONDS)
            _clients[jwks_uri] = client
        return client


def reset_cache() -> None:
    with _lock:
        _clients.clear()


def allowed_algorithms(cfg: dict) -> list:
    advertised = cfg.get('id_token_signing_alg_values_supported')
    if not isinstance(advertised, list) or not advertised:
        return list(DEFAULT_ALGS) + list(HMAC_ALGS)
    allowed = [str(a) for a in advertised if str(a) in DEFAULT_ALGS + HMAC_ALGS]
    return allowed or list(DEFAULT_ALGS)


def verify(id_token: str, cfg: dict, client_id: str, client_secret: str = '', now: float = None) -> dict:
    if not id_token:
        raise IdTokenError('the provider returned no id_token')
    try:
        header = jwt.get_unverified_header(id_token)
    except Exception as exc:
        raise IdTokenError(f'the id_token is not a readable JWT ({exc})') from exc

    alg = str(header.get('alg') or '')
    allowed = allowed_algorithms(cfg)
    if alg not in allowed:
        raise IdTokenError(f'the id_token is signed with {alg or "no algorithm"}, which this provider does not advertise')

    if alg in HMAC_ALGS:
        if not client_secret:
            raise IdTokenError(f'the id_token is signed with {alg}, which needs the client secret')
        key = client_secret
    else:
        jwks_uri = str(cfg.get('jwks_uri') or '')
        if not jwks_uri:
            raise IdTokenError('the provider discovery document has no jwks_uri, so the id_token signature cannot be checked')
        try:
            key = _jwks_client(jwks_uri).get_signing_key_from_jwt(id_token).key
        except Exception as exc:
            raise IdTokenError(f'the signing key could not be read from {jwks_uri} ({exc})') from exc

    issuer = str(cfg.get('issuer') or '')
    options = {'require': ['exp', 'iat', 'iss', 'aud'], 'verify_aud': True, 'verify_iss': bool(issuer)}
    try:
        claims = jwt.decode(id_token, key, algorithms=[alg], audience=client_id,
                            issuer=issuer or None, leeway=LEEWAY, options=options)
    except jwt.ExpiredSignatureError as exc:
        raise IdTokenError('the id_token has expired') from exc
    except jwt.InvalidAudienceError as exc:
        raise IdTokenError(f'the id_token was issued for another client, not {client_id}') from exc
    except jwt.InvalidIssuerError as exc:
        raise IdTokenError(f'the id_token was issued by another provider, not {issuer}') from exc
    except jwt.InvalidSignatureError as exc:
        raise IdTokenError('the id_token signature does not match the provider key') from exc
    except Exception as exc:
        raise IdTokenError(f'the id_token failed verification ({exc})') from exc

    azp = str(claims.get('azp') or '')
    aud = claims.get('aud')
    if isinstance(aud, list) and len(aud) > 1 and azp and azp != client_id:
        raise IdTokenError('the id_token names another authorized party')

    iat = claims.get('iat')
    if isinstance(iat, (int, float)) and iat > (now if now is not None else time.time()) + LEEWAY:
        raise IdTokenError('the id_token was issued in the future, check the clock on this host and the provider')

    logger.debug("OIDC id_token verified (%s, issuer %s)", alg, issuer or 'unchecked')
    return claims
