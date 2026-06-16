import bulletchess as chess
import chess as chs
import chess.polyglot as polyglot
import chess.gaviota as gaviota

import math
import sys
import os
import time
from enum import IntEnum, auto

class Flag(IntEnum):
    EXACT = auto()
    UPPER = auto()
    LOWER = auto()

class EvalBoard():
    __slots__ = ("board", "mg_evaluation", "eg_evaluation", "white_phase", "black_phase", "state_stack")

    def __init__(self) -> None:
        self.board = chess.Board()
        self.mg_evaluation = mg_eval(self.board)
        self.eg_evaluation = eg_eval(self.board)
        self.white_phase = get_phase_value(self.board, chess.WHITE)
        self.black_phase = get_phase_value(self.board, chess.BLACK)
        
        self.state_stack = []
    
    def __getitem__(self, key):
        return self.board.__getitem__(key)
    
    def __hash__(self) -> int:
        return self.board.__hash__()
    
    def status(self, status: chess.BoardStatus) -> bool:
        return self.board in status
    
    def is_capture(self, move: chess.Move) -> bool:
        return move.is_capture(self.board)
    
    def is_castling(self, move: chess.Move) -> bool:
        return move.is_castling(self.board)
    
    def legal_moves(self) -> list[chess.Move]:
        return self.board.legal_moves()
    
    def fen(self) -> str:
        return self.board.fen()
    
    def apply(self, move: chess.Move | None) -> None:
        self.state_stack.append((self.mg_evaluation, self.eg_evaluation, self.white_phase, self.black_phase))

        if move is None:
            self.board.apply(move)
            self.mg_evaluation = -self.mg_evaluation
            self.eg_evaluation = -self.eg_evaluation
            return
        
        is_capture = move.is_capture(self.board)
        is_castling = move.is_castling(self.board)
        is_en_passant = self.board.en_passant_square == move.destination and self.board[move.origin].piece_type is chess.PAWN # type: ignore
        is_promotion = move.is_promotion()

        turn = self.board.turn
        origin_piece = self.board[move.origin]
        piece_type = origin_piece.piece_type if origin_piece else chess.PAWN

        dSmg = dSeg = 0.0
        
        if turn == chess.WHITE:
            origin_idx = MIRROR_BOARD[move.origin.index()]
            dest_idx = MIRROR_BOARD[move.destination.index()]
        else:
            origin_idx = move.origin.index()
            dest_idx = move.destination.index()

        psqt_old_mg = MIDDLEGAME_BONUS[piece_type][origin_idx]
        psqt_new_mg = MIDDLEGAME_BONUS[piece_type][dest_idx]
        dSmg += (psqt_new_mg - psqt_old_mg)

        psqt_old_eg = ENDGAME_BONUS[piece_type][origin_idx]
        psqt_new_eg = ENDGAME_BONUS[piece_type][dest_idx]
        dSeg += (psqt_new_eg - psqt_old_eg)

        if is_capture:
            piece_type = self.board[move.destination].piece_type # type: ignore
            if self.turn is chess.WHITE:
                index = move.destination.index()
                self.black_phase -= PHASE_VALUES[piece_type]
            else:
                index = MIRROR_BOARD[move.destination.index()]
                self.white_phase -= PHASE_VALUES[piece_type]
            mg_piece_value = eg_piece_value = PIECE_VALUES[piece_type]
            mg_piece_value += MIDDLEGAME_BONUS[piece_type][index]
            eg_piece_value += ENDGAME_BONUS[piece_type][index]

            dSmg += mg_piece_value
            dSeg += eg_piece_value

        if is_promotion:
            piece_type = move.promotion
            if self.turn is chess.WHITE:
                index = move.destination.index()
                self.white_phase += PHASE_VALUES[piece_type] - PHASE_VALUES[chess.PAWN] # type: ignore
            else:
                index = MIRROR_BOARD[move.destination.index()]
                self.black_phase += PHASE_VALUES[piece_type] - PHASE_VALUES[chess.PAWN] # type: ignore
            mg_piece_value = eg_piece_value = PIECE_VALUES[move.promotion] - PIECE_VALUES[chess.PAWN] # type: ignore
            mg_piece_value += MIDDLEGAME_BONUS[piece_type][index] # type: ignore
            eg_piece_value += ENDGAME_BONUS[piece_type][index] # type: ignore

            dSmg += mg_piece_value
            dSeg += eg_piece_value

        if is_en_passant:
            
            if self.turn is chess.WHITE:
                index = move.destination.south(1).index() # type: ignore
                self.black_phase -= PHASE_VALUES[chess.PAWN]
            else:
                index = MIRROR_BOARD[move.destination.north(1).index()] # type: ignore
                self.white_phase -= PHASE_VALUES[chess.PAWN]
            
            mg_piece_value = eg_piece_value = PIECE_VALUES[chess.PAWN]
            mg_piece_value += MIDDLEGAME_BONUS[chess.PAWN][index]
            eg_piece_value += ENDGAME_BONUS[chess.PAWN][index]

            dSmg += mg_piece_value
            dSeg += eg_piece_value
        
        if is_castling:
            piece_type = chess.ROOK
            if turn == chess.WHITE:
                origin_idx = MIRROR_BOARD[move.origin.index()]
                dest_idx = MIRROR_BOARD[move.destination.index()]
            else:
                origin_idx = move.origin.index()
                dest_idx = move.destination.index()

            psqt_old_mg = MIDDLEGAME_BONUS[piece_type][origin_idx]
            psqt_new_mg = MIDDLEGAME_BONUS[piece_type][dest_idx]
            dSmg += (psqt_new_mg - psqt_old_mg)

            psqt_old_eg = ENDGAME_BONUS[piece_type][origin_idx]
            psqt_new_eg = ENDGAME_BONUS[piece_type][dest_idx]
            dSeg += (psqt_new_eg - psqt_old_eg)

        old_castle_self = self.board.castling_rights.any(self.board.turn)
        old_castle_opp = self.board.castling_rights.any(self.board.turn.opposite)

        self.board.apply(move)

        new_castle_self = self.board.castling_rights.any(self.board.turn.opposite)
        new_castle_opp = self.board.castling_rights.any(self.board.turn)

        if old_castle_self and not new_castle_self:
            dSmg -= CASTLE_RIGHTS_BONUS
            dSeg -= CASTLE_RIGHTS_BONUS
        if old_castle_opp and not new_castle_opp:
            dSmg += CASTLE_RIGHTS_BONUS
            dSeg += CASTLE_RIGHTS_BONUS

        self.mg_evaluation = -self.mg_evaluation - dSmg
        self.eg_evaluation = -self.eg_evaluation - dSeg

        return
    
    def undo(self) -> chess.Move | None:
        move = self.board.undo()

        self.mg_evaluation, self.eg_evaluation, self.white_phase, self.black_phase = self.state_stack.pop()
            
        return move
    
    @classmethod
    def from_fen(cls, fen: str) -> EvalBoard:
        n = cls()
        n.board = chess.Board.from_fen(fen)
        n.mg_evaluation = mg_eval(n.board)
        n.eg_evaluation = eg_eval(n.board)
        n.white_phase = get_phase_value(n.board, chess.WHITE)
        n.black_phase = get_phase_value(n.board, chess.BLACK)
        n.state_stack = []
        return n
    
    def copy(self) -> EvalBoard:
        n = EvalBoard()
        n.board = self.board.copy()
        n.mg_evaluation = self.mg_evaluation
        n.eg_evaluation = self.eg_evaluation
        n.white_phase = self.white_phase
        n.black_phase = self.black_phase
        n.state_stack = self.state_stack.copy()
        return n
    
    def pretty(self) -> str:
        return self.board.pretty()
    
    @property
    def fullmove_number(self) -> int:
        return self.board.fullmove_number
    
    @property
    def turn(self) -> chess.Color:
        return self.board.turn
    
    @property
    def castling_rights(self) -> chess.CastlingRights:
        return self.board.castling_rights
    
    @property
    def history(self) -> list[chess.Move]:
        return self.board.history
    
    @property
    def evaluation(self) -> float:
        if self.board in chess.CHECKMATE:
            return -100000.0
        phase = min(24, self.white_phase + self.black_phase)
        mg_pct = phase / 24
        eg_pct = (24 - phase) / 24

        return (self.mg_evaluation * mg_pct) + (self.eg_evaluation * eg_pct)

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
        20, 30, 20,  0,  0, 10, 30, 20
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

