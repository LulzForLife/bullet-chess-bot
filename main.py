import bulletchess as bchess
import chess
import chess.syzygy as syzygy

import math
import sys
import time
from enum import IntEnum, auto

class Flag(IntEnum):
    EXACT = auto()
    UPPER = auto()
    LOWER = auto()

PIECE_VALUES = {
    bchess.KING: 60000.0,
    bchess.QUEEN: 900.0,
    bchess.ROOK: 490.0,
    bchess.BISHOP: 320.0,
    bchess.KNIGHT: 290.0,
    bchess.PAWN: 100.0
}

PHASE_VALUES = {
    bchess.KING: 0,
    bchess.QUEEN: 4,
    bchess.ROOK: 2,
    bchess.BISHOP: 1,
    bchess.KNIGHT: 1,
    bchess.PAWN: 0
}

MOBILITY_BONUS_MG = {
    bchess.KING: 0,
    bchess.QUEEN: 1,
    bchess.ROOK: 2,
    bchess.BISHOP: 4,
    bchess.KNIGHT: 6,
    bchess.PAWN: 0
}

MOBILITY_BONUS_EG = {
    bchess.KING: 3,
    bchess.QUEEN: 3,
    bchess.ROOK: 4,
    bchess.BISHOP: 3,
    bchess.KNIGHT: 5,
    bchess.PAWN: 0
}

