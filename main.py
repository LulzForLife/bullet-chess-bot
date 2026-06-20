import bulletchess as chess
import chess as chs
import chess.polyglot as polyglot
import chess.gaviota as gaviota

import math
import sys
import os
import time
from enum import IntEnum, auto
from dataclasses import dataclass

class Flag(IntEnum):
    EXACT = auto()
    UPPER = auto()
    LOWER = auto()

@dataclass(slots=True)
class TTEntry:
    depth: int
    score: float
    flag: Flag
    move: chess.Move | None
    age: int

class EvalBoard():
    __slots__ = ("board", "mg_evaluation", "eg_evaluation", "white_phase", "black_phase", "state_stack", "in_check", "in_checkmate", "in_draw", "ks_w", "qs_w", "ks_b", "qs_b")

    def __init__(self) -> None:
        self.board = chess.Board()
        self.mg_evaluation = mg_eval(self.board)
        self.eg_evaluation = eg_eval(self.board)
        self.white_phase = get_phase_value(self.board, chess.WHITE)
        self.black_phase = get_phase_value(self.board, chess.BLACK)

        self.in_check = self.board in chess.CHECK
        self.in_checkmate = self.board in chess.CHECKMATE
        self.in_draw = self.board in chess.DRAW

        self.ks_w = self.board.castling_rights.kingside(chess.WHITE)
        self.qs_w = self.board.castling_rights.queenside(chess.WHITE)
        self.ks_b = self.board.castling_rights.kingside(chess.BLACK)
        self.qs_b = self.board.castling_rights.queenside(chess.BLACK)
        
        self.state_stack = []
    
    def __getitem__(self, key):
        return self.board.__getitem__(key)
    
    def __hash__(self) -> int:
        return self.board.__hash__()
    
    def status(self, status: chess.BoardStatus) -> bool:
        if status is chess.CHECK:
            return self.in_check
        elif status is chess.CHECKMATE:
            return self.in_checkmate
        elif status is chess.DRAW:
            return self.in_draw
        raise NotImplementedError
    
    def castling_rights_any(self, turn: chess.Color) -> bool:
        if turn is chess.WHITE:
            return self.ks_w or self.qs_w
        elif turn is chess.BLACK:
            return self.ks_b or self.ks_w
        raise ValueError
    
    def is_capture(self, move: chess.Move) -> bool:
        return move.is_capture(self.board)
    
    def is_castling(self, move: chess.Move) -> bool:
        return move.is_castling(self.board)
    
    def legal_moves(self) -> list[chess.Move]:
        return self.board.legal_moves()
    
    def fen(self) -> str:
        return self.board.fen()
    
    def apply(self, move: chess.Move | None) -> None:
        self.state_stack.append(
            (self.mg_evaluation, self.eg_evaluation, self.white_phase, self.black_phase,
             self.in_check, self.in_checkmate, self.in_draw, self.ks_w,
             self.qs_w, self.ks_b, self.qs_b)
        )

        if move is None:
            self.board.apply(move)
            self.update_status()
            self.mg_evaluation = -self.mg_evaluation
            self.eg_evaluation = -self.eg_evaluation
            return
        
        self_board = self.board

        origin_piece = self_board[move.origin]
        dest_piece = self_board[move.destination]
        origin_piece_type = origin_piece.piece_type # type: ignore
        if dest_piece is not None:
            dest_piece_type = dest_piece.piece_type
        else:
            dest_piece_type = None
        
        origin_idx = move.origin.index()
        dest_idx = move.destination.index()
        origin_idx_mir = MIRROR_BOARD[origin_idx]
        dest_idx_mir = MIRROR_BOARD[dest_idx]

        self_turn = self.turn
        opp_turn = self_turn.opposite

        is_capture = move.is_capture(self_board)
        is_castling = move.is_castling(self_board)
        is_en_passant = self_board.en_passant_square == move.destination and origin_piece is chess.PAWN # type: ignore
        is_promotion = move.is_promotion()

        dSmg = dSeg = 0.0
        
        if self_turn is chess.WHITE:
            psqt_old_mg = MIDDLEGAME_BONUS[origin_piece_type][origin_idx_mir]
            psqt_new_mg = MIDDLEGAME_BONUS[origin_piece_type][dest_idx_mir]
            psqt_old_eg = ENDGAME_BONUS[origin_piece_type][origin_idx_mir]
            psqt_new_eg = ENDGAME_BONUS[origin_piece_type][dest_idx_mir]
        else:
            psqt_old_mg = MIDDLEGAME_BONUS[origin_piece_type][origin_idx]
            psqt_new_mg = MIDDLEGAME_BONUS[origin_piece_type][dest_idx]
            psqt_old_eg = ENDGAME_BONUS[origin_piece_type][origin_idx]
            psqt_new_eg = ENDGAME_BONUS[origin_piece_type][dest_idx]

        dSmg += (psqt_new_mg - psqt_old_mg)
        dSeg += (psqt_new_eg - psqt_old_eg)

        if is_capture:
            mg_piece_value = eg_piece_value = PIECE_VALUES[dest_piece_type] # type: ignore

            if self_turn is chess.WHITE:
                mg_piece_value += MIDDLEGAME_BONUS[dest_piece_type][dest_idx] # type: ignore
                eg_piece_value += ENDGAME_BONUS[dest_piece_type][dest_idx] # type: ignore
            else:
                mg_piece_value += MIDDLEGAME_BONUS[dest_piece_type][dest_idx_mir] # type: ignore
                eg_piece_value += ENDGAME_BONUS[dest_piece_type][dest_idx_mir] # type: ignore

            dSmg += mg_piece_value
            dSeg += eg_piece_value

        if is_promotion:
            piece_type = move.promotion
            mg_piece_value = eg_piece_value = PIECE_VALUES[move.promotion] - PIECE_VALUES[chess.PAWN] # type: ignore
            
            if self_turn is chess.WHITE:
                mg_piece_value += MIDDLEGAME_BONUS[piece_type][dest_idx] # type: ignore
                eg_piece_value += ENDGAME_BONUS[piece_type][dest_idx] # type: ignore
            else:
                mg_piece_value += MIDDLEGAME_BONUS[piece_type][dest_idx_mir] # type: ignore
                eg_piece_value += ENDGAME_BONUS[piece_type][dest_idx_mir] # type: ignore

            dSmg += mg_piece_value
            dSeg += eg_piece_value

        if is_en_passant:            
            mg_piece_value = eg_piece_value = PIECE_VALUES[chess.PAWN]

            if self_turn is chess.WHITE:
                mg_piece_value += MIDDLEGAME_BONUS[chess.PAWN][dest_idx - 8]
                eg_piece_value += ENDGAME_BONUS[chess.PAWN][dest_idx - 8]
            else:
                mg_piece_value += MIDDLEGAME_BONUS[chess.PAWN][dest_idx_mir - 8]
                eg_piece_value += ENDGAME_BONUS[chess.PAWN][dest_idx_mir - 8]

            dSmg += mg_piece_value
            dSeg += eg_piece_value
        
        if is_castling:
            if self_turn is chess.WHITE:
                if dest_idx == 6:
                    dSmg += KS_MG
                    dSeg += KS_EG
                else:
                    dSmg += QS_MG
                    dSeg += QS_EG
            else:
                if dest_idx == 62:
                    dSmg += KS_MG
                    dSeg += KS_EG
                else:
                    dSmg += QS_MG
                    dSeg += QS_EG

        old_castle_self = self.castling_rights_any(self_turn)
        old_castle_opp = self.castling_rights_any(opp_turn)

        self.board.apply(move)
        self.update_status()
        if is_castling or origin_piece_type is chess.KING or origin_piece_type is chess.ROOK or dest_piece_type is chess.ROOK:
            self.update_castling_rights()

        new_castle_self = self.castling_rights_any(self_turn)
        new_castle_opp = self.castling_rights_any(opp_turn)

        if old_castle_self and not new_castle_self:
            dSmg += CASTLE_RIGHTS_BONUS
            dSeg += CASTLE_RIGHTS_BONUS
        if old_castle_opp and not new_castle_opp:
            dSmg -= CASTLE_RIGHTS_BONUS
            dSeg -= CASTLE_RIGHTS_BONUS

        self.mg_evaluation = -self.mg_evaluation - dSmg
        self.eg_evaluation = -self.eg_evaluation - dSeg

        return
    
    def undo(self) -> chess.Move | None:
        move = self.board.undo()

        (
            self.mg_evaluation, self.eg_evaluation, self.white_phase, self.black_phase,
            self.in_check, self.in_checkmate, self.in_draw, self.ks_w,
            self.qs_w, self.ks_b, self.qs_b
        ) = self.state_stack.pop()
            
        return move
    
    def update_status(self) -> None:
        self.in_check = self.board in chess.CHECK
        self.in_checkmate = self.board in chess.CHECKMATE
        self.in_draw = self.board in chess.DRAW
    
    def update_castling_rights(self) -> None:
        self.ks_w = self.board.castling_rights.kingside(chess.WHITE)
        self.qs_w = self.board.castling_rights.queenside(chess.WHITE)
        self.ks_b = self.board.castling_rights.kingside(chess.BLACK)
        self.qs_b = self.board.castling_rights.queenside(chess.BLACK)
    
    @classmethod
    def from_fen(cls, fen: str) -> EvalBoard:
        n = cls()
        n.board = chess.Board.from_fen(fen)
        n.mg_evaluation = mg_eval(n.board)
        n.eg_evaluation = eg_eval(n.board)
        n.white_phase = get_phase_value(n.board, chess.WHITE)
        n.black_phase = get_phase_value(n.board, chess.BLACK)
        n.state_stack = []
        n.update_status()
        return n
    
    def copy(self) -> EvalBoard:
        n = EvalBoard()
        n.board = self.board.copy()
        n.mg_evaluation = self.mg_evaluation
        n.eg_evaluation = self.eg_evaluation
        n.white_phase = self.white_phase
        n.black_phase = self.black_phase
        n.state_stack = self.state_stack.copy()
        n.in_check, n.in_checkmate, n.in_draw = self.in_check, self.in_checkmate, self.in_draw
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
    def history(self) -> list[chess.Move]:
        return self.board.history
    
    @property
    def evaluation(self) -> float:
        if self.in_checkmate:
            return -100000.0
        elif self.in_draw:
            return 0.0
        phase = min(24, self.white_phase + self.black_phase)
        mg_pct = phase / 24
        eg_pct = (24 - phase) / 24

        return (self.mg_evaluation * mg_pct) + (self.eg_evaluation * eg_pct)