# list of things to do
# add back single extensions
# split endgame and middlegame evaluation in board class and make evaluation() function obsolete

TIME_LIMIT = 10
USE_UCI = "--uci" in sys.argv
CASTLE_RIGHTS_BONUS = 10
DELTA = PIECE_VALUES[chess.QUEEN]
INITIAL_EPSILON = 25.0
LMR = 2
MAX_PLY = 64
MINIMUM_MOVE_TIME = 0.2
END = 0
MAX_PREFILL_TIME = max(0.5, MINIMUM_MOVE_TIME)
CAPTURE_EXTENSION = False
SELF_PLAY = True
USE_OPENING = True
USE_GAVIOTA = True
PONDER = False

nodes_searched = 0

transposition_table: dict[int, float] = {}
tt_depth: dict[int, int] = {}
tt_bestmove: dict[int, chess.Move | None] = {}
tt_flags: dict[int, Flag] = {}
tt_expire: dict[int, int] = {}

killer_moves: list[list[None | chess.Move]] = [[None, None] for _ in range(MAX_PLY)]
history: dict[chess.Color, dict[chess.Move, int]] = {
    chess.WHITE: {},
    chess.BLACK: {}
}

if os.path.exists("gaviota_5"):
    try:
        tablebase = gaviota.open_tablebase("gaviota_5/5")
        tablebase.add_directory("gaviota_5/4")
        tablebase.add_directory("gaviota_5/3")
    except OSError:
        ...
