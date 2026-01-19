from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm.exc import NoResultFound
import random
import gevent
import os

app = Flask(__name__);
app.config['SECRET_KEY'] = 'secret!'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tic_tac_toe.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# --- MODELS ---
class Room(db.Model):
    id = db.Column(db.String(80), primary_key=True)
    size = db.Column(db.Integer, nullable=False)
    board = db.Column(db.Text, nullable=False)
    turn = db.Column(db.Integer, default=1)
    player1_id = db.Column(db.String(80), nullable=True)
    player2_id = db.Column(db.String(80), nullable=True)
    player1_score = db.Column(db.Integer, default=0)
    player2_score = db.Column(db.Integer, default=0)
    password = db.Column(db.String(100), nullable=True)

class Player(db.Model):
    sid = db.Column(db.String(80), primary_key=True)
    room_id = db.Column(db.String(80), db.ForeignKey('room.id'), nullable=False)
    player_number = db.Column(db.Integer, nullable=False)
    nickname = db.Column(db.String(50), default="Unknown")

with app.app_context():
    db.create_all()

# --- HELPER FUNCTIONS ---
def get_room_names(room_id):
    p1 = Player.query.filter_by(room_id=room_id, player_number=1).first()
    p2 = Player.query.filter_by(room_id=room_id, player_number=2).first()
    return {
        1: p1.nickname if p1 else "Waiting...",
        2: p2.nickname if p2 else "Waiting..."
    }

def check_winner(board, size):
    # Logic thắng thua
    for i in range(size):
        if all(board[i*size + j] == board[i*size] and board[i*size] != ' ' for j in range(size)): return True
        if all(board[j*size + i] == board[i] and board[i] != ' ' for j in range(size)): return True
    if all(board[i*size + i] == board[0] and board[0] != ' ' for i in range(size)): return True
    if all(board[i*size + (size-i-1)] == board[size-1] and board[size-1] != ' ' for i in range(size)): return True
    return False

def get_bot_move(board_str, size):
    """Bot ngẫu nhiên (Dễ)"""
    board_list = list(board_str)
    empty_indices = [i for i, x in enumerate(board_list) if x == ' ']
    if not empty_indices:
        return None
    return random.choice(empty_indices)

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/room/<room_id>/<int:size>')
def create_room(room_id, size):
    password = request.args.get('password')
    existing_room = db.session.get(Room, room_id)
    if not existing_room:
        new_room = Room(id=room_id, size=size, board=' '*(size*size), password=password)
        db.session.add(new_room)
        db.session.commit()
    return render_template('room.html', room_id=room_id, size=size)

@app.route('/join/<room_id>')
def join_room_view(room_id):
    password = request.args.get('password')
    room = db.session.get(Room, room_id)
    if room and room.password == password:
        return render_template('room.html', room_id=room_id, size=room.size)
    return "Error: Room not found or wrong password", 404

# --- SOCKET EVENTS ---

@socketio.on('join')
def handle_join(data):
    room_id = data['room_id']
    nickname = data.get('nickname', 'Player')
    sid = request.sid
    join_room(room_id)

    room = db.session.get(Room, room_id)
    if not room: return

    # Check reconnect
    player = Player.query.filter_by(sid=sid).first()
    
    if not player:
        # Tìm slot trống
        player_num = 0
        if not room.player1_id:
            player_num = 1
            room.player1_id = sid
        elif not room.player2_id:
            # Nếu là phòng BOT thì slot 2 đã dành cho BOT rồi, người vào sau sẽ là Spectator
            if "bot" in room_id:
                 pass # Spectator logic below
            else:
                player_num = 2
                room.player2_id = sid
        
        if player_num == 0:
            names = get_room_names(room_id)
            emit('spectator', {'size': room.size, 'player_names': names})
            return

        # Tạo player mới
        try:
            new_player = Player(sid=sid, room_id=room_id, player_number=player_num, nickname=nickname)
            db.session.add(new_player)
            db.session.commit()
            emit('set_player', player_num)
        except:
            db.session.rollback()
            return
    
    names = get_room_names(room_id)
    socketio.emit('update_names', names, room=room_id)
    
    emit('room_joined', {
        'room_id': room_id,
        'board': room.board,
        'size': room.size,
        'turn': room.turn,
        'player_names': names
    })

