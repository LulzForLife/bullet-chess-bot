import berserk
import bulletchess as chess
import main  # Added import for the custom engine

# 1. Authenticate with Lichess
try:
    with open("lichess-api-key", 'r') as f:
        TOKEN = f.read()
except KeyboardInterrupt:
    raise
except Exception:
    print("Unable to parse lichess-api.yml")
    exit(1)

print(f"Token selected: {TOKEN}")

session = berserk.TokenSession(TOKEN)
client = berserk.Client(session=session)

# Get the bot's own user ID so we can check our color later
BOT_ID = client.account.get()['id']
print(f"Bot connected successfully as ID: {BOT_ID}")
print("Listening for challenges and games...")

# Keep track of which color we are for active games
# Key: game_id, Value: True (if White) or False (if Black)
game_colors = {}

# 2. Loop continuously to catch game invites and state changes
for event in client.bots.stream_incoming_events():
    
    # Accept incoming game challenges automatically
    if event['type'] == 'challenge':
        challenge_id = event['challenge']['id']
        client.bots.accept_challenge(challenge_id)
        print(f"Accepted challenge: {challenge_id}")

    # Handle actual live games
    elif event['type'] == 'gameStart':
        game_id = event['game']['id']
        print(f"\nGame started! ID: {game_id}")
        
        # Stream the states of this specific game
        for state in client.bots.stream_game_state(game_id):
            
            # Default time values to fall back on
            wtime = btime = 30000
            winc = binc = 0
            
            # Determine moves, color, and clocks based on the event payload
            if state['type'] == 'gameFull':
                moves_played = state['state']['moves']
                
                # Check if our BOT_ID matches the white player's ID
                white_id = state['white'].get('id')
                is_white = (BOT_ID == white_id)
                game_colors[game_id] = is_white
                
                # Extract clocks (Lichess returns these in milliseconds)
                wtime = state['state'].get('wtime', 30000)
                btime = state['state'].get('btime', 30000)
                winc = state['state'].get('winc', 0)
                binc = state['state'].get('binc', 0)
                
            elif state['type'] == 'gameState':
                moves_played = state['moves']
                # Retrieve our color from the dictionary we set up during 'gameFull'
                is_white = game_colors.get(game_id, True)
                
                # Extract clocks
                wtime = state.get('wtime', 30000)
                btime = state.get('btime', 30000)
                winc = state.get('winc', 0)
                binc = state.get('binc', 0)
            else:
                continue

            # Recreate the current board position using python-chess/bulletchess
            board = chess.Board()
            if moves_played:
                for move in moves_played.split():
                    board.apply(chess.Move.from_uci(move))

            # Check if it's our turn to move
            my_turn = (board.turn == chess.WHITE and is_white) or (board.turn == chess.BLACK and not is_white)

            # If it's our turn and the game isn't over, make a move
            if my_turn and not (board in chess.CHECKMATE or board in chess.DRAW):
                
                # Calculate active time management allocation based on Script 2
                my_time = wtime if is_white else btime
                my_inc = winc if is_white else binc
                
                my_time_sec = my_time / 1000.0
                my_inc_sec = my_inc / 1000.0
                
                # Assume an average remaining baseline of 35 moves
                time_limit = (my_time_sec / 35.0) + my_inc_sec
                
                # Establish safety cushion to prevent losing on time flag drops
                if hasattr(time_limit, "total_seconds"):
                    time_limit = time_limit.total_seconds() * 1000
                if hasattr(my_time_sec, "total_seconds"):
                    my_time_sec = my_time_sec.total_seconds() * 1000
                time_limit = max(0.02, min(time_limit, my_time_sec * 0.85))
                
                # Pass position to the engine (using main.EvalBoard)
                eval_board = main.EvalBoard.from_fen(board.fen())
                
                # Fetch best move (max_depth=100 arbitrarily set to rely on time_limit, identical to Script 2)
                chosen_move, evaluation = main.get_best_move(eval_board, time_limit, 100)
                
                if chosen_move:
                    # Send the move to Lichess
                    client.bots.make_move(game_id, chosen_move.uci())
                    print(f"[{'White' if is_white else 'Black'}] Played move: {chosen_move.uci()} (Evaluation: {evaluation}, Search Time Limit: {time_limit:.2f}s)")
