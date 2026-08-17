if __name__ == "__main__":
    import sys
    from pathlib import Path

    root_dir = Path(__file__).resolve().parent.parent
    if str(root_dir) not in sys.path:
        sys.path.append(str(root_dir))

import main

import berserk
import berserk.exceptions
import bulletchess as chess

import time
import os
import http.client
import json
import random
import threading

main.USE_OPENING = True
main.USE_SYZYGY = os.path.exists("syzygy")
main.USE_UCI = False

KEYBOARD_INTERRUPT = 0
API_KEY_ERROR = 100
UNKNOWN_BOT_EXCEPTION = 101
UNKNOWN_RESPONSE_EXCEPTION = 102
WATCHDOG_CANCEL_ERROR = 103

TIME_CONTROL = "blitz"
SECONDS = 180
INC = 0
TIME_WAIT = 60

UNSUCCESSFUL = []

try:
    with open("lichess-api-key", 'r') as f:
        TOKEN = f.read()
except KeyboardInterrupt:
    raise
except Exception:
    print("Unable to parse lichess-api-key file")
    exit(API_KEY_ERROR)

def get_potential_bots(my_rating: int, rating_diff: int = 300) -> list[str]:
    conn = http.client.HTTPSConnection("lichess.org")

    headers = {"Accept": "application/x-ndjson"}
    conn.request("GET", "/api/bot/online", headers=headers)

    response = conn.getresponse()
    if response.status != 200:
        conn.close()
        raise RuntimeError(f"Lichess API returned status {response.status}")

    matching_bots = []

    try:
        while True:
            line = response.readline()
            if not line:
                break

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            bot = json.loads(line_str)

            perf = bot.get("perfs", {}).get(TIME_CONTROL, {})
            rating = perf.get("rating", 0)

            if abs(rating - my_rating) <= rating_diff:
                username = bot["username"]
                if username:
                    matching_bots.append(username)

    finally:
        conn.close()

    return matching_bots

def get_random_bot(my_rating: int) -> str:

    bots = []
    rating_diff = 100
    while len(bots) < 5:
        bots = get_potential_bots(my_rating, rating_diff)
        for bot in UNSUCCESSFUL:
            if bot in bots:
                bots.remove(bot)
        rating_diff += 50

    return random.choice(bots)

def challenge_timeout_watchdog(client: berserk.Client, challenge_id: str, active_flag: dict[str, bool], timeout_sec: int = 15) -> None:
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if not active_flag.get("pending", True):
            return
        time.sleep(1)

    if active_flag.get("pending", True):
        print(f"\nOpponent did not respond within {timeout_sec}s. Canceling challenge {challenge_id}...")
        try:
            client.challenges.cancel(challenge_id)
        except berserk.exceptions.ResponseError as e:
            if e.status_code == 404:
                print(f"Challenge {challenge_id} doesn't exist. Please restart.")
                os._exit(WATCHDOG_CANCEL_ERROR)
        except Exception as e:
            print(f"Failed to cancel challenge: {e}")

while True:
    try:
        session = berserk.TokenSession(TOKEN)
        client = berserk.Client(session=session)

        account = client.account.get()
        BOT_ID = account['id']
        print(f"Bot connected successfully as ID: {BOT_ID}")
        print("Listening for challenges and games...")

        opponent = get_random_bot(account['perfs'][TIME_CONTROL]['rating'])
        UNSUCCESSFUL.append(opponent)
        game = client.challenges.create(opponent, True, SECONDS, INC)
        challenge_state = {"pending": True}

        timer_thread = threading.Thread(
            target=challenge_timeout_watchdog,
            args=(client, game['id'], challenge_state),
            daemon=True
        )
        timer_thread.start()

        print(f"\nSent challenge! ID: {game['id']}")

        game_colors = {}

        for event in client.bots.stream_incoming_events():
            
            if event['type'] == 'challenge':
                if event['challenge']['challenger']['id'] == BOT_ID:
                    continue
                challenge_id = event['challenge']['id']
                client.bots.decline_challenge(challenge_id)
                print(f"Declined challenge: {challenge_id}")

            elif event['type'] == 'gameStart':
                game_id = event['game']['id']
                print(f"\nGame started! ID: {game_id}")

                fen = main.chs.STARTING_FEN
                
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

                        if state['initialFen'] != 'startpos':
                            fen = state['initialFen']
                        
                    elif state['type'] == 'gameState':
                        moves_played = state['moves']
                        is_white = game_colors.get(game_id, True)
                        
                        wtime = state.get('wtime', 30000)
                        btime = state.get('btime', 30000)
                        winc = state.get('winc', 0)
                        binc = state.get('binc', 0)
                    else:
                        continue

                    board = main.EvalBoard.from_fen(fen)
                    if moves_played:
                        for move in moves_played.split():
                            board.apply(chess.Move.from_uci(move), None, None, None)

                    my_turn = (board.turn == chess.WHITE and is_white) or (board.turn == chess.BLACK and not is_white)

                    if my_turn and not board.is_game_over():
                        
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

            elif event['type'] == 'gameFinish':
                main.END = 0
                print("\nGame finished!")
                UNSUCCESSFUL.clear()
                time.sleep(1)

                opponent = get_random_bot(account['perfs'][TIME_CONTROL]['rating'])
                UNSUCCESSFUL.append(opponent)
                game = client.challenges.create(opponent, True, SECONDS, INC)
                print(f"Sent challenge! ID: {game['id']}")

                challenge_state = {"pending": True}
                threading.Thread(
                    target=challenge_timeout_watchdog,
                    args=(client, game['id'], challenge_state),
                    daemon=True
                ).start()

            elif event['type'] == 'challengeDeclined' or event['type'] == 'challengeCanceled':
                challenge_state["pending"] = False
                main.END = 0
                print("\nChallenge declined/canceled!")
                time.sleep(1)

                opponent = get_random_bot(account['perfs'][TIME_CONTROL]['rating'])
                UNSUCCESSFUL.append(opponent)
                game = client.challenges.create(opponent, True, SECONDS, INC)
                print(f"Sent challenge! ID: {game['id']}")

                challenge_state = {"pending": True}
                threading.Thread(
                    target=challenge_timeout_watchdog,
                    args=(client, game['id'], challenge_state),
                    daemon=True
                ).start()

    except KeyboardInterrupt:
        exit(KEYBOARD_INTERRUPT)
    except berserk.exceptions.ResponseError as e:
        print(f"Encountered Exception: {e}")
        print(e.response.headers)
        if e.status_code == 429:
            print(f"Waiting {TIME_WAIT} seconds...")
            for t in range(TIME_WAIT):
                print(f"{TIME_WAIT - t - 1} seconds remaining...   ", end='\r')
                time.sleep(1)
            TIME_WAIT += 30
        elif e.status_code == 400:
            pass
        else:
            print("Terminating process...")
            exit(UNKNOWN_RESPONSE_EXCEPTION)
        print("Restarting...                ")
    except Exception as e:
        print(f"Encountered Exception: {e}")
        print("Terminating process...")
        exit(UNKNOWN_BOT_EXCEPTION)