PIECE_VALUES = {
    chess.KING: 60000,
    chess.QUEEN: 900,
    chess.ROOK: 490,
    chess.BISHOP: 320,
    chess.KNIGHT: 290,
    chess.PAWN: 100
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

CASTLE_RIGHTS_BONUS = 10
DELTA = PIECE_VALUES[chess.QUEEN]
INITIAL_EPSILON = 25.0
LMR = 2

KS_MG = MIDDLEGAME_BONUS[chess.ROOK][chess.F8.index()] - MIDDLEGAME_BONUS[chess.ROOK][chess.H8.index()]
KS_EG = ENDGAME_BONUS[chess.ROOK][chess.F8.index()] - ENDGAME_BONUS[chess.ROOK][chess.H8.index()]
QS_MG = MIDDLEGAME_BONUS[chess.ROOK][chess.D8.index()] - MIDDLEGAME_BONUS[chess.ROOK][chess.A8.index()]
QS_EG = ENDGAME_BONUS[chess.ROOK][chess.D8.index()] - ENDGAME_BONUS[chess.ROOK][chess.A8.index()]

TIME_LIMIT = 10
MAX_PLY = 64
MINIMUM_MOVE_TIME = min(0.2, TIME_LIMIT)
MAX_PREFILL_TIME = max(0.5, MINIMUM_MOVE_TIME)
END = 0

USE_UCI = "--uci" in sys.argv
CHECK_EXTENSION = False
SELF_PLAY = True
USE_OPENING = True
USE_GAVIOTA = True
PONDER = False

nodes_searched = 0

tt: dict[str, TTEntry] = {}

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
        USE_GAVIOTA = False
else:
    USE_GAVIOTA = False
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
    global tt
    min_date = b.fullmove_number - 1

    expired = []

    for b_fen, entry in tt.items():
        if entry.age < min_date:
            expired.append(b_fen)

    for b_fen in expired:
        del tt[b_fen]

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

    if b.turn == chess.BLACK:
        evaluation = -evaluation
    
    if b.castling_rights.any(chess.WHITE):
        evaluation += CASTLE_RIGHTS_BONUS
    if b.castling_rights.any(chess.BLACK):
        evaluation -= CASTLE_RIGHTS_BONUS

    return evaluation

def get_pv(b: EvalBoard | chess.Board, move: chess.Move) -> list[str]:
    global tt
    nb = b.copy()
    pv: list[str] = [move.uci()]
    nb.apply(move)
    b_fen = nb.fen()
    while b_fen in tt:
        bestmove = tt[b_fen].move
        if bestmove not in nb.legal_moves():
            break
        pv.append(bestmove.uci()) # type: ignore
        nb.apply(bestmove)
        b_fen = nb.fen()
    return pv

def order_moves(b: EvalBoard, ply: int, captures_only: bool = False) -> list[chess.Move]:
    piece_values = PIECE_VALUES
    history_side = history[b.turn]
    legal_moves = b.legal_moves

    is_capture = b.is_capture
    is_castling = b.is_castling
    status = b.status
    board_get = b.board.__getitem__

    killer0, killer1 = killer_moves[ply]

    tt_entry = tt.get(b.fen())
    if tt_entry is not None:
        tt_move = tt_entry.move
    else:
        tt_move = None

    winning: list[tuple[chess.Move, float]] = []
    equal: list[chess.Move] = []
    losing: list[tuple[chess.Move, float]] = []
    quiets: list[tuple[chess.Move, float]] = []
    castling: list[chess.Move] = []

    killer0_exists = False
    killer1_exists = False

    in_check = status(chess.CHECK)

    for move in legal_moves():
        if move == tt_move:
            continue

        capture = is_capture(move)
        promo = move.is_promotion()

        if captures_only and not (
            capture or
            (promo and move.promotion == chess.QUEEN) or
            in_check
        ):
            continue

        if promo:
            winning.append((move, piece_values[move.promotion])) # type: ignore
            continue

        if capture:
            victim = board_get(move.destination)
            victim_type = chess.PAWN if victim is None else victim.piece_type

            attacker_type = board_get(move.origin).piece_type # type: ignore
            score = piece_values[victim_type] - piece_values[attacker_type]

            if score > 0:
                winning.append((move, score))
            elif score == 0:
                equal.append(move)
            else:
                losing.append((move, score))

            continue

        if move == killer0:
            killer0_exists = True
            continue

        if move == killer1:
            killer1_exists = True
            continue

        if is_castling(move):
            castling.append(move)
        else:
            quiets.append((move, history_side.get(move, 0)))

    winning.sort(key=lambda x: x[1], reverse=True)
    losing.sort(key=lambda x: x[1], reverse=True)
    quiets.sort(key=lambda x: x[1], reverse=True)

    return (
        ([tt_move] if tt_move is not None else []) +
        [m for m, _ in winning] +
        equal +
        ([killer0] if killer0_exists else []) +
        ([killer1] if killer1_exists else []) +
        [m for m, _ in losing] +
        castling +
        [m for m, _ in quiets]
    ) # type: ignore

def store_killer(move: chess.Move, ply: int) -> None:
    global killer_moves
    if killer_moves[ply][0] != move:
        killer_moves[ply][1] = killer_moves[ply][0]
        killer_moves[ply][0] = move

def store_history(move: chess.Move, depth: int, turn: chess.Color) -> None:
    global history

    history[turn][move] = history[turn].get(move, 0) + (depth * depth)

def store_tt(b: EvalBoard, b_fen: str, move: chess.Move | None, depth: int, score: float, flag: Flag) -> None:
    global tt
    entry = TTEntry(depth, score, flag, move, b.fullmove_number)
    tt[b_fen] = entry

def quiesce(b: EvalBoard, alpha: float, beta: float, ply: int) -> float:
    global tt, nodes_searched, DELTA, END

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
    
    b_fen = b.fen()
    entry = tt.get(b_fen)
    in_tt = b_fen in tt
    original_alpha = alpha
    first_move = None
    best_move = None

    if in_tt:
        score = entry.score # type: ignore

        if 90000.0 < score < math.inf:
            score -= ply
        elif -math.inf < score < -90000.0:
            score += ply
        
        flag = entry.flag # type: ignore
        if flag == Flag.EXACT:
            return score
        elif flag == Flag.LOWER and score >= beta:
            return beta
        elif flag == Flag.UPPER and score <= alpha:
            return alpha
            
        first_move = entry.move # type: ignore
        
        if (first_move is not None and
            (b.is_capture(first_move) or
             first_move.is_promotion() and first_move.promotion is chess.QUEEN)):
            b.apply(first_move)
            evaluation = -quiesce(b, -beta, -alpha, ply + 1)
            b.undo()

            if evaluation >= beta:
                tt_score = evaluation
                if 90000.0 < tt_score < math.inf:
                    tt_score += ply
                elif -math.inf < tt_score < -90000.0:
                    tt_score -= ply
                
                if entry.depth <= 0: # type: ignore
                    store_tt(b, b_fen, first_move, 0, tt_score, Flag.LOWER)
                
                return beta
            
            if evaluation > alpha:
                alpha = evaluation
                best_move = first_move
    
    for move in order_moves(b, ply, captures_only = True):
        try:
            b.apply(move)
        except Exception:
            print(b.pretty())
            print(move)
            raise
        evaluation = -quiesce(b, -beta, -alpha, ply + 1)
        b.undo()

        if evaluation >= beta:
            tt_score = evaluation
            if 90000.0 < tt_score < math.inf:
                tt_score += ply
            elif -math.inf < tt_score < -90000.0:
                tt_score -= ply
            
            if not in_tt or entry.depth <= 0: # type: ignore
                store_tt(b, b_fen, move, 0, tt_score, Flag.LOWER)

            return beta
            
        if evaluation > alpha:
            alpha = evaluation
            best_move = move
    
    tt_score = alpha
    if 90000.0 < tt_score < math.inf:
        tt_score += ply
    elif -math.inf < tt_score < -90000.0:
        tt_score -= ply

    if not in_tt or entry.depth <= 0: # type: ignore
        if alpha > original_alpha:
            tt_flag = Flag.EXACT
        else:
            tt_flag = Flag.UPPER
        
        store_tt(b, b_fen, best_move, 0, tt_score, tt_flag)

    return alpha

def search_moves(b: EvalBoard, depth: int, alpha: float, beta: float, ply: int = 0) -> float:
    global tt, nodes_searched, killer_moves, LMR, CHECK_EXTENSION, END, USE_QUIESCE
    
    if time.perf_counter() >= END:
        raise TimeoutError

    nodes_searched += 1

    if b.status(chess.CHECKMATE):
        return -100000.0 + ply
    elif b.status(chess.DRAW):
        return 0.0
    
    if (~b[None]).__len__() <= 5 and USE_GAVIOTA:
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
    
    if depth <= 0:
        return quiesce(b, alpha, beta, ply)
    
    b_fen = b.fen()
    entry = tt.get(b_fen)
    original_alpha = alpha
    best_move = None
    moves_searched = 0

    if b_fen in tt and entry.depth >= depth: # type: ignore
        evaluation = entry.score # type: ignore

        if 90000.0 < evaluation < math.inf:
            evaluation -= ply
        elif -math.inf < evaluation < -90000.0:
            evaluation += ply
        
        flag = entry.flag # type: ignore

        if flag == Flag.EXACT:
            return evaluation
        elif flag == Flag.LOWER and evaluation >= beta:
            return beta
        elif flag == Flag.UPPER and evaluation <= alpha:
            return alpha

    if not in_check:
        player_phase = min(b.white_phase, b.black_phase)
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
        
    for move in order_moves(b, ply):
        moves_searched += 1
        b.apply(move)
        evaluation = None

        is_capture = b.is_capture(move)
        is_promotion = move.is_promotion()
        can_reduce = (
            moves_searched > 3 and
            depth >= LMR and
            not is_capture and
            not is_promotion and
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
                
            store_tt(b, b_fen, move, depth, tt_score, Flag.LOWER)

            if not is_capture and not is_promotion:
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

    store_tt(b, b_fen, best_move, depth, tt_score, tt_flag)
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
            
            if USE_UCI:
                if best_move is not None:
                    pv = get_pv(b, best_move)
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
