import asyncio
import websockets
import json

JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzgxMDA3OTIxLCJpYXQiOjE3ODA4MzUxMjEsImp0aSI6IjM2OWVjOWM1ZTI0NjQwZTY5Y2E0MDU3ZDBlYWM4ZjE5IiwidXNlcl9pZCI6MiwidXNlcm5hbWUiOiJ0b2pvenIiLCJhY2NvdW50X3R5cGUiOiJ2ZW5kZXVycyJ9.ROVl_PNJSU8WHwQQU2ATOdafTK57mN9a-wKz_3mlIHU"

async def test():
    url = f"ws://127.0.0.1:7500/ws/customer/?token={JWT_TOKEN}"
    async with websockets.connect(url) as ws:
        print("Connecté !")
        while True:
            msg = await ws.recv()
            print("Message reçu :", msg)

asyncio.run(test())
