# /app/hypercorn_config.py
from hypercorn.config import Config

config = Config()
config.bind = ["0.0.0.0:8000"]   # Puerto interno en el contenedor
config.workers = 2               # Con tus 4 vCPU, 2–4 workers es razonable
config.alpn_protocols = ["h2", "http/1.1"]
# HTTP/3 lo hará Caddy hacia fuera; aquí no hace falta QUIC
