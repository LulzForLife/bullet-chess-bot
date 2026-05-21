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

MIDDLEGAME_BONUS = {
    chess.PAWN: [
        0,  0,  0,  0,  0,  0,  0,  0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5,  5, 10, 25, 25, 10,  5,  5,
        0,  0,  0, 20, 20,  0,  0,  0,
        5, -5,-10,  0,  0,-10, -5,  5,
        5, 10, 10,-20,-20, 10, 10,  5,
        0,  0,  0,  0,  0,  0,  0,  0
    ],
    chess.KNIGHT: [
        -50,-40,-30,-30,-30,-30,-40,-50,
        -40,-20,  0,  0,  0,  0,-20,-40,
        -30,  0, 10, 15, 15, 10,  0,-30,
        -30,  5, 15, 20, 20, 15,  5,-30,
        -30,  0, 15, 20, 20, 15,  0,-30,
        -30,  5, 10, 15, 15, 10,  5,-30,
        -40,-20,  0,  5,  5,  0,-20,-40,
        -50,-40,-30,-30,-30,-30,-40,-50
    ],
    chess.BISHOP: [
        -20,-10,-10,-10,-10,-10,-10,-20,
        -10,  5,  0,  0,  0,  0,  5,-10,
        -10, 10, 10, 10, 10, 10, 10,-10,
        -10,  0, 10, 10, 10, 10,  0,-10,
        -10,  5,  5, 10, 10,  5,  5,-10,
        -10,  0,  5, 10, 10,  5,  0,-10,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -20,-10,-10,-10,-10,-10,-10,-20
    ],
    chess.ROOK: [
        0,  0,  0,  5,  5,  0,  0,  0,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        5, 10, 10, 10, 10, 10, 10,  5,
        0,  0,  0,  0,  0,  0,  0,  0
    ],
    chess.QUEEN: [
        -20,-10,-10, -5, -5,-10,-10,-20,
        -10,  0,  5,  0,  0,  0,  0,-10,
        -10,  5,  5,  5,  5,  5,  0,-10,
        -5,  0,  5,  5,  5,  5,  0, -5,
        0,  0,  5,  5,  5,  5,  0, -5,
        -10,  0,  5,  5,  5,  5,  0,-10,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -20,-10,-10, -5, -5,-10,-10,-20
    ],
    chess.KING: [
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -20,-30,-30,-40,-40,-30,-30,-20,
        -10,-20,-20,-20,-20,-20,-20,-10,
        20, 20,  0,  0,  0,  0, 20, 20,
        20, 30, 10,  0,  0, 10, 30, 20
    ]
}
ENDGAME_BONUS = {
    chess.PAWN: [
        0,  0,  0,  0,  0,  0,  0,  0,
        80, 80, 80, 80, 80, 80, 80, 80,
        40, 40, 50, 60, 60, 50, 40, 40,
        20, 20, 30, 40, 40, 30, 20, 20,
        10, 10, 20, 30, 30, 20, 10, 10,
        5,  5, 10, 20, 20, 10,  5,  5,
        0,  0,  0,  0,  0,  0,  0,  0,
        0,  0,  0,  0,  0,  0,  0,  0
    ],
    chess.KNIGHT: [
        -40,-30,-20,-20,-20,-20,-30,-40,
        -30,-10,  0,  5,  5,  0,-10,-30,
        -20,  5, 10, 15, 15, 10,  5,-20,
        -20, 10, 15, 20, 20, 15, 10,-20,
        -20, 10, 15, 20, 20, 15, 10,-20,
        -20,  5, 10, 15, 15, 10,  5,-20,
        -30,-10,  0,  5,  5,  0,-10,-30,
        -40,-30,-20,-20,-20,-20,-30,-40
    ],
    chess.BISHOP: [
        -20,-10,-10,-10,-10,-10,-10,-20,
        -10,  5,  0,  0,  0,  0,  5,-10,
        -10, 10, 10, 10, 10, 10, 10,-10,
        -10,  0, 10, 10, 10, 10,  0,-10,
        -10,  5,  5, 10, 10,  5,  5,-10,
        -10,  0,  5, 10, 10,  5,  0,-10,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -20,-10,-10,-10,-10,-10,-10,-20
    ],
    chess.ROOK: [
        0,  0,  5, 10, 10,  5,  0,  0,
        0,  5, 10, 15, 15, 10,  5,  0,
        0,  5, 10, 15, 15, 10,  5,  0,
        0,  5, 10, 15, 15, 10,  5,  0,
        0,  5, 10, 15, 15, 10,  5,  0,
        0,  5, 10, 15, 15, 10,  5,  0,
        0,  0,  5, 10, 10,  5,  0,  0,
        0,  0,  0,  0,  0,  0,  0,  0
    ],
    chess.QUEEN: [
        -20,-10,-10, -5, -5,-10,-10,-20,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -10,  0,  5,  5,  5,  5,  0,-10,
        -5,  0,  5,  5,  5,  5,  0, -5,
        0,  0,  5,  5,  5,  5,  0, -5,
        -10,  0,  5,  5,  5,  5,  0,-10,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -20,-10,-10, -5, -5,-10,-10,-20
    ],
    chess.KING: [
        -50,-40,-30,-20,-20,-30,-40,-50,
        -30,-20,-10,  0,  0,-10,-20,-30,
        -30,-10, 20, 30, 30, 20,-10,-30,
        -30,-10, 30, 40, 40, 30,-10,-30,
        -30,-10, 30, 40, 40, 30,-10,-30,
        -30,-10, 20, 30, 30, 20,-10,-30,
        -30,-30,  0,  0,  0,  0,-30,-30,
        -50,-30,-30,-30,-30,-30,-30,-50
    ]
}