MIDDLEGAME_BONUS = {
    bchess.PAWN: [
        0,  0,  0,  0,  0,  0,  0,  0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5,  5, 10, 25, 25, 10,  5,  5,
        0,  0,  0, 20, 20,  0,  0,  0,
        5, -5,-10,  0,  0,-10, -5,  5,
        5, 10, 10,-20,-20, 10, 10,  5,
        0,  0,  0,  0,  0,  0,  0,  0
    ],
    bchess.KNIGHT: [
        -50,-40,-30,-30,-30,-30,-40,-50,
        -40,-20,  0,  0,  0,  0,-20,-40,
        -30,  0, 10, 15, 15, 10,  0,-30,
        -30,  5, 15, 20, 20, 15,  5,-30,
        -30,  0, 15, 20, 20, 15,  0,-30,
        -30,  5, 10, 15, 15, 10,  5,-30,
        -40,-20,  0,  5,  5,  0,-20,-40,
        -50,-40,-30,-30,-30,-30,-40,-50
    ],
    bchess.BISHOP: [
        -20,-10,-10,-10,-10,-10,-10,-20,
        -10,  5,  0,  0,  0,  0,  5,-10,
        -10, 10, 10, 10, 10, 10, 10,-10,
        -10,  0, 10, 10, 10, 10,  0,-10,
        -10,  5,  5, 10, 10,  5,  5,-10,
        -10,  0,  5, 10, 10,  5,  0,-10,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -20,-10,-10,-10,-10,-10,-10,-20
    ],
    bchess.ROOK: [
        0,  0,  0,  5,  5,  0,  0,  0,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        5, 10, 10, 10, 10, 10, 10,  5,
        0,  0,  0,  0,  0,  0,  0,  0
    ],
    bchess.QUEEN: [
        -20,-10,-10, -5, -5,-10,-10,-20,
        -10,  0,  5,  0,  0,  0,  0,-10,
        -10,  5,  5,  5,  5,  5,  0,-10,
        -5,  0,  5,  5,  5,  5,  0, -5,
        0,  0,  5,  5,  5,  5,  0, -5,
        -10,  0,  5,  5,  5,  5,  0,-10,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -20,-10,-10, -5, -5,-10,-10,-20
    ],
    bchess.KING: [
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
    bchess.PAWN: [
        0,  0,  0,  0,  0,  0,  0,  0,
        80, 80, 80, 80, 80, 80, 80, 80,
        40, 40, 50, 60, 60, 50, 40, 40,
        20, 20, 30, 40, 40, 30, 20, 20,
        10, 10, 20, 30, 30, 20, 10, 10,
        5,  5, 10, 20, 20, 10,  5,  5,
        0,  0,  0,  0,  0,  0,  0,  0,
        0,  0,  0,  0,  0,  0,  0,  0
    ],
    bchess.KNIGHT: [
        -40,-30,-20,-20,-20,-20,-30,-40,
        -30,-10,  0,  5,  5,  0,-10,-30,
        -20,  5, 10, 15, 15, 10,  5,-20,
        -20, 10, 15, 20, 20, 15, 10,-20,
        -20, 10, 15, 20, 20, 15, 10,-20,
        -20,  5, 10, 15, 15, 10,  5,-20,
        -30,-10,  0,  5,  5,  0,-10,-30,
        -40,-30,-20,-20,-20,-20,-30,-40
    ],
    bchess.BISHOP: [
        -20,-10,-10,-10,-10,-10,-10,-20,
        -10,  5,  0,  0,  0,  0,  5,-10,
        -10, 10, 10, 10, 10, 10, 10,-10,
        -10,  0, 10, 10, 10, 10,  0,-10,
        -10,  5,  5, 10, 10,  5,  5,-10,
        -10,  0,  5, 10, 10,  5,  0,-10,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -20,-10,-10,-10,-10,-10,-10,-20
    ],
    bchess.ROOK: [
        0,  0,  5, 10, 10,  5,  0,  0,
        0,  5, 10, 15, 15, 10,  5,  0,
        0,  5, 10, 15, 15, 10,  5,  0,
        0,  5, 10, 15, 15, 10,  5,  0,
        0,  5, 10, 15, 15, 10,  5,  0,
        0,  5, 10, 15, 15, 10,  5,  0,
        0,  0,  5, 10, 10,  5,  0,  0,
        0,  0,  0,  0,  0,  0,  0,  0
    ],
    bchess.QUEEN: [
        -20,-10,-10, -5, -5,-10,-10,-20,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -10,  0,  5,  5,  5,  5,  0,-10,
        -5,  0,  5,  5,  5,  5,  0, -5,
        0,  0,  5,  5,  5,  5,  0, -5,
        -10,  0,  5,  5,  5,  5,  0,-10,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -20,-10,-10, -5, -5,-10,-10,-20
    ],
    bchess.KING: [
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

# list of thing todo
# make board keep track of material instead of recalcuating it every time
# maybe instead calculate material at depth = 1 and use it for all of the depth = 0
# delta pruning
# add promotions/checks to quiescence search (maybe?)

TIME_LIMIT = 10
USE_UCI = "--uci" in sys.argv
CASTLE_BONUS = 30
CHECK_BONUS = 10
DELTA = PIECE_VALUES[bchess.QUEEN]
MAX_PLY = 64
KILLER_PRIMARY = 750.0
KILLER_SECONDARY = 650.0
SELF_PLAY = True

nodes_searched = 0

transposition_table: dict[int, float] = {}
tt_depth: dict[int, int] = {}
tt_bestmove: dict[int, bchess.Move | None] = {}
tt_flags: dict[int, Flag] = {}

killer_moves: list[list[None | bchess.Move]] = [[None, None] for _ in range(MAX_PLY)]

tablebase = syzygy.open_tablebase("syzygy")

def get_input(b: bchess.Board) -> bchess.Move:
    move = None
    legal_moves = b.legal_moves()
    while move not in legal_moves:
        try:
            move = bchess.Move.from_uci(input("Enter move (e2e4, etc): "))
        except ValueError:
            continue
    return move # type: ignore

def get_best_tablebase_move(board: bchess.Board):
    piece_count = sum(1 for square in bchess.SQUARES if board[square] is not None)

    if piece_count <= 5:
        best_move = None
        best_score = -2

        for move in board.legal_moves():
            board.apply(move)
            next_fen = board.fen()
            next_board = chess.Board(next_fen)

            try:
                score = -tablebase.probe_wdl(next_board)
                if score > best_score:
                    best_score = score
                    best_move = move
            except syzygy.MissingTableError:
                pass

            board.undo()

        if best_move:
            return best_move

    return None

def get_phase_value(b: bchess.Board, color: bchess.Color) -> int:
    global PHASE_VALUES
    return sum(
        len(b[(color, piece_type)]) * PHASE_VALUES[piece_type]
        for piece_type in bchess.PIECE_TYPES
    )

def evaluate(b: bchess.Board) -> float:
    global PIECE_VALUES, PHASE_VALUES, MIRROR_BOARD, ENDGAME_BONUS, MIDDLEGAME_BONUS, MOBILITY_BONUS_EG, MOBILITY_BONUS_MG
    if b in bchess.CHECKMATE:
        return -100000.0
    elif b in bchess.DRAW:
        return 0.0

    evaluation = 0.0

    white_bitboard = b[bchess.WHITE]
    black_bitboard = b[bchess.BLACK]

    phase = get_phase_value(b, bchess.WHITE) + get_phase_value(b, bchess.BLACK)

    middlegame_percentage = (phase / 24)
    endgame_percentage = ((24 - phase) / 24)

    for square in white_bitboard:
        piece= b[square]
        if piece is None:
            raise ValueError
        piece_type = piece.piece_type
        index = MIRROR_BOARD[square.index()]
        psqb = MIDDLEGAME_BONUS[piece_type][index] * middlegame_percentage
        psqb += ENDGAME_BONUS[piece_type][MIRROR_BOARD[square.index()]] * endgame_percentage
        evaluation += PIECE_VALUES[piece_type] + psqb

    for square in black_bitboard:
        piece = b[square]
        if piece is None:
            raise ValueError
        piece_type = piece.piece_type
        index = square.index()
        psqb = MIDDLEGAME_BONUS[piece_type][index] * middlegame_percentage
        psqb += ENDGAME_BONUS[piece_type][square.index()] * endgame_percentage
        evaluation -= PIECE_VALUES[piece_type] + psqb
    
    if b in bchess.CHECK:
        evaluation -= CHECK_BONUS

    return evaluation if b.turn == bchess.WHITE else -evaluation

def order_moves(b: bchess.Board, ply: int) -> map[bchess.Move]:
    global PIECE_VALUES, CASTLE_BONUS
    new_moves: list[tuple[bchess.Move, float]] = []
    for move in b.legal_moves():
        if move.is_capture(b):
            value = PIECE_VALUES[b[move.destination].piece_type] - PIECE_VALUES[b[move.origin].piece_type] # type: ignore
        else:
            if move == killer_moves[ply][0]:
                value = KILLER_PRIMARY
            else:
                value = KILLER_SECONDARY
        if move.is_promotion():
            value += PIECE_VALUES[move.promotion] # type: ignore
        if move.is_castling(b):
            value += CASTLE_BONUS
        new_moves.append((move, value))
    new_moves.sort(key = lambda t: t[1], reverse = True)
    return map(lambda t: t[0], new_moves)

def store_killer(move: bchess.Move, ply: int) -> None:
    global killer_moves
    if killer_moves[ply][0] != move:
        killer_moves[ply][1] = killer_moves[ply][0]
        killer_moves[ply][0] = move

def quiesce(b: bchess.Board, alpha: float, beta: float, end: float, ply: int) -> float:
    global transposition_table, tt_depth, tt_bestmove, tt_flags, nodes_searched, DELTA

    if time.perf_counter() >= end:
        raise TimeoutError
    
    nodes_searched += 1

    if b in bchess.CHECKMATE:
        return -100000.0 + ply
    elif b in bchess.DRAW:
        return 0.0
    
    stand_pat = evaluate(b)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    if stand_pat + DELTA < alpha and not b in bchess.CHECK:
        if b.turn is bchess.WHITE:
            if not (b[(bchess.WHITE, bchess.PAWN)] & bchess.RANK_7):
                return alpha
        else:
            if not (b[(bchess.BLACK, bchess.PAWN)] & bchess.RANK_2):
                return alpha
    
    b_hash = hash(b)
    original_alpha = alpha
    first_move = None
    best_move = None

    if b_hash in transposition_table:
        score = transposition_table[b_hash]

        if 90000.0 < score < math.inf:
            score -= ply
        elif -math.inf < score < -90000.0:
            score += ply
        
        flag = tt_flags[b_hash]
        if flag == Flag.EXACT:
            return score
        elif flag == Flag.LOWER and score >= beta:
            return beta
        elif flag == Flag.UPPER and score <= alpha:
            return alpha
            
        first_move = tt_bestmove[b_hash]
        
        if (first_move is not None and
            first_move in b.legal_moves() and
            (first_move.is_capture(b) or
             first_move.is_promotion and first_move.promotion is bchess.QUEEN)):
            b.apply(first_move)
            evaluation = -quiesce(b, -beta, -alpha, end, ply + 1)
            b.undo()

            if evaluation >= beta:
                tt_score = beta
                if 90000.0 < tt_score < math.inf:
                    tt_score += ply
                elif -math.inf < tt_score < -90000.0:
                    tt_score -= ply
                
                transposition_table[b_hash] = tt_score
                tt_depth[b_hash] = 0
                tt_bestmove[b_hash] = first_move
                tt_flags[b_hash] = Flag.LOWER
                
                return beta
            
            if evaluation > alpha:
                alpha = evaluation
                best_move = first_move
    
    for move in b.legal_moves():
        if not move.is_capture(b) or not (move.is_promotion() and move.promotion is bchess.QUEEN):
            continue
        b.apply(move)
        evaluation = -quiesce(b, -beta, -alpha, end, ply + 1)
        b.undo()

        if evaluation >= beta:
            tt_score = beta
            if 90000.0 < tt_score < math.inf:
                tt_score += ply
            elif -math.inf < tt_score < -90000.0:
                tt_score -= ply
                
            transposition_table[b_hash] = tt_score
            tt_depth[b_hash] = 0
            tt_bestmove[b_hash] = move
            tt_flags[b_hash] = Flag.LOWER

            return beta
            
        if evaluation > alpha:
            alpha = evaluation
            best_move = move
    
    tt_score = alpha
    if 90000.0 < tt_score < math.inf:
        tt_score += ply
    elif -math.inf < tt_score < -90000.0:
        tt_score -= ply

    transposition_table[b_hash] = tt_score
    tt_depth[b_hash] = 0
    tt_bestmove[b_hash] = best_move
    
    if alpha > original_alpha:
        tt_flags[b_hash] = Flag.EXACT
    else:
        tt_flags[b_hash] = Flag.UPPER

    return alpha

def search_moves(b: bchess.Board, depth: int, alpha: float, beta: float, end: float, ply: int = 0) -> float:
    global transposition_table, tt_depth, tt_bestmove, tt_flags, nodes_searched, killer_moves
    
    if time.perf_counter() >= end:
        raise TimeoutError

    nodes_searched += 1

    if b in bchess.CHECKMATE:
        return -100000.0 + ply
    elif b in bchess.DRAW:
        return 0.0
    
    if depth == 0:
        return quiesce(b, alpha, beta, end, ply)
    
    b_hash = hash(b)
    original_alpha = alpha
    first_move = None
    best_move = None

    if b_hash in transposition_table and tt_depth[b_hash] >= depth:
        score = transposition_table[b_hash]

        if 90000.0 < score < math.inf:
            score -= ply
        elif -math.inf < score < -90000.0:
            score += ply
        
        flag = tt_flags[b_hash]
        if flag == Flag.EXACT:
            return score
        elif flag == Flag.LOWER and score >= beta:
            return beta
        elif flag == Flag.UPPER and score <= alpha:
            return alpha
            
        first_move = tt_bestmove[b_hash]
        
        if first_move is not None and first_move in b.legal_moves():
            b.apply(first_move)
            evaluation = -search_moves(b, depth - 1, -beta, -alpha, end, ply + 1)
            b.undo()

            if evaluation >= beta:
                tt_score = beta
                if 90000.0 < tt_score < math.inf:
                    tt_score += ply
                elif -math.inf < tt_score < -90000.0:
                    tt_score -= ply
                    
                transposition_table[b_hash] = tt_score
                tt_depth[b_hash] = depth
                tt_bestmove[b_hash] = first_move
                tt_flags[b_hash] = Flag.LOWER

                if not first_move.is_capture(b):
                    store_killer(first_move, ply)

                return beta
            
            if evaluation > alpha:
                alpha = evaluation
                best_move = first_move

    if not b in bchess.CHECK:
        player_phase = get_phase_value(b, b.turn)

        if player_phase >= 12:
            r = 3
        elif player_phase > 0:
            r = 2
        else:
            r = 0

        if r != 0 and depth > r:

            b.apply(None)

            null_score = -search_moves(b, depth - 1 - r, -beta, -beta + 1, end, ply + 1)

            b.undo()

            if null_score >= beta:
                return beta

    for move in order_moves(b, ply):
        if move == first_move:
            continue
        b.apply(move)
        evaluation = -search_moves(b, depth - 1, -beta, -alpha, end, ply + 1)
        b.undo()

        if evaluation >= beta:
            tt_score = beta
            if 90000.0 < tt_score < math.inf:
                tt_score += ply
            elif -math.inf < tt_score < -90000.0:
                tt_score -= ply
                
            transposition_table[b_hash] = tt_score
            tt_depth[b_hash] = depth
            tt_bestmove[b_hash] = move
            tt_flags[b_hash] = Flag.LOWER

            if not move.is_capture(b):
                store_killer(move, ply)

            return beta
            
        if evaluation > alpha:
            alpha = evaluation
            best_move = move
    
    tt_score = alpha
    if 90000.0 < tt_score < math.inf:
        tt_score += ply
    elif -math.inf < tt_score < -90000.0:
        tt_score -= ply

    transposition_table[b_hash] = tt_score
    tt_depth[b_hash] = depth
    tt_bestmove[b_hash] = best_move
    
    if alpha > original_alpha:
        tt_flags[b_hash] = Flag.EXACT
    else:
        tt_flags[b_hash] = Flag.UPPER

    return alpha

def get_best_move(b: bchess.Board, time_limit: float, max_depth: int = MAX_PLY) -> tuple[bchess.Move | None, float | str]:
    global nodes_searched, USE_UCI
    
    nodes_searched = 0
    start_time = time.perf_counter()
    end = start_time + time_limit
    
    best_move = None
    best_eval = -math.inf

    try:
        for depth in range(1, max_depth + 1):
            cur_best_move = None
            b_check = b.copy()

            cur_best_eval = -150000.0
            alpha = -150000.0
            beta = 150000.0

            legal_moves = list(b.legal_moves())
            if not legal_moves:
                break
                
            if best_move is not None and best_move in legal_moves:
                legal_moves.remove(best_move)
                legal_moves.insert(0, best_move)

            for move in legal_moves:
                b_check.apply(move)
                evaluation = -search_moves(b_check, depth - 1, -beta, -alpha, end)
                b_check.undo()

                if evaluation > cur_best_eval:
                    cur_best_eval = evaluation
                    cur_best_move = move
                
                if cur_best_eval > alpha:
                    alpha = cur_best_eval
                
            best_move = cur_best_move
            best_eval = cur_best_eval

            elapsed = time.perf_counter() - start_time
            elapsed_ms = max(1, int(elapsed * 1000))
            nps = int(nodes_searched / elapsed) if elapsed > 0 else 0
            
            if abs(best_eval) > 90000.0:
                plies_to_mate = 100000.0 - abs(best_eval)
                moves_to_mate = math.ceil(plies_to_mate / 2)
                score_str = f"mate {int(moves_to_mate) if best_eval > 0 else -int(moves_to_mate)}"
            else:
                score_str = f"cp {int(best_eval)}"

            pv_str = best_move.uci() if best_move else ""
            
            if USE_UCI:
                print(f"info depth {depth} score {score_str} nodes {nodes_searched} nps {nps} time {elapsed_ms} pv {pv_str}", flush=True)
            else:
                print(f"Depth: {depth}", end = "\r")

            if abs(best_eval) > 90000.0:
                break

    except KeyboardInterrupt:
        raise
    except TimeoutError:
        pass

    if abs(best_eval) > 90000.0:
        plies_to_mate = 100000.0 - abs(best_eval)
        moves_to_mate = math.ceil(plies_to_mate / 2)
        prefix = "-" if best_eval < 0 else ""
        return (best_move, f"{prefix}M{moves_to_mate}")

    return (best_move, best_eval)

def main() -> None:
    global nodes_searched
    board = bchess.Board()

    print(board.pretty())

    while board not in bchess.CHECKMATE and board not in bchess.DRAW:
        if not SELF_PLAY:
            best_move = get_input(board)
            board.apply(best_move)
            print(board.pretty())
        s = time.perf_counter()
        best_move, evaluation = get_best_move(board, TIME_LIMIT)
        time.sleep(max(0, min(TIME_LIMIT - (time.perf_counter() - s), 0.5)))
        print()
        if best_move == None:
            break
        board.apply(best_move)
        print(board.pretty())
        print(f"Evaluation: {evaluation}")
        print(f"Nodes searched: {nodes_searched}")

if __name__ == "__main__":
    if not USE_UCI:
        main()
    else:
        import uci
        uci.uci_loop()