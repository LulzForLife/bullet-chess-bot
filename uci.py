import sys
import random
import bulletchess as chess
import main

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

def parse_go(board: chess.Board, tokens: list[str]) -> None:
    """Calculates active time management allocation budgets and fires search."""
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

    if depth:
        max_depth = depth
        if time_limit is None:
            time_limit = main.TIME_LIMIT
    else:
        max_depth = 100
        if time_limit is None:
            time_limit = 3.0

    # Execute engine iterative deepening search
    best_move, _ = main.get_best_move(board, time_limit, max_depth=max_depth)
    
    # Safe fallback if search was forced out prematurely
    if best_move is None:
        legal_moves = list(board.legal_moves())
        if not legal_moves:
            best_move = chess.Move.from_uci("0000")
        best_move = random.choice(legal_moves)

    if best_move:
        print(f"bestmove {best_move.uci()}", flush=True)

def uci_loop() -> None:
    """Core text input stream orchestration loop compliant with the UCI specification."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore # Ensure line buffering is strictly active
    main.USE_UCI = True                          # Override engine flag to enforce proper logging output
    main.USE_OPENING = True
    main.USE_SYZYGY = True
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
            print("uciok", flush=True)
        elif cmd == "isready":
            print("readyok", flush=True)
        elif cmd == "ucinewgame":
            main.transposition_table.clear()
            main.tt_depth.clear()
            main.tt_bestmove.clear()
            main.tt_flags.clear()
            board = chess.Board()
        elif cmd == "position":
            board = parse_position(board, parts[1:])
        elif cmd == "go":
            parse_go(board, parts[1:])
        elif cmd == "quit":
            break

if __name__ == "__main__":
    uci_loop()