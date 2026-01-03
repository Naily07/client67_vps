import asyncio
import websockets
import json

JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY3NTk2NDY5LCJpYXQiOjE3Njc0MjM2NjksImp0aSI6IjQyZTcyYTQwYjZmOTQyY2NiNTU0MWRmODlhNDAyMjI0IiwidXNlcl9pZCI6MiwidXNlcm5hbWUiOiJ2ZW5kZXVyMSIsImFjY291bnRfdHlwZSI6InZlbmRldXJzIn0.UZvDCvnmA8DocUcRbNPbX6exYk7SsVccc3WlWXE9R8c"

async def test():
    url = f"ws://localhost/ws/stock/?token={JWT_TOKEN}"
    async with websockets.connect(url) as ws:
        print("Connecté !")
        while True:
            msg = await ws.recv()
            print("Message reçu :", msg)

asyncio.run(test())