else:
    ...
opening_book = polyglot.open_reader("komodo.bin")

def get_input(b: EvalBoard) -> chess.Move:
    move = None
    legal_moves = b.legal_moves()
    while move not in legal_moves:
        try:
            move = chess.Move.from_uci(input("Enter move (e2e4, etc): "))
        except ValueError:
            continue
    return move # type: ignore

def get_best_opening_move(board: EvalBoard) -> chess.Move | None:
    global opening_book

    try:
        chs_board = chs.Board(board.fen())

        best_move = opening_book.weighted_choice(chs_board)

        chess_move = chess.Move.from_uci(best_move.move.uci())

        return chess_move
    
    except IndexError:
        return None

def get_best_tablebase_move(board: EvalBoard) -> tuple[chess.Move, float] | tuple[None, None]:
    global tablebase

    best_move = None
    best_dtm = math.inf
    best_wdl = -math.inf

    for move in board.legal_moves():
        board.apply(move)
        chs_board = chs.Board(board.fen())
        
        try:
            dtm_score = -tablebase.probe_dtm(chs_board)
            wdl_score = -tablebase.probe_wdl(chs_board)
            if wdl_score > best_wdl:
                best_dtm = dtm_score
                best_wdl = wdl_score
                best_move = move
            elif wdl_score == best_wdl and dtm_score < best_dtm:
                best_dtm = dtm_score
                best_wdl = wdl_score
                best_move = move
                    
        except (gaviota.MissingTableError, Exception):
            ...

        board.undo()

    if best_move is not None:
            
        return best_move, 100000.0 - best_dtm

    return None, None

def clean_tt(b: EvalBoard) -> None:
    global transposition_table, tt_depth, tt_flags, tt_bestmove, tt_expire
    min_date = b.fullmove_number - 1

    hashes_to_delete = []

    for b_hash, date in tt_expire.items():
        if date < min_date:
            hashes_to_delete.append(b_hash)

    for b_hash in hashes_to_delete:
        del transposition_table[b_hash]
        del tt_depth[b_hash]
        del tt_flags[b_hash]
        del tt_bestmove[b_hash]
        del tt_expire[b_hash]

