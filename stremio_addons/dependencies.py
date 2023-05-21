from fastapi import Request


def get_http_client(request: Request):
    return request.state.http_client


def get_cloudflare_client(request: Request):
    return request.state.cloudflare_client
