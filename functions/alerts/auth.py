import os
import json

import jwt


def unauthorized(event):
    """Return a 401 response when JWT_SECRET is set and the request has no valid HS256 bearer token, else None."""
    secret = os.getenv('JWT_SECRET')
    if not secret:
        return None
    headers = {k.lower(): v for k, v in (event.get('headers') or {}).items()}
    scheme, _, token = (headers.get('authorization') or '').partition(' ')
    try:
        if scheme.lower() != 'bearer':
            raise jwt.InvalidTokenError('missing bearer token')
        jwt.decode(token.strip(), secret, algorithms=['HS256'])
        return None
    except jwt.InvalidTokenError:
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'WWW-Authenticate': 'Bearer'},
            'body': json.dumps({'error': 'Unauthorized'})
        }