def clear_killer() -> None:
    global killer_moves, MAX_PLY

    killer_moves = [[None, None] for _ in range(MAX_PLY)]

def clear_history() -> None:
    global history

    history[chess.WHITE].clear()
    history[chess.BLACK].clear()

def clean_history() -> None:
    global history

    for turn in (chess.WHITE, chess.BLACK):

        for key, value in history[turn].items():

            history[turn][key] = value >> 1

def get_phase_value(b: EvalBoard | chess.Board, color: chess.Color) -> int:
    global PHASE_VALUES
    return sum(
        len(b[(color, piece_type)]) * PHASE_VALUES[piece_type]
        for piece_type in chess.PIECE_TYPES
    )

def mg_eval(b: chess.Board) -> float:
    global PIECE_VALUES, PHASE_VALUES, MIRROR_BOARD, MIDDLEGAME_BONUS, CASTLE_RIGHTS_BONUS
    if b in chess.CHECKMATE:
        return -100000.0
    elif b in chess.DRAW:
        return 0.0
    
    evaluation = 0.0

    white_bitboard = b[chess.WHITE]
    black_bitboard = b[chess.BLACK]

    for square in white_bitboard:
        piece= b[square]
        if piece is None:
            continue
        piece_type = piece.piece_type
        index = MIRROR_BOARD[square.index()]
        psqb = MIDDLEGAME_BONUS[piece_type][index]
        evaluation += PIECE_VALUES[piece_type] + psqb

    for square in black_bitboard:
        piece = b[square]
        if piece is None:
            raise ValueError
        piece_type = piece.piece_type
        index = square.index()
        psqb = MIDDLEGAME_BONUS[piece_type][index]
        evaluation -= PIECE_VALUES[piece_type] + psqb

    if b.castling_rights.any(chess.WHITE):
        evaluation += CASTLE_RIGHTS_BONUS
    if b.castling_rights.any(chess.BLACK):
        evaluation -= CASTLE_RIGHTS_BONUS

    if b.turn == chess.BLACK:
        evaluation = -evaluation

    return evaluation

def eg_eval(b: chess.Board) -> float:
    global PIECE_VALUES, PHASE_VALUES, MIRROR_BOARD, ENDGAME_BONUS, CASTLE_RIGHTS_BONUS
    if b in chess.CHECKMATE:
        return -100000.0
    elif b in chess.DRAW:
        return 0.0
    
    evaluation = 0.0

    white_bitboard = b[chess.WHITE]
    black_bitboard = b[chess.BLACK]

    for square in white_bitboard:
        piece= b[square]
        if piece is None:
            continue
        piece_type = piece.piece_type
        index = MIRROR_BOARD[square.index()]
        psqb = ENDGAME_BONUS[piece_type][index]
        evaluation += PIECE_VALUES[piece_type] + psqb

    for square in black_bitboard:
        piece = b[square]
        if piece is None:
            raise ValueError
        piece_type = piece.piece_type
        index = square.index()
        psqb = ENDGAME_BONUS[piece_type][index]
        evaluation -= PIECE_VALUES[piece_type] + psqb

    if b.castling_rights.any(chess.WHITE):
        evaluation += CASTLE_RIGHTS_BONUS
    if b.castling_rights.any(chess.BLACK):
        evaluation -= CASTLE_RIGHTS_BONUS

    if b.turn == chess.BLACK:
        evaluation = -evaluation

    return evaluation

def evaluate(b: chess.Board) -> float:
    global PIECE_VALUES, PHASE_VALUES, MIRROR_BOARD, ENDGAME_BONUS, MIDDLEGAME_BONUS, CASTLE_RIGHTS_BONUS
    if b in chess.CHECKMATE:
        return -100000.0
    elif b in chess.DRAW:
        return 0.0

    evaluation = 0.0

    white_bitboard = b[chess.WHITE]
    black_bitboard = b[chess.BLACK]

    phase = min(24, get_phase_value(b, chess.WHITE) + get_phase_value(b, chess.BLACK))

    middlegame_percentage = (phase / 24)
    endgame_percentage = ((24 - phase) / 24)

    for square in white_bitboard:
        piece= b[square]
        if piece is None:
            continue
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

    if b.castling_rights.any(chess.WHITE):
        evaluation += CASTLE_RIGHTS_BONUS
    if b.castling_rights.any(chess.BLACK):
        evaluation -= CASTLE_RIGHTS_BONUS

    if b.turn == chess.BLACK:
        evaluation = -evaluation

    return evaluation