MIRROR_BOARD = [
    56, 57, 58, 59, 60, 61, 62, 63,
    48, 49, 50, 51, 52, 53, 54, 55,
    40, 41, 42, 43, 44, 45, 46, 47,
    32, 33, 34, 35, 36, 37, 38, 39,
    24, 25, 26, 27, 28, 29, 30, 31,
    16, 17, 18, 19, 20, 21, 22, 23,
    8,  9,  10, 11, 12, 13, 14, 15,
    0,  1,  2,  3,  4,  5,  6,  7,
]

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
        psqb = MIDDLEGAME_BONUS[piece.piece_type][MIRROR_BOARD[square.index()]] # type: ignore
        evaluation += PIECE_VALUES[piece.piece_type] + psqb # type: ignore

    for square in black_bitboard:
        piece = b[square]
        psqb = MIDDLEGAME_BONUS[piece.piece_type][MIRROR_BOARD[square.index()]] # type: ignore
        evaluation -= PIECE_VALUES[piece.piece_type] + psqb # type: ignore

    return evaluation

def search_moves(b: chess.Board, depth: int) -> float:
    if b in chess.CHECKMATE:
        if b.turn == chess.BLACK:
            return math.inf
        return -math.inf
    elif b in chess.DRAW:
        return 0.0
    
    if depth == 0:
        return evaluate(b)
    
    is_black = b.turn == chess.BLACK
    
    best_eval = math.inf if is_black else -math.inf

    for move in b.legal_moves():
        b.apply(move)
        evaluation = search_moves(b, depth - 1)
        b.undo()

        if is_black:
            if evaluation <= best_eval:
                best_eval = evaluation
        else:
            if evaluation >= best_eval:
                best_eval = evaluation
    
    return best_eval

def get_best_move(b: chess.Board, depth: int) -> chess.Move | None:

    is_black = b.turn == chess.BLACK
    
    best_move = None
    best_eval = math.inf if is_black else -math.inf

    for move in b.legal_moves():
        b.apply(move)
        evaluation = search_moves(b, depth - 1)
        b.undo()
        if is_black:
            if evaluation <= best_eval:
                best_eval = evaluation
                best_move = move
        else:
            if evaluation >= best_eval:
                best_eval = evaluation
                best_move = move

    return best_move

def main() -> None:
    board = chess.Board()

    while len(board.legal_moves()) > 0:

        best_move = get_best_move(board, DEPTH)
        if best_move == None:
            break
        print(best_move)
        board.apply(best_move)

        print(board.pretty())

if __name__ == "__main__":
    if not USE_UCI:
        main()
    else:
        uci_loop()