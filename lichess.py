import berserk
import berserk.exceptions
import bulletchess as chess
import main
import time
import os

main.USE_OPENING = True
main.USE_SYZYGY = os.path.exists("syzygy")
main.USE_UCI = False

try:
    with open("lichess-api-key", 'r') as f:
        TOKEN = f.read()
except KeyboardInterrupt:
    raise
except Exception:
    print("Unable to parse lichess-api.yml")
    exit(1)

while True:
    try:
        session = berserk.TokenSession(TOKEN)
        client = berserk.Client(session=session)

        BOT_ID = client.account.get()['id']
        print(f"Bot connected successfully as ID: {BOT_ID}")
        print("Listening for challenges and games...")

        game_colors = {}

        for event in client.bots.stream_incoming_events():
            
            if event['type'] == 'challenge':
                challenge_id = event['challenge']['id']
                client.bots.accept_challenge(challenge_id)
                print(f"Accepted challenge: {challenge_id}")

            elif event['type'] == 'gameStart':
                game_id = event['game']['id']
                print(f"\nGame started! ID: {game_id}")
                
                for state in client.bots.stream_game_state(game_id):
                    
                    wtime = btime = 30000
                    winc = binc = 0
                    
                    if state['type'] == 'gameFull':
                        moves_played = state['state']['moves']
                        
                        white_id = state['white'].get('id')
                        is_white = (BOT_ID == white_id)
                        game_colors[game_id] = is_white
                        
                        wtime = state['state'].get('wtime', 30000)
                        btime = state['state'].get('btime', 30000)
                        winc = state['state'].get('winc', 0)
                        binc = state['state'].get('binc', 0)
                        
                    elif state['type'] == 'gameState':
                        moves_played = state['moves']
                        is_white = game_colors.get(game_id, True)
                        
                        wtime = state.get('wtime', 30000)
                        btime = state.get('btime', 30000)
                        winc = state.get('winc', 0)
                        binc = state.get('binc', 0)
                    else:
                        continue

                    board = main.EvalBoard()
                    if moves_played:
                        for move in moves_played.split():
                            board.apply(chess.Move.from_uci(move), None, None, None)

                    my_turn = (board.turn == chess.WHITE and is_white) or (board.turn == chess.BLACK and not is_white)

                    if my_turn and not board.is_game_over:
                        
                        my_time = wtime if is_white else btime
                        my_inc = winc if is_white else binc
                        
                        my_time_sec = my_time / 1000.0
                        my_inc_sec = my_inc / 1000.0
                        
                        time_limit = (my_time_sec / 35.0) + my_inc_sec
                        
                        if hasattr(time_limit, "total_seconds"):
                            time_limit = time_limit.total_seconds() * 1000
                        if hasattr(my_time_sec, "total_seconds"):
                            my_time_sec = my_time_sec.total_seconds() * 1000
                        time_limit = max(0.02, min(time_limit, my_time_sec * 0.85))
                        if time_limit > 10000:
                            time_limit = 10
                        
                        chosen_move, evaluation = main.get_best_move(board, time_limit, 100)
                        if chosen_move is None:
                            chosen_move, evaluation = main.get_best_move(board, 86400, 1)
                        
                        if chosen_move:
                            client.bots.make_move(game_id, chosen_move.uci())
                            print(f"[{'White' if is_white else 'Black'}] Played move: {chosen_move.uci()} (Evaluation: {evaluation}, Search Time Limit: {time_limit:.2f}s)")

    except KeyboardInterrupt:
        raise
    except berserk.exceptions.ResponseError as e:
        print(f"Encountered Exception: {e}")
        print("Waiting 30 seconds...")
        for t in range(30):
            print(f"{29 - t} seconds remaining...   ", end='\r')
            time.sleep(1)
        print("Restarting...                ")
    except Exception as e:
        print(f"Encountered Exception: {e}")
        print("Restarting...")