def get_pv(b: EvalBoard | chess.Board, move: chess.Move) -> list[str]:
    nb = b.copy()
    pv: list[str] = [move.uci()]
    nb.apply(move)
    b_hash = hash(nb)
    while b_hash in transposition_table:
        bestmove = tt_bestmove[b_hash]
        if bestmove not in nb.legal_moves():
            break
        pv.append(bestmove.uci()) # type: ignore
        nb.apply(bestmove)
        b_hash = hash(nb)
    return pv

def order_moves(b: EvalBoard, ply: int, captures_only: bool = False) -> list[chess.Move]:
    global PIECE_VALUES, CASTLE_BONUS, history, killer_moves, tt_bestmove
    new_moves: list[tuple[chess.Move, float]] = []
    
    b_hash = hash(b)
    tt_move = tt_bestmove.get(b_hash, None)
    
    for move in b.legal_moves():
        is_capture = b.is_capture(move)
        is_promo = move.is_promotion()
        
        if captures_only and not (is_capture or (is_promo and move.promotion == chess.QUEEN) or b.status(chess.CHECK)):
            continue
            
        if move == tt_move:
            value = 1000000.0
            
        elif is_capture:
            if b[move.destination] is None:
                destination_piece_type = chess.PAWN
            else:
                destination_piece_type = b[move.destination].piece_type  # type: ignore
            
            value = 100000.0 + (PIECE_VALUES[destination_piece_type] * 10) - PIECE_VALUES[b[move.origin].piece_type]  # type: ignore
            
        else:
            if ply < len(killer_moves) and move == killer_moves[ply][0]:
                value = 20000.0
            elif ply < len(killer_moves) and move == killer_moves[ply][1]:
                value = 15000.0
            else:
                value = history[b.turn].get(move, 0)
                
        if is_promo:
            value += 90000.0 + PIECE_VALUES[move.promotion]  # type: ignore
            
        if b.is_castling(move):
            value += 1000
            
        new_moves.append((move, value))
        
    new_moves.sort(key=lambda t: t[1], reverse=True)
    return [t[0] for t in new_moves]

def store_killer(move: chess.Move, ply: int) -> None:
    global killer_moves
    if killer_moves[ply][0] != move:
        killer_moves[ply][1] = killer_moves[ply][0]
        killer_moves[ply][0] = move

def store_history(move: chess.Move, depth: int, turn: chess.Color) -> None:
    global history

    history[turn][move] = history[turn].get(move, 0) + (depth * depth)

def store_tt(b: EvalBoard, b_hash: int, move: chess.Move | None, depth: int, score: float, flag: Flag) -> None:
    global transposition_table, tt_depth, tt_bestmove, tt_flags, tt_expire, tt_pos

    transposition_table[b_hash] = score
    tt_depth[b_hash] = depth
    tt_bestmove[b_hash] = move
    tt_flags[b_hash] = flag
    tt_expire[b_hash] = b.fullmove_number

