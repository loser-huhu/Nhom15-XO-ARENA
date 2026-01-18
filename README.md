# Tic Tac Toe Multiplayer Application

This project is a web-based multiplayer Tic Tac Toe game built using Flask, Flask-SocketIO, and SQLAlchemy. Players can join rooms, make moves, chat with each other, and even request rematches. The game supports room creation with optional passwords and tracks player scores.

## Features

- **Real-Time Multiplayer:** Players can join existing rooms or create new ones to play Tic Tac Toe with others in real time.
- **Room Management:** Each room can have up to two players. Additional players can join as spectators.
- **Persistent Game State:** The game state, including the board and scores, is stored in a SQLite database, ensuring that game progress is not lost.
- **Password-Protected Rooms:** Players can create rooms that require a password to join, adding an extra layer of privacy.
- **Chat Functionality:** Players in a room can send messages to each other, which are stored and displayed in real time.
- **Reconnect Handling:** If a player disconnects and reconnects, their game state is restored.
- **Rematch Support:** Players can request a rematch after a game ends.

## Project Structure

- **app.py**: The main Flask application file. It handles the game logic, socket events, and database interactions.
- **templates/**: Contains the HTML templates for the web pages.
  - `index.html`: The landing page where players can join or create rooms.
  - `room.html`: The game room interface where players make moves and chat.
- **tic_tac_toe.db**: The SQLite database file where game data is stored.

## Key Components

### Flask and Flask-SocketIO
- Flask is used to serve the web pages and handle HTTP requests.
- Flask-SocketIO manages real-time communication between the server and clients, allowing for instant updates of game moves, chat messages, and player statuses.

### SQLAlchemy
- SQLAlchemy is used for database management, with models defined for Rooms, Players, Moves, and ChatMessages.

### Game Logic
- The game board is stored as a string in the database, where each character represents a cell on the Tic Tac Toe board.
- The `check_winner` function checks if there's a winning combination on the board after each move.
- The current player's turn, scores, and game state are managed in the Room model.

## Routes

- **`/`**: The landing page where players can create or join rooms.
- **`/room/<room_id>/<int:size>`**: Endpoint to create a new room with the specified size (e.g., 3x3 for a standard Tic Tac Toe game).
- **`/join/<room_id>`**: Endpoint to join an existing room. If the room is password-protected, the correct password must be provided.

## Socket Events

- **`join`**: Handles player joining a room.
- **`make_move`**: Processes a player's move and checks for a winner.
- **`rematch`**: Resets the board and starts a new game in the same room.
- **`chat_message`**: Broadcasts a chat message to all players in the room.
- **`reconnect`**: Restores a player's game state if they reconnect.
- **`disconnect`**: Handles player disconnection, updating the room and player states accordingly.

## Running the Project

You can use, `docker compose up` or run it yourself by following the instruction below

Firstly, create a virtual env, 
```
python3 -m venv venv && source venv/bin/activate
```

Secondly, install the requirements by running
```bash
pip install -r requirements.txt
```

To start the application, simply run:

```bash
python app.py
```
The server will start in debug mode, and you can access the game in your web browser at http://localhost:5000.

