import sys
import bulletchess as chess
import main
import os
import time
import threading

TIME_LIMIT = main.TIME_LIMIT

class DualOutputStream:
    """A stream for handling stdout/stderr (writing out)."""
    def __init__(self, log_file, original_stream, prefix=""):
        self.log_file = log_file
        self.original_stream = original_stream
        self.prefix = prefix

    def write(self, data):
        # Write to the terminal completely untouched for the chess GUI
        self.original_stream.write(data)
        
        # Write to log file, applying the prefix to every individual line
        if data:
            # Split lines but keep the line endings so we don't break spacing
            lines = data.splitlines(keepends=True)
            for line in lines:
                if line.strip():
                    self.log_file.write(f"{self.prefix}{line}")
                else:
                    self.log_file.write(line)
        self.flush()

    def flush(self):
        self.log_file.flush()
        self.original_stream.flush()

    def reconfigure(self, *args, **kwargs):
        return self.original_stream.reconfigure(*args, **kwargs)

class DualInputStream:
    """A stream for handling stdin (reading in)."""
    def __init__(self, log_file, original_stream, prefix=""):
        self.log_file = log_file
        self.original_stream = original_stream
        self.prefix = prefix

    def readline(self, *args, **kwargs):
        data = self.original_stream.readline(*args, **kwargs)
        if data:
            # 'data' already ends with a \n, so we don't add another one!
            self.log_file.write(f"{self.prefix}{data}")
            self.log_file.flush()
        return data

    def read(self, *args, **kwargs):
        data = self.original_stream.read(*args, **kwargs)
        if data:
            self.log_file.write(data)
            self.log_file.flush()
        return data

f = open("output.log", "w", encoding="utf-8")
f.write("")

sys.stdout = DualOutputStream(f, sys.__stdout__, prefix="[OUT] ")
sys.stderr = DualOutputStream(f, sys.__stderr__, prefix="[ERR] ")
sys.stdin = DualInputStream(f, sys.__stdin__, prefix="[IN ] ")

def parse_position(board: main.EvalBoard, tokens: list[str]) -> main.EvalBoard:
    """Parses standard UCI position strings into the engine's board state."""
    if not tokens:
        return board
    
    # Isolate base position setup
    if tokens[0] == "startpos":
        board = main.EvalBoard()
        remaining_tokens = tokens[1:]
    elif tokens[0] == "fen":
        if "moves" in tokens:
            moves_idx = tokens.index("moves")
            fen_str = " ".join(tokens[1:moves_idx])
            remaining_tokens = tokens[moves_idx:]
        else:
            fen_str = " ".join(tokens[1:])
            remaining_tokens = []
        board = main.EvalBoard.from_fen(fen_str)
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
        time_limit = 86400
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
            time_limit = 86400
    else:
        max_depth = 100
        if time_limit is None:
            time_limit = 3.0
    
    return time_limit, max_depth

def parse_go(board: main.EvalBoard, tokens: list[str], is_ponder: bool = False) -> None:
    def run_and_print(board: main.EvalBoard, time_limit: float, max_depth: int) -> None:
        if board.in_draw or board.in_checkmate:
            raise ValueError
        best_move, _ = main.get_best_move(board, time_limit, max_depth)
        if best_move is None:
            best_move, _ = main.get_best_move(board, 86400, 1)
        if best_move is None:
            raise ValueError
        try:
            ponder_move = main.get_pv(board, best_move)[1]
            board.apply(best_move)
            board.apply(chess.Move.from_uci(ponder_move))
            if board.in_checkmate or board.in_draw:
                raise IndexError
            board.undo()
            board.undo()
            print(f"bestmove {best_move.uci()} ponder {ponder_move}", flush=True)
        except IndexError:
            print(f"bestmove {best_move.uci()}")
    global TIME_LIMIT
    """Calculates active time management allocation budgets and fires search."""
    
    time_limit, max_depth = get_time(tokens, board)
    TIME_LIMIT = time_limit

    main.PONDER = is_ponder

    b = board.copy()
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
    main.USE_GAVIOTA = os.path.exists("gaviota_5")
    board = main.EvalBoard()
    
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
            print("option name Opening_Book type check default true")
            print("option name Endgame_Table type check default true")
            print("uciok", flush=True)
        elif cmd == "isready":
            print("readyok", flush=True)
        elif cmd == "ucinewgame":
            main.tt.clear()
            main.clear_killer()
            main.clear_history()
            board = main.EvalBoard()
        elif cmd == "position":
            board = parse_position(board, parts[1:])
        elif cmd == "setoption":
            if len(parts) >= 5:
                if parts[1] == "name" and parts[2] == "Opening_Book":
                    main.USE_OPENING = parts[4].lower() == "true"
                if parts[1] == "name" and parts[2] == "Endgame_Table":
                    main.USE_GAVIOTA = parts[4].lower() == "true" and os.path.exists("gaviota_5")
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