def quiesce(b: EvalBoard, alpha: float, beta: float, ply: int) -> float:
    global transposition_table, tt_depth, tt_bestmove, tt_flags, tt_expire, nodes_searched, DELTA, END

    if time.perf_counter() >= END:
        raise TimeoutError
    
    nodes_searched += 1

    if b.status(chess.CHECKMATE):
        return -100000.0 + ply
    elif b.status(chess.DRAW):
        return 0.0
    
    stand_pat = b.evaluation
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    if stand_pat + DELTA < alpha and not b.status(chess.CHECK):
        if b.turn is chess.WHITE:
            if not (b[(chess.WHITE, chess.PAWN)] & chess.RANK_7):
                return alpha
        else:
            if not (b[(chess.BLACK, chess.PAWN)] & chess.RANK_2):
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
            (b.is_capture(first_move) or
             first_move.is_promotion() and first_move.promotion is chess.QUEEN) and
             first_move in b.legal_moves()):
            b.apply(first_move)
            evaluation = -quiesce(b, -beta, -alpha, ply + 1)
            b.undo()

            if evaluation >= beta:
                tt_score = evaluation
                if 90000.0 < tt_score < math.inf:
                    tt_score += ply
                elif -math.inf < tt_score < -90000.0:
                    tt_score -= ply
                
                if b_hash not in transposition_table or tt_depth[b_hash] <= 0:
                    store_tt(b, b_hash, first_move, 0, tt_score, Flag.LOWER)
                
                return beta
            
            if evaluation > alpha:
                alpha = evaluation
                best_move = first_move
    
    for move in order_moves(b, ply, captures_only = True):
        b.apply(move)
        evaluation = -quiesce(b, -beta, -alpha, ply + 1)
        b.undo()

        if evaluation >= beta:
            tt_score = evaluation
            if 90000.0 < tt_score < math.inf:
                tt_score += ply
            elif -math.inf < tt_score < -90000.0:
                tt_score -= ply
            
            if b_hash not in transposition_table or tt_depth[b_hash] <= 0:
                store_tt(b, b_hash, move, 0, tt_score, Flag.LOWER)

            return beta
            
        if evaluation > alpha:
            alpha = evaluation
            best_move = move
    
    tt_score = alpha
    if 90000.0 < tt_score < math.inf:
        tt_score += ply
    elif -math.inf < tt_score < -90000.0:
        tt_score -= ply

    if b_hash not in transposition_table or tt_depth[b_hash] <= 0:
        if alpha > original_alpha:
            tt_flag = Flag.EXACT
        else:
            tt_flag = Flag.UPPER
        
        store_tt(b, b_hash, best_move, 0, tt_score, tt_flag)

    return alpha

