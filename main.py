import bulletchess as chess
import math
import sys
import random

PIECE_VALUES = {
    chess.KING: 60000.0,
    chess.QUEEN: 900.0,
    chess.ROOK: 490.0,
    chess.BISHOP: 320.0,
    chess.KNIGHT: 290.0,
    chess.PAWN: 100.0
}

DEPTH = 4
USE_UCI = "--uci" in sys.argv

def uci_loop() -> None:
    sys.stdout.reconfigure(line_buffering=True) # pyright: ignore[reportAttributeAccessIssue]

    board = chess.Board()
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        parts = line.split()
        if not parts:
            continue

        if parts[0] == "uci":
            print("id name KikiBot")
            print("id author kiranmjlowe")
            print("uciok", flush=True)
            
        elif parts[0] == "isready":
            print("readyok", flush=True)
            
        elif parts[0] == "position":
            if "startpos" in parts:
                board = chess.Board()
            elif "fen" in parts:
                # Find where 'moves' starts to isolate the FEN
                fen_end = parts.index("moves") if "moves" in parts else len(parts)
                fen_string = " ".join(parts[parts.index("fen")+1 : fen_end])
                board = chess.Board.from_fen(fen_string)
            
            if "moves" in parts:
                for move in parts[parts.index("moves") + 1:]:
                    board.apply(chess.Move.from_uci(move))

        elif parts[0] == "go":
            move = get_best_move(board, DEPTH)
            if move is None:
                move = random.choice(board.legal_moves())
            
            print(f"bestmove {move.uci()}", flush=True)

        elif parts[0] == "ucinewgame":
            board = chess.Board()

        elif parts[0] == "quit":
            break

def evaluate(b: chess.Board) -> float:
    if b in chess.CHECKMATE:
        if b.turn == chess.BLACK:
            return math.inf
        return -math.inf
    elif b in chess.DRAW:
        return 0.0

    evaluation = 0.0

    white_bitboard = b[chess.WHITE]
    black_bitboard = b[chess.BLACK]

    for square in white_bitboard:
        piece= b[square]
        evaluation += PIECE_VALUES[piece.piece_type] # pyright: ignore[reportOptionalMemberAccess]

    for square in black_bitboard:
        piece = b[square]
        evaluation -= PIECE_VALUES[piece.piece_type] # pyright: ignore[reportOptionalMemberAccess]

    return evaluation

def search_moves(b: chess.Board, depth: int) -> float:
    if depth == 0:
        return evaluate(b)
    
    is_black = b.turn == chess.BLACK
    
    best_eval = -math.inf
    for move in b.legal_moves():
        b.apply(move)
        evaluation = search_moves(b, depth - 1)
        b.undo()

        if not is_black:
            evaluation = -evaluation

        if evaluation > best_eval:
            best_eval = evaluation
    
    return best_eval

def get_best_move(b: chess.Board, depth: int) -> chess.Move | None:

    is_black = b.turn == chess.BLACK
    
    best_move = None
    best_eval = -math.inf

    for move in b.legal_moves():
        b.apply(move)
        evaluation = -search_moves(b, depth - 1)
        b.undo()
        if is_black:
            evaluation = -evaluation
        if evaluation > best_eval:
            best_eval = evaluation
            best_move = move

    return best_move

def main() -> None:
    board = chess.Board()

    while len(board.legal_moves()) > 0:

        best_move = get_best_move(board, DEPTH)
        print(best_move)
        board.apply(best_move)

        print(board.pretty())

if __name__ == "__main__":
    if not USE_UCI:
        main()
    else:
        uci_loop()