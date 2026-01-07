import asyncio
import websockets
import json

JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY3OTM0NjI4LCJpYXQiOjE3Njc3NjE4MjgsImp0aSI6IjU5NWJhNmZlNDAxMjQxZmM4MGRjMDNmZjZhZTM4ZTkxIiwidXNlcl9pZCI6MiwidXNlcm5hbWUiOiJ0b2pvenIiLCJhY2NvdW50X3R5cGUiOiJ2ZW5kZXVycyJ9.q-JQA_mpFpOwoYwdFsh1ywUERA68oN9fE03NNb2dzlc"

async def test():
    url = f"wss://client67-vps.digievo.mg/ws/stock/?token={JWT_TOKEN}"
    async with websockets.connect(url) as ws:
        print("Connecté !")
        while True:
            msg = await ws.recv()
            print("Message reçu :", msg)

asyncio.run(test())