def search_moves(b: EvalBoard, depth: int, alpha: float, beta: float, ply: int = 0) -> float:
    global transposition_table, tt_depth, tt_bestmove, tt_flags, tt_expire, nodes_searched, killer_moves, LMR, CAPTURE_EXTENSION, END
    
    if time.perf_counter() >= END:
        raise TimeoutError

    nodes_searched += 1

    if b.status(chess.CHECKMATE):
        return -100000.0 + ply
    elif b.status(chess.DRAW):
        return 0.0
    
    if (~b[None]).__len__() <= 5:
        chs_board = chs.Board(b.fen())
        wdl = tablebase.get_wdl(chs_board)
        if wdl is not None:
            if wdl == 0:
                return 0.0
            dtm = tablebase.get_dtm(chs_board)
            if dtm is not None:
                if wdl > 0:
                    return 100000.0 - ply - dtm
                else:
                    return -100000.0 + ply + dtm
    
    in_check = b.status(chess.CHECK)
    if in_check and CAPTURE_EXTENSION:
        depth += 1
    
    if depth <= 0:
        return quiesce(b, alpha, beta, ply)
    
    b_hash = hash(b)
    original_alpha = alpha
    first_move = None
    best_move = None
    moves_searched = 0
    ordered_moves = None

    if b_hash in transposition_table and tt_depth[b_hash] >= depth:
        evaluation = transposition_table[b_hash]

        if 90000.0 < evaluation < math.inf:
            evaluation -= ply
        elif -math.inf < evaluation < -90000.0:
            evaluation += ply
        
        flag = tt_flags[b_hash]
        first_move = tt_bestmove[b_hash]

        if flag == Flag.EXACT:
            return evaluation
        elif flag == Flag.LOWER and evaluation >= beta:
            return beta
        elif flag == Flag.UPPER and evaluation <= alpha:
            return alpha

    if not in_check:
        player_phase = min(get_phase_value(b, chess.WHITE), get_phase_value(b, chess.BLACK))
        if player_phase >= 8:
            r = 3
        elif player_phase >= 2:
            r = 2
        else:
            r = 0

        if r != 0 and depth > r:
            b.apply(None)
            null_score = -search_moves(b, depth - 1 - r, -beta, -beta + 1, ply + 1)
            b.undo()
            if null_score >= beta:
                return beta

    if ordered_moves is None:
        ordered_moves = order_moves(b, ply)
        
    for move in ordered_moves:
        moves_searched += 1
        b.apply(move)
        evaluation = None

        can_reduce = (
            moves_searched > 3 and
            depth >= LMR and
            not b.is_capture(move) and
            not move.is_promotion() and
            not in_check
        )

        if can_reduce:
            reduced_depth = max(1, depth - LMR)
            evaluation = -search_moves(b, reduced_depth, -alpha - 1, -alpha, ply + 1)
            if evaluation > alpha:
                evaluation = -search_moves(b, depth - 1, -beta, -alpha, ply + 1)
        else:
            if moves_searched == 1:
                evaluation = -search_moves(b, depth - 1, -beta, -alpha, ply + 1)
            else:
                evaluation = -search_moves(b, depth - 1, -alpha - 1, -alpha, ply + 1)
                if evaluation > alpha and evaluation < beta:
                    evaluation = -search_moves(b, depth - 1, -beta, -alpha, ply + 1)
        
        b.undo()

        if evaluation >= beta:
            tt_score = evaluation
            if 90000.0 < tt_score < math.inf:
                tt_score += ply
            elif -math.inf < tt_score < -90000.0:
                tt_score -= ply
                
            store_tt(b, b_hash, move, depth, tt_score, Flag.LOWER)

            if not b.is_capture(move) and not move.is_promotion():
                store_killer(move, ply)
                store_history(move, depth, b.turn)
            return beta
            
        if evaluation > alpha:
            alpha = evaluation
            best_move = move
    
    tt_score = alpha
    if 90000.0 < tt_score < math.inf:
        tt_score += ply
    elif -math.inf < tt_score < -90000.0:
        tt_score -= ply

    if alpha > original_alpha:
        tt_flag = Flag.EXACT
    else:
        tt_flag = Flag.UPPER

    store_tt(b, b_hash, best_move, depth, tt_score, tt_flag)
    return alpha

