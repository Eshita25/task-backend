# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import os
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store connected WebSocket clients
clients = []
polls = [] 
poll_counter = 0


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global poll_counter
    await websocket.accept()
    clients.append(websocket)

    # Send all existing polls to the newly connected client
    for p in polls:
        await websocket.send_text(json.dumps({"type": "poll", "poll": p}))

    try:
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)

            if data_json["type"] == "poll":
                poll_counter += 1
                poll_data = {
                    "id": poll_counter,
                    "question": data_json["poll"]["question"],
                    "likes": 0,
                    "dislikes": 0
                }
                polls.append(poll_data)

                await broadcast({"type": "poll", "poll": poll_data})

            # A vote was cast
            elif data_json["type"] == "vote":
                poll_id = data_json["pollId"]
                vote_type = data_json["vote"]

                # Find and update the poll
                for poll in polls:
                    if poll["id"] == poll_id:
                        if vote_type == "like":
                            poll["likes"] += 1
                        elif vote_type == "dislike":
                            poll["dislikes"] += 1

                        # Broadcast updated poll to everyone
                        await broadcast({"type": "vote", "poll": poll})
                        break

    except WebSocketDisconnect:
        clients.remove(websocket)


async def broadcast(message: dict):
    """Send message to all connected clients."""
    disconnected = []
    for client in clients:
        try:
            await client.send_text(json.dumps(message))
        except WebSocketDisconnect:
            disconnected.append(client)
    for d in disconnected:
        clients.remove(d)
