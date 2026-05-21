import bulletchess as chess
import math
import sys
import random
import time

PIECE_VALUES = {
    chess.KING: 60000.0,
    chess.QUEEN: 900.0,
    chess.ROOK: 490.0,
    chess.BISHOP: 320.0,
    chess.KNIGHT: 290.0,
    chess.PAWN: 100.0
}

PHASE_VALUES = {
    chess.KING: 0,
    chess.QUEEN: 4,
    chess.ROOK: 2,
    chess.BISHOP: 1,
    chess.KNIGHT: 1,
    chess.PAWN: 0
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

TIME_LIMIT = 10
USE_UCI = "--uci" in sys.argv

transposition_table: dict[int, float] = {}
tt_depth: dict[int, int] = {}

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
            move = get_best_move(board, TIME_LIMIT)
            if move is None:
                move = random.choice(board.legal_moves())
            
            print(f"bestmove {move.uci()}", flush=True)

        elif parts[0] == "ucinewgame":
            board = chess.Board()

        elif parts[0] == "quit":
            break

def evaluate(b: chess.Board) -> float:
    if b in chess.CHECKMATE:
        return -100000.0
    elif b in chess.DRAW:
        return 0.0

    evaluation = 0.0

    white_bitboard = b[chess.WHITE]
    black_bitboard = b[chess.BLACK]

    phase = 0
    for square in white_bitboard | black_bitboard:
        phase += PHASE_VALUES[b[square].piece_type] # type: ignore

    middlegame_percentage = (phase / 24)
    endgame_percentage = ((24 - phase) / 24)

    for square in white_bitboard:
        piece= b[square]
        index = MIRROR_BOARD[square.index()]
        psqb = MIDDLEGAME_BONUS[piece.piece_type][index] * middlegame_percentage # type: ignore
        psqb += ENDGAME_BONUS[piece.piece_type][MIRROR_BOARD[square.index()]] * endgame_percentage # type: ignore
        evaluation += PIECE_VALUES[piece.piece_type] + psqb # type: ignore

    for square in black_bitboard:
        piece = b[square]
        index = square.index()
        psqb = MIDDLEGAME_BONUS[piece.piece_type][index] * middlegame_percentage # type: ignore
        psqb += ENDGAME_BONUS[piece.piece_type][MIRROR_BOARD[square.index()]] * endgame_percentage # type: ignore
        evaluation -= PIECE_VALUES[piece.piece_type] + psqb # type: ignore

    return evaluation if b.turn == chess.WHITE else -evaluation

def search_moves(b: chess.Board, depth: int, alpha: float, beta: float, end: float) -> float:
    global transposition_table, tt_depth, hits
    if time.perf_counter() >= end:
        raise TimeoutError
    if b in chess.CHECKMATE:
        return -100000.0 - depth
    elif b in chess.DRAW:
        return 0.0
    
    if depth == 0:
        return evaluate(b)
    
    b_hash = hash(b)

    if b_hash in transposition_table:
        if tt_depth[b_hash] >= depth:
            return transposition_table[b_hash]

    for move in b.legal_moves():
        b.apply(move)
        evaluation = -search_moves(b, depth - 1, -beta, -alpha, end)
        b.undo()

        if evaluation >= beta:
            return beta
        if evaluation > alpha:
            alpha = evaluation
    
    transposition_table[b_hash] = alpha
    tt_depth[b_hash] = depth

    return alpha

def get_best_move(b: chess.Board, time_limit: int) -> chess.Move | None:

    end = time.perf_counter() + time_limit
    
    best_move = None

    try:
        for depth in range(1, 100):
            cur_best_move = None
            b_check = b.copy()

            if not USE_UCI:
                print(f"Depth: {depth}", end = "\r")

            best_eval = -math.inf

            for move in b.legal_moves():
                b_check.apply(move)
                evaluation = -search_moves(b_check, depth - 1, -math.inf, math.inf, end)
                b_check.undo()

                if evaluation > best_eval:
                    best_eval = evaluation
                    cur_best_move = move
                
            best_move = cur_best_move
    except KeyboardInterrupt:
        raise
    except TimeoutError:
        pass

    return best_move

def main() -> None:
    global hits
    board = chess.Board()

    print(board.pretty())

    hits = 0
    while board not in chess.CHECKMATE and board not in chess.DRAW:
        best_move = get_best_move(board, TIME_LIMIT)
        print()
        print(f"Hits: {hits} / Nodes: {len(transposition_table.keys())}")
        if best_move == None:
            break
        board.apply(best_move)

        print(board.pretty())

if __name__ == "__main__":
    if not USE_UCI:
        main()
    else:
        uci_loop()