def get_best_move(b: EvalBoard, time_limit: float = TIME_LIMIT, max_depth: int = MAX_PLY) -> tuple[chess.Move | None, float | str]:
    global nodes_searched, USE_UCI, killer_moves, USE_OPENING, USE_GAVIOTA, INITIAL_EPSILON, MAX_PREFILL_TIME, END, PONDER
    
    nodes_searched = 0
    start_time = time.perf_counter()
    if not PONDER:
        END = start_time + time_limit
    else:
        END = start_time + 86400

    if USE_OPENING:
        opening_move = get_best_opening_move(b)
        if opening_move is not None:
            evaluation = 0.0
            clean_tt(b)
            clean_history()
            END = start_time + min(time_limit / 10, MAX_PREFILL_TIME)
            try:
                for depth in range(MAX_PLY):
                    new_b = b.copy()
                    evaluation = search_moves(new_b, depth, -150000.0, 150000.0)
                    if not USE_UCI:
                        print(f"Depth: {depth} (prefill)    ", end = '\r')
            except TimeoutError:
                ...
            if USE_UCI:
                elapsed = time.perf_counter() - start_time
                elapsed_ms = max(1, int(elapsed * 1000))
                print(f"info depth 0 score {evaluation} nodes 0 nps 0 time {elapsed_ms} pv {opening_move.uci()}", flush=True)
            return (opening_move, evaluation)

    if USE_GAVIOTA:
        piece_count = (~b[None]).__len__()
        if piece_count <= 5:
            gaviota_move, score = get_best_tablebase_move(b)
            if gaviota_move is not None and score is not None:
                if -1 < score < 1:
                    score_str = "cp 0.0"
                else:
                    plies_to_mate = 100000.0 - abs(score)
                    moves_to_mate = math.ceil(plies_to_mate / 2)
                    if USE_UCI:
                        score_str = f"mate {int(moves_to_mate) if b.turn is chess.WHITE else -int(moves_to_mate)}"
                        elapsed = time.perf_counter() - start_time
                        elapsed_ms = max(1, int(elapsed * 1000))
                        print(f"info depth 0 score {score_str} nodes 0 nps 0 time {elapsed_ms} pv {gaviota_move.uci()}", flush=True)
                    else:
                        prefix = "-" if b.turn is chess.WHITE else ""
                        score_str = f"{prefix}M{abs(moves_to_mate)}"
                return (gaviota_move, score_str)
    
    clean_tt(b)
    clear_history()

    best_move = None
    best_eval = -150000.0

    epsilon = INITIAL_EPSILON

    try:
        for depth in range(1, max_depth + 1):

            b_check = b.copy()

            if depth == 1:
                alpha = -150000.0
                beta = 150000.0
            else:
                epsilon = INITIAL_EPSILON
                alpha = best_eval - epsilon
                beta = best_eval + epsilon

            while True:
                cur_best_move = None
                cur_best_eval = -150000.0
                current_alpha = alpha

                legal_moves = order_moves(b, 0)
                if not legal_moves:
                    break
                    
                if best_move is not None and best_move in legal_moves:
                    legal_moves.remove(best_move)
                    legal_moves.insert(0, best_move)

                clear_killer()

                for move in legal_moves:
                    b_check.apply(move)
                    evaluation = -search_moves(b_check, depth - 1, -beta, -current_alpha, 1)
                    b_check.undo()

                    if evaluation > cur_best_eval:
                        cur_best_eval = evaluation
                        cur_best_move = move
                    
                    if cur_best_eval > current_alpha:
                        current_alpha = cur_best_eval

                    if cur_best_eval >= beta:
                        break

                if cur_best_eval <= alpha:
                    alpha = max(-150000.0, alpha - epsilon)
                    epsilon *= 2
                    continue

                elif cur_best_eval >= beta:
                    beta = min(150000.0, beta + epsilon)
                    epsilon *= 2
                    continue

                best_move = cur_best_move
                best_eval = cur_best_eval
                break

            elapsed = time.perf_counter() - start_time
            elapsed_ms = max(1, int(elapsed * 1000))
            nps = int(nodes_searched / elapsed) if elapsed > 0 else 0
            
            if abs(best_eval) > 90000.0:
                plies_to_mate = 100000.0 - abs(best_eval)
                moves_to_mate = math.ceil(plies_to_mate / 2)
                score_str = f"mate {int(moves_to_mate) if best_eval > 0 else -int(moves_to_mate)}"
            else:
                score_str = f"cp {int(best_eval)}"

            if best_move is not None:
                pv = get_pv(b, best_move)
            else:
                raise ValueError
            
            if USE_UCI:
                print(f"info depth {depth} score {score_str} nodes {nodes_searched} nps {nps} time {elapsed_ms} pv {" ".join(pv)}", flush=True)
            else:
                print(f"Depth: {depth} ({nps}nps)       ", end = "\r")

            if abs(best_eval) > 90000.0:
                break

    except KeyboardInterrupt:
        raise
    except TimeoutError:
        ...

    if abs(best_eval) > 90000.0:
        plies_to_mate = 100000.0 - abs(best_eval)
        moves_to_mate = math.ceil(plies_to_mate / 2)
        prefix = "-" if best_eval < 0 else ""
        return (best_move, f"{prefix}M{moves_to_mate}")

    return (best_move, best_eval)

def main() -> None:
    global nodes_searched
    board = EvalBoard()

    print(board.pretty())

    while not board.status(chess.CHECKMATE) and not board.status(chess.DRAW):
        if not SELF_PLAY:
            best_move = get_input(board)
            board.apply(best_move)
            print(board.pretty())
        s = time.perf_counter()
        best_move, evaluation = get_best_move(board, TIME_LIMIT)
        time.sleep(max(0, min(TIME_LIMIT - (time.perf_counter() - s), MINIMUM_MOVE_TIME)))
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