@socketio.on('make_move')
def handle_move(data):
    room_id = data['room_id']
    move = int(data['move'])
    room = Room.query.get(room_id)
    player = Player.query.get(request.sid)

    # 1. NGƯỜI CHƠI ĐÁNH
    if player and room and room.turn == player.player_number:
        board_list = list(room.board)
        if board_list[move] == ' ':
            symbol = 'X' if player.player_number == 1 else 'O'
            board_list[move] = symbol
            room.board = ''.join(board_list)
            
            winner = 0
            game_ended = False
            
            # Check Win
            if check_winner(board_list, room.size):
                winner = player.player_number
                if winner == 1: room.player1_score += 1
                else: room.player2_score += 1
                game_ended = True
                emit('move_made', {'move': move, 'player': player.player_number}, room=room_id)
                emit('game_over', {'winner': winner}, room=room_id)
            
            # Check Draw
            elif ' ' not in board_list:
                game_ended = True
                emit('move_made', {'move': move, 'player': player.player_number}, room=room_id)
                emit('game_over', {'winner': 0}, room=room_id)
            
            # Next Turn
            else:
                emit('move_made', {'move': move, 'player': player.player_number}, room=room_id)
                room.turn = 2 if player.player_number == 1 else 1
            
            db.session.commit()

            # 2. BOT ĐÁNH (Nếu là phòng Bot và chưa hết game)
            is_bot_room = "bot" in room_id
            if not game_ended and is_bot_room and room.turn == 2:
                gevent.sleep(0.5) # Bot suy nghĩ
                
                bot_move = get_bot_move(room.board, room.size)
                if bot_move is not None:
                    board_list = list(room.board)
                    board_list[bot_move] = 'O'
                    room.board = ''.join(board_list)
                    
                    if check_winner(board_list, room.size):
                        room.player2_score += 1
                        emit('move_made', {'move': bot_move, 'player': 2}, room=room_id)
                        emit('game_over', {'winner': 2}, room=room_id)
                    elif ' ' not in board_list:
                        emit('move_made', {'move': bot_move, 'player': 2}, room=room_id)
                        emit('game_over', {'winner': 0}, room=room_id)
                    else:
                        emit('move_made', {'move': bot_move, 'player': 2}, room=room_id)
                        room.turn = 1 # Trả lượt người
                    
                    db.session.commit()

@socketio.on('chat_message')
def handle_chat(data):
    room_id = data['room_id']
    player = Player.query.get(request.sid)
    if player:
        emit('receive_message', {'player': player.player_number, 'message': data['message']}, room=room_id)

@socketio.on('rematch')
def handle_rematch(data):
    room_id = data['room_id']
    room = Room.query.get(room_id)
    room.board = ' ' * (room.size * room.size)
    room.turn = 1
    db.session.commit()
    emit('start_rematch', {'size': room.size}, room=room_id)

@socketio.on('disconnect')
def handle_disconnect():
    player = Player.query.get(request.sid)
    if player:
        room = Room.query.get(player.room_id)
        if room:
            if player.player_number == 1: room.player1_id = None
            elif player.player_number == 2: room.player2_id = None
            db.session.delete(player)
            db.session.commit()
            
            if not room.player1_id and not room.player2_id:
                db.session.delete(room)
                db.session.commit()
            else:
                names = get_room_names(room.id)
                socketio.emit('update_names', names, room=room.id)
                emit('player_disconnected', {}, room=room.id)

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
    # app.run(debug=True)
    # socketio.run(app, debug=True)