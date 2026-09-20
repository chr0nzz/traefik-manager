import threading
import time

import jwt
import requests

from core.env import APP_VERSION, logger

LEEWAY = 60
JWKS_CACHE_SECONDS = 600
JWKS_TIMEOUT = (3, 5)
USER_AGENT = f'traefik-manager/{APP_VERSION}'
HMAC_ALGS = ('HS256', 'HS384', 'HS512')
DEFAULT_ALGS = ('RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512', 'PS256', 'PS384', 'PS512')

_cache = {}
_lock = threading.Lock()


class IdTokenError(Exception):
    pass


def reset_cache() -> None:
    with _lock:
        _cache.clear()


def _fetch_jwks(jwks_uri: str) -> dict:
    resp = requests.get(jwks_uri, timeout=JWKS_TIMEOUT,
                        headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict) or not data.get('keys'):
        raise IdTokenError(f'{jwks_uri} returned no keys')
    return data


def _jwks(jwks_uri: str, refresh: bool = False) -> dict:
    now = time.time()
    with _lock:
        hit = _cache.get(jwks_uri)
        if hit and not refresh and now - hit[0] < JWKS_CACHE_SECONDS:
            return hit[1]
    data = _fetch_jwks(jwks_uri)
    with _lock:
        _cache[jwks_uri] = (now, data)
    return data


def _signing_key(jwks_uri: str, kid: str):
    for refresh in (False, True):
        try:
            keys = jwt.PyJWKSet.from_dict(_jwks(jwks_uri, refresh=refresh))
        except IdTokenError:
            raise
        except Exception as exc:
            raise IdTokenError(f'the keys at {jwks_uri} could not be read ({exc})') from exc
        usable = [k for k in keys.keys if not k.public_key_use or k.public_key_use == 'sig']
        if kid:
            for key in usable:
                if key.key_id == kid:
                    return key.key
        elif len(usable) == 1:
            return usable[0].key
        elif usable:
            raise IdTokenError('the id_token names no key id and the provider publishes several keys')
        if refresh:
            break
    raise IdTokenError(f'the provider does not publish the key {kid or "(no key id)"} the id_token was signed with')


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
    if alg not in allowed_algorithms(cfg):
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
            key = _signing_key(jwks_uri, str(header.get('kid') or ''))
        except IdTokenError:
            raise
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
