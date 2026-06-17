import sys
import random
import bulletchess as chess
import main
import os
import time
import threading

TIME_LIMIT = main.TIME_LIMIT

def parse_position(board: chess.Board, tokens: list[str]) -> chess.Board:
    """Parses standard UCI position strings into the engine's board state."""
    if not tokens:
        return board
    
    # Isolate base position setup
    if tokens[0] == "startpos":
        board = chess.Board()
        remaining_tokens = tokens[1:]
    elif tokens[0] == "fen":
        if "moves" in tokens:
            moves_idx = tokens.index("moves")
            fen_str = " ".join(tokens[1:moves_idx])
            remaining_tokens = tokens[moves_idx:]
        else:
            fen_str = " ".join(tokens[1:])
            remaining_tokens = []
        board = chess.Board.from_fen(fen_str)
    else:
        return board

    # Process move history tracking
    if remaining_tokens and remaining_tokens[0] == "moves":
        for move_str in remaining_tokens[1:]:
            try:
                board.apply(chess.Move.from_uci(move_str))
            except ValueError:
                continue
    return board

def get_time(tokens, board) -> tuple[float, int]:
    """
    Parses UCI 'go' command tokens and calculates the search time_limit and max_depth.
    """
    wtime = btime = winc = binc = movestogo = movetime = depth = None
    infinite = False

    iterator = iter(tokens)
    for token in iterator:
        try:
            if token == "wtime": wtime = int(next(iterator))
            elif token == "btime": btime = int(next(iterator))
            elif token == "winc": winc = int(next(iterator))
            elif token == "binc": binc = int(next(iterator))
            elif token == "movestogo": movestogo = int(next(iterator))
            elif token == "movetime": movetime = int(next(iterator))
            elif token == "depth": depth = int(next(iterator))
            elif token == "infinite": infinite = True
        except StopIteration:
            break

    # Determine allocated time budget (in seconds)
    if movetime is not None:
        time_limit = movetime / 1000.0
    elif infinite:
        time_limit = main.TIME_LIMIT
    else:
        # Dynamic calculation based on side-to-move clock
        my_time = wtime if board.turn == chess.WHITE else btime
        my_inc = winc if board.turn == chess.WHITE else binc
        
        if my_time is not None:
            my_time_sec = my_time / 1000.0
            my_inc_sec = (my_inc / 1000.0) if my_inc is not None else 0.0
            
            if movestogo is not None:
                time_limit = (my_time_sec / max(1, movestogo)) + my_inc_sec
            else:
                # Assume an average remaining baseline of 35 moves
                time_limit = (my_time_sec / 35.0) + my_inc_sec
            
            # Establish safety cushion to prevent losing on time flag drops
            time_limit = max(0.02, min(time_limit, my_time_sec * 0.85))
        else:
            time_limit = None

    if depth is not None:
        max_depth = depth
        if time_limit is None:
            time_limit = main.TIME_LIMIT
    else:
        max_depth = 100
        if time_limit is None:
            time_limit = 3.0
    
    return time_limit, max_depth

def parse_go(board: chess.Board, tokens: list[str], is_ponder: bool = False) -> None:
    def run_and_print(board: main.EvalBoard, time_limit: float, max_depth: int) -> None:
        best_move, _ = main.get_best_move(board, time_limit, max_depth)
        if best_move is None:
            raise ValueError
        try:
            ponder_move = main.get_pv(board, best_move)[1]
            print(f"bestmove {best_move.uci()} ponder {ponder_move}", flush=True)
        except IndexError:
            print(f"bestmove {best_move.uci()}")
    global TIME_LIMIT
    """Calculates active time management allocation budgets and fires search."""
    
    time_limit, max_depth = get_time(tokens, board)
    TIME_LIMIT = time_limit

    # Execute engine iterative deepening search
    b = main.EvalBoard.from_fen(board.fen())
    thread = threading.Thread(
        target=run_and_print,
        args=(b, time_limit, max_depth),
        daemon=True
    )
    thread.start()

def uci_loop() -> None:
    """Core text input stream orchestration loop compliant with the UCI specification."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore # Ensure line buffering is strictly active
    main.USE_UCI = True                          # Override engine flag to enforce proper logging output
    main.USE_OPENING = True
    main.USE_GAVIOTA = True if os.path.exists("gaviota_5") else False
    board = chess.Board()
    
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        parts = line.split()
        if not parts:
            continue
            
        cmd = parts[0]
        if cmd == "uci":
            print("id name KikiBot")
            print("id author kiranmjlowe")
            print("option name Ponder type check default false")
            print("uciok", flush=True)
        elif cmd == "isready":
            print("readyok", flush=True)
        elif cmd == "ucinewgame":
            main.tt.clear()
            main.clear_killer()
            main.clear_history()
            board = chess.Board()
        elif cmd == "position":
            board = parse_position(board, parts[1:])
        elif cmd == "setoption":
            if len(parts) >= 5:
                if parts[1] == "name" and parts[2] == "Ponder":
                    main.PONDER = parts[4].lower() == "true"
        elif cmd == "ponderhit":
            main.END = time.perf_counter() + TIME_LIMIT
        elif cmd == "stop":
            main.END = 0.0
        elif cmd == "go":
            if len(parts) >= 2 and parts[1] == "ponder":
                parse_go(board, parts[2:], True)
            else:
                parse_go(board, parts[1:], False)
        elif cmd == "quit":
            break

if __name__ == "__main__":
    uci_loop()