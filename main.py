from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

clients = []
polls = []
poll_counter = 0

@app.get("/")
async def root():
    return {"message": "hello world"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global poll_counter
    await websocket.accept()
    clients.append(websocket)

    # Track votes per client
    websocket.user_votes = {}

    # Send existing polls to the new client
    for p in polls:
        await websocket.send_text(json.dumps({"type": "poll", "poll": p}))

    try:
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)
            
            # --- Create a new poll ---
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

            # --- Handle voting ---
            elif data_json["type"] == "vote":
                poll_id = data_json["pollId"]
                vote_type = data_json["vote"]  # "like", "dislike", or None
                prev_vote = websocket.user_votes.get(poll_id)

                for poll in polls:
                    if poll["id"] == poll_id:
                        # Remove previous vote
                        if prev_vote == "like":
                            poll["likes"] -= 1
                        elif prev_vote == "dislike":
                            poll["dislikes"] -= 1

                        # Apply new vote if not None
                        if vote_type == "like":
                            poll["likes"] += 1
                        elif vote_type == "dislike":
                            poll["dislikes"] += 1

                        # Update user's vote
                        if vote_type is None:
                            websocket.user_votes.pop(poll_id, None)
                        else:
                            websocket.user_votes[poll_id] = vote_type

                        await broadcast({"type": "vote", "poll": poll})
                        break

            # --- Handle deleting a poll ---
            elif data_json["type"] == "delete_poll":
                poll_id = data_json["pollId"]
                # Remove the poll from list
                polls[:] = [p for p in polls if p["id"] != poll_id]
                # Remove this poll from all users' votes
                for client in clients:
                    if hasattr(client, "user_votes") and poll_id in client.user_votes:
                        client.user_votes.pop(poll_id)
                # Broadcast deletion
                await broadcast({"type": "delete_poll", "pollId": poll_id})

    except WebSocketDisconnect:
        clients.remove(websocket)


async def broadcast(message: dict):
    """Send a message to all connected clients."""
    disconnected = []
    for client in clients:
        try:
            await client.send_text(json.dumps(message))
        except WebSocketDisconnect:
            disconnected.append(client)
    for d in disconnected:
        clients.remove(d)


