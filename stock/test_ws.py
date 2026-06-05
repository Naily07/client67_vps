import asyncio
import websockets
import json

JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzgwODU3MzAxLCJpYXQiOjE3ODA2ODQ1MDEsImp0aSI6IjQwMDIyMTJjMmMwNTQ2ZTlhZjI3NWU1NmI5Y2EyYTRlIiwidXNlcl9pZCI6MywidXNlcm5hbWUiOiJ2ZW5kZXVyMSIsImFjY291bnRfdHlwZSI6InZlbmRldXJzIn0.re5SrgArtlA2FRM8UYv6IDYN3Kpdq-u2vyHh1eHds_s"

async def test():
    url = f"ws://127.0.0.1:7500/ws/stock/?token={JWT_TOKEN}"
    async with websockets.connect(url) as ws:
        print("Connecté !")
        while True:
            msg = await ws.recv()
            print("Message reçu :", msg)

asyncio.run(test())
