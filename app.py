from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError
import os

# Xóa db cũ nếu cần thiết (optional)
# if os.path.exists("tic_tac_toe.db"):
#     os.remove("tic_tac_toe.db")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tic_tac_toe.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*") # Cho phép kết nối thoải mái hơn

# --- MODELS ---
class Room(db.Model):
    id = db.Column(db.String(80), primary_key=True)
    size = db.Column(db.Integer, nullable=False)
    board = db.Column(db.Text, nullable=False)
    turn = db.Column(db.Integer, default=1)
    player1_id = db.Column(db.String(80), nullable=True) # Lưu SID socket
    player2_id = db.Column(db.String(80), nullable=True) # Lưu SID socket
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

# --- HELPERS ---
def get_room_names(room_id):
    """Lấy tên hiển thị cho frontend"""
    p1_entry = Player.query.filter_by(room_id=room_id, player_number=1).first()
    p2_entry = Player.query.filter_by(room_id=room_id, player_number=2).first()
    return {
        1: p1_entry.nickname if p1_entry else "Waiting...",
        2: p2_entry.nickname if p2_entry else "Waiting..."
    }

def check_winner(board, size):
    # Logic check win (giữ nguyên)
    for i in range(size):
        if all(board[i*size + j] == board[i*size] and board[i*size] != ' ' for j in range(size)): return True
        if all(board[j*size + i] == board[i] and board[i] != ' ' for j in range(size)): return True
    if all(board[i*size + i] == board[0] and board[0] != ' ' for i in range(size)): return True
    if all(board[i*size + (size-i-1)] == board[size-1] and board[size-1] != ' ' for i in range(size)): return True
    return False

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

# --- SOCKET EVENTS (ĐÃ SỬA LỖI LOGIC) ---

@socketio.on('join')
def handle_join(data):
    room_id = data['room_id']
    nickname = data.get('nickname', 'Player')
    sid = request.sid
    join_room(room_id)

    print(f"DEBUG: User {nickname} ({sid}) joining room {room_id}")

    room = db.session.get(Room, room_id)
    if not room:
        return

    # Kiểm tra xem player này đã có trong DB chưa (trường hợp reconnect)
    player = Player.query.filter_by(sid=sid).first()
    
    if not player:
        # Nếu chưa có, tìm slot trống
        player_num = 0
        if not room.player1_id:
            player_num = 1
            room.player1_id = sid
        elif not room.player2_id:
            player_num = 2
            room.player2_id = sid
        else:
            # Phòng đã đầy -> Spectator
            names = get_room_names(room_id)
            emit('spectator', {'size': room.size, 'player_names': names})
            return

        # Tạo player mới
        try:
            new_player = Player(sid=sid, room_id=room_id, player_number=player_num, nickname=nickname)
            db.session.add(new_player)
            db.session.commit()
            
            # Gửi thông tin cá nhân cho người chơi
            emit('set_player', player_num)
            
        except Exception as e:
            print(f"Error adding player: {e}")
            db.session.rollback()
            return
    
    # Cập nhật lại UI cho TẤT CẢ mọi người
    names = get_room_names(room_id)
    socketio.emit('update_names', names, room=room_id)
    
    # Gửi trạng thái bàn cờ hiện tại
    emit('room_joined', {
        'room_id': room_id,
        'board': room.board,
        'size': room.size,
        'turn': room.turn,
        'player_names': names
    })
    print(f"DEBUG: Join success. Player {player.player_number if player else 'New'} - Names: {names}")


@socketio.on('make_move')
def handle_move(data):
    room_id = data['room_id']
    move = int(data['move'])
    room = Room.query.get(room_id)
    player = Player.query.get(request.sid)

    # Validate: Phải là player, đúng lượt, ô trống
    if player and room and room.turn == player.player_number:
        board_list = list(room.board)
        if board_list[move] == ' ':
            # Cập nhật bàn cờ
            symbol = 'X' if player.player_number == 1 else 'O'
            board_list[move] = symbol
            room.board = ''.join(board_list)
            
            # Check win/draw
            winner = 0
            game_ended = False
            if check_winner(board_list, room.size):
                winner = player.player_number
                if winner == 1: room.player1_score += 1
                else: room.player2_score += 1
                game_ended = True
            elif ' ' not in board_list:
                winner = 0 # Draw
                game_ended = True
            
            # Gửi nước đi
            emit('move_made', {'move': move, 'player': player.player_number}, room=room_id)
            
            if game_ended:
                emit('game_over', {'winner': winner}, room=room_id)
            else:
                # Đổi lượt
                room.turn = 2 if player.player_number == 1 else 1
            
            db.session.commit()

@socketio.on('chat_message')
def handle_chat(data):
    room_id = data['room_id']
    msg = data['message']
    player = Player.query.get(request.sid)
    
    if player:
        # Gửi tin nhắn ngay lập tức (không cần lưu DB để test nhanh)
        emit('receive_message', {
            'player': player.player_number,
            'message': msg
        }, room=room_id)
    else:
        print("DEBUG: Chat failed - Player not found in DB")

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
    sid = request.sid
    player = Player.query.get(sid)
    if player:
        print(f"DEBUG: Player {player.nickname} disconnected")
        room = Room.query.get(player.room_id)
        
        # Xóa khỏi slot trong Room
        if room:
            if player.player_number == 1: room.player1_id = None
            elif player.player_number == 2: room.player2_id = None
            
            # Xóa player khỏi DB
            db.session.delete(player)
            db.session.commit()
            
            # Nếu phòng trống thì xóa phòng luôn để tránh rác
            if not room.player1_id and not room.player2_id:
                db.session.delete(room)
                db.session.commit()
            else:
                # Báo cho người còn lại biết
                emit('player_disconnected', {'player_number': player.player_number}, room=room.id)
                names = get_room_names(room.id)
                socketio.emit('update_names', names, room=room.id)

if __name__ == '__main__':
    # Dùng allow_unsafe_werkzeug=True để chạy môi trường dev mượt hơn
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)