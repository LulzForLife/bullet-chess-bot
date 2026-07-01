import math
import sys
import os
import time
from enum import IntEnum, auto
from dataclasses import dataclass

import bulletchess as chess
import chess as chs
import chess.polyglot as polyglot
import chess.gaviota as gaviota

from zobrist import hash_board, POLYGLOT_RANDOM_ARRAY, TYPE_TO_INT

from collections.abc import Generator

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
    __slots__ = ("board", "mg_evaluation", "eg_evaluation", "white_phase", "black_phase", "state_stack", "in_check", "ks_w", "qs_w", "ks_b", "qs_b", "piece_count", "zobrist_hash")

    def __init__(self) -> None:
        self.board = chess.Board()
        self.mg_evaluation = mg_eval(self.board)
        self.eg_evaluation = eg_eval(self.board)
        self.white_phase = get_phase_value(self.board, chess.WHITE)
        self.black_phase = get_phase_value(self.board, chess.BLACK)

        self.in_check = self.board in chess.CHECK

        self.ks_w: bool = self.board.castling_rights.kingside(chess.WHITE)
        self.qs_w: bool = self.board.castling_rights.queenside(chess.WHITE)
        self.ks_b: bool = self.board.castling_rights.kingside(chess.BLACK)
        self.qs_b: bool = self.board.castling_rights.queenside(chess.BLACK)

        self.piece_count = 0
        self.update_piece_count()

        self.zobrist_hash = hash_board(self.board)
        
        self.state_stack = []
    
    def __getitem__(self, key):
        return self.board.__getitem__(key)
    
    def __hash__(self) -> int:
        return self.zobrist_hash
    
    def castling_rights_any(self, turn: chess.Color) -> bool:
        if turn is chess.WHITE:
            return self.ks_w or self.qs_w
        elif turn is chess.BLACK:
            return self.ks_b or self.ks_w
        raise ValueError
    
    def legal_moves(self) -> list[chess.Move]:
        return self.board.legal_moves()
    
    def apply(self, move: chess.Move | None, is_capture: bool | None, is_promo: bool | None, is_castling: bool | None) -> None:
        self.state_stack.append(
            (self.mg_evaluation, self.eg_evaluation, self.white_phase, self.black_phase,
             self.in_check, self.ks_w, self.qs_w, self.ks_b,
             self.qs_b, self.piece_count, self.zobrist_hash)
        )

        poly = POLYGLOT_RANDOM_ARRAY
        self_zobrist_hash = self.zobrist_hash ^ poly[780]

        if move is None:
            self.board.apply(move)
            self.update_status()
            self.mg_evaluation = -self.mg_evaluation
            self.eg_evaluation = -self.eg_evaluation
            self.zobrist_hash = self_zobrist_hash
            return
        
        self_board = self.board

        origin = move.origin
        destination = move.destination
        origin_piece = self_board[origin]
        dest_piece = self_board[destination]
        origin_piece_type = origin_piece.piece_type # type: ignore
        if dest_piece is not None:
            dest_piece_type = dest_piece.piece_type
        else:
            dest_piece_type = None
        
        origin_idx = origin.index()
        dest_idx = destination.index()
        origin_idx_mir = MIRROR_BOARD[origin_idx]
        dest_idx_mir = MIRROR_BOARD[dest_idx]

        self_turn = self.board.turn
        self_turn_is_white = self_turn is chess.WHITE

        ep_square = self_board.en_passant_square
        if ep_square:
            ep_idx = ep_square.index()
        else:
            ep_idx = None
        is_en_passant = ep_square == destination and origin_piece is chess.PAWN # type: ignore

        if is_capture is None:
            is_capture = move.is_capture(self_board)
        if is_promo is None:
            is_promo = move.is_promotion()
        if is_castling is None:
            is_castling = move.is_castling(self.board)
        
        piece_values = PIECE_VALUES
        mg_bonus = MIDDLEGAME_BONUS
        eg_bonus = ENDGAME_BONUS
        type_to_int = TYPE_TO_INT
        phase = PHASE_VALUES

        dSmg = dSeg = 0.0
        
        if self_turn is chess.WHITE:
            psqt_old_mg = mg_bonus[origin_piece_type][origin_idx_mir]
            psqt_new_mg = mg_bonus[origin_piece_type][dest_idx_mir]
            psqt_old_eg = eg_bonus[origin_piece_type][origin_idx_mir]
            psqt_new_eg = eg_bonus[origin_piece_type][dest_idx_mir]
        else:
            psqt_old_mg = mg_bonus[origin_piece_type][origin_idx]
            psqt_new_mg = mg_bonus[origin_piece_type][dest_idx]
            psqt_old_eg = eg_bonus[origin_piece_type][origin_idx]
            psqt_new_eg = eg_bonus[origin_piece_type][dest_idx]

        dSmg += (psqt_new_mg - psqt_old_mg)
        dSeg += (psqt_new_eg - psqt_old_eg)

        pivot = int(self_turn_is_white)
        enemy_pivot = 1 - pivot
        piece_index = type_to_int[origin_piece_type] * 2 + pivot

        self_zobrist_hash ^= poly[64 * piece_index + origin_idx]
        if not is_promo:
            self_zobrist_hash ^= poly[64 * piece_index + dest_idx]

        if is_capture:
            self.piece_count -= 1
            if self_turn_is_white:
                self.black_phase -= phase[dest_piece_type] # type: ignore
            else:
                self.white_phase -= phase[origin_piece_type]

            mg_piece_value = eg_piece_value = piece_values[dest_piece_type] # type: ignore

            if self_turn_is_white:
                mg_piece_value += mg_bonus[dest_piece_type][dest_idx] # type: ignore
                eg_piece_value += eg_bonus[dest_piece_type][dest_idx] # type: ignore
            else:
                mg_piece_value += mg_bonus[dest_piece_type][dest_idx_mir] # type: ignore
                eg_piece_value += eg_bonus[dest_piece_type][dest_idx_mir] # type: ignore

            dSmg += mg_piece_value
            dSeg += eg_piece_value

            captured_index = type_to_int[dest_piece_type] * 2 + enemy_pivot # type: ignore
            self_zobrist_hash ^= poly[64 * captured_index + dest_idx]

        if is_promo:
            piece_type = move.promotion

            if self_turn_is_white:
                self.white_phase += phase[piece_type] - phase[chess.PAWN] # type: ignore
            else:
                self.black_phase += phase[piece_type] - phase[chess.PAWN] # type: ignore

            mg_piece_value = eg_piece_value = piece_values[move.promotion] - piece_values[chess.PAWN] # type: ignore
            
            if self_turn_is_white:
                mg_piece_value += mg_bonus[piece_type][dest_idx] # type: ignore
                eg_piece_value += eg_bonus[piece_type][dest_idx] # type: ignore
            else:
                mg_piece_value += mg_bonus[piece_type][dest_idx_mir] # type: ignore
                eg_piece_value += eg_bonus[piece_type][dest_idx_mir] # type: ignore

            dSmg += mg_piece_value
            dSeg += eg_piece_value

            promo_index = type_to_int[piece_type] * 2 + pivot # type: ignore
            self_zobrist_hash ^= poly[64 * promo_index + dest_idx]

        if is_en_passant:
            self.piece_count -= 1
            if self_turn_is_white:
                self.black_phase -= phase[chess.PAWN]
            else:
                self.white_phase -= phase[chess.PAWN]

            mg_piece_value = eg_piece_value = piece_values[chess.PAWN]

            if self_turn_is_white:
                mg_piece_value += mg_bonus[chess.PAWN][dest_idx - 8]
                eg_piece_value += eg_bonus[chess.PAWN][dest_idx - 8]
            else:
                mg_piece_value += mg_bonus[chess.PAWN][dest_idx_mir - 8]
                eg_piece_value += eg_bonus[chess.PAWN][dest_idx_mir - 8]

            dSmg += mg_piece_value
            dSeg += eg_piece_value

            passant_index = type_to_int[chess.PAWN] * 2 + enemy_pivot
            self_zobrist_hash ^= poly[64 * passant_index + ep_idx] # type: ignore
        
        if is_castling:
            if self_turn_is_white:
                if dest_idx == 6:
                    dSmg += KS_MG
                    dSeg += KS_EG
                    castle_origin_idx = 7
                    castle_dest_idx = 5
                else:
                    dSmg += QS_MG
                    dSeg += QS_EG
                    castle_origin_idx = 0
                    castle_dest_idx = 3
            else:
                if dest_idx == 62:
                    dSmg += KS_MG
                    dSeg += KS_EG
                    castle_origin_idx = 63
                    castle_dest_idx = 61
                else:
                    dSmg += QS_MG
                    dSeg += QS_EG
                    castle_origin_idx = 56
                    castle_dest_idx = 59
            castle_idx = type_to_int[chess.ROOK] * 2 + pivot
            self_zobrist_hash ^= poly[64 * castle_idx + castle_origin_idx]
            self_zobrist_hash ^= poly[64 * castle_idx + castle_dest_idx]

        self_ks_w = self.ks_w
        self_qs_w = self.qs_w
        self_ks_b = self.ks_b
        self_qs_b = self.qs_b

        if self_turn_is_white:
            old_castle_self = self_ks_w or self_qs_w
            old_castle_opp = self_ks_b or self_qs_b
        else:
            old_castle_self = self_ks_w or self_qs_w
            old_castle_opp = self_ks_b or self_qs_b

        self.board.apply(move)
        self.update_status()

        if is_castling or origin_piece_type is chess.KING:
            if self_turn_is_white:
                if self_ks_w:
                    self.ks_w = False
                    self_zobrist_hash ^= poly[768]
                if self_qs_w:
                    self.qs_w = False
                    self_zobrist_hash ^= poly[768 + 1]
            else:
                if self_ks_b:
                    self.ks_b = False
                    self_zobrist_hash ^= poly[768 + 2]
                if self_qs_b:
                    self.qs_b = False
                    self_zobrist_hash ^= poly[768 + 3]
        elif origin_piece_type is chess.ROOK:
            if self_turn_is_white:
                if origin_idx == 0:
                    if self_qs_w:
                        self.qs_w = False
                        self_zobrist_hash ^= poly[768 + 1]
                else:
                    if self_ks_w:
                        self.ks_w = False
                        self_zobrist_hash ^= poly[768]
            else:
                if origin_idx == 56:
                    if self_qs_b:
                        self.qs_b = False
                        self_zobrist_hash ^= poly[768 + 3]
                else:
                    if self_ks_b:
                        self.ks_b = False
                        self_zobrist_hash ^= poly[768 + 2]
        elif dest_piece_type is chess.ROOK and is_capture:
            if self_turn_is_white:
                if dest_idx == 56:
                    if self_qs_b:
                        self.qs_b = False
                        self_zobrist_hash ^= poly[768 + 3]
                else:
                    if self_ks_b:
                        self.ks_b = False
                        self_zobrist_hash ^= poly[768 + 2]
            else:
                if dest_idx == 0:
                    if self_qs_w:
                        self.qs_w = False
                        self_zobrist_hash ^= poly[768 + 1]
                else:
                    if self_ks_w:
                        self.ks_w = False
                        self_zobrist_hash ^= poly[768]

        if self_turn_is_white:
            new_castle_self = self.ks_w or self.qs_w
            new_castle_opp = self.ks_b or self.qs_b
        else:
            new_castle_self = self.ks_w or self.qs_w
            new_castle_opp = self.ks_b or self.qs_b

        if old_castle_self and not new_castle_self:
            dSmg += CASTLE_RIGHTS_BONUS
            dSeg += CASTLE_RIGHTS_BONUS
        if old_castle_opp and not new_castle_opp:
            dSmg -= CASTLE_RIGHTS_BONUS
            dSeg -= CASTLE_RIGHTS_BONUS

        if ep_square:
            file = ep_idx & 7 # type: ignore
            if self_turn_is_white:
                ep_mask = WHITE_EP_MASK[file]
            else:
                ep_mask = BLACK_EP_MASK[file]

            if ep_mask & self_board[(self_turn, chess.PAWN)]:
                self_zobrist_hash ^= poly[772 + file]
        
        new_ep = self_board.en_passant_square
        if new_ep:
            file = dest_idx & 7
            if not self_turn_is_white:
                new_mask = WHITE_EP_MASK[file]
            else:
                new_mask = BLACK_EP_MASK[file]

            if new_mask & self_board[(self_turn.opposite, chess.PAWN)]:
                self_zobrist_hash ^= poly[772 + file]

        self.mg_evaluation = -self.mg_evaluation - dSmg
        self.eg_evaluation = -self.eg_evaluation - dSeg

        self.zobrist_hash = self_zobrist_hash

        return
    
    def undo(self) -> chess.Move | None:
        move = self.board.undo()

        (
            self.mg_evaluation, self.eg_evaluation, self.white_phase, self.black_phase,
            self.in_check, self.ks_w, self.qs_w, self.ks_b,
            self.qs_b, self.piece_count, self.zobrist_hash
        ) = self.state_stack.pop()
            
        return move
    
    def update_status(self) -> None:
        self.in_check = chess.CHECK.__contains__(self.board)
    
    def update_castling_rights(self) -> None:
        self.ks_w = self.board.castling_rights.kingside(chess.WHITE)
        self.qs_w = self.board.castling_rights.queenside(chess.WHITE)
        self.ks_b = self.board.castling_rights.kingside(chess.BLACK)
        self.qs_b = self.board.castling_rights.queenside(chess.BLACK)

    def update_piece_count(self) -> None:
        self.piece_count = (~self.board[None]).__len__()
    
    @classmethod
    def from_fen(cls, fen: str) -> EvalBoard:
        n = cls()
        n.board = chess.Board.from_fen(fen)
        n.mg_evaluation = mg_eval(n.board)
        n.eg_evaluation = eg_eval(n.board)
        n.white_phase = get_phase_value(n.board, chess.WHITE)
        n.black_phase = get_phase_value(n.board, chess.BLACK)
        n.update_status()
        n.update_castling_rights()
        n.update_piece_count()
        n.state_stack = []
        n.update_status()
        n.zobrist_hash = hash_board(n.board)
        return n
    
    def copy(self) -> EvalBoard:
        n = EvalBoard()
        n.board = self.board.copy()
        n.mg_evaluation = self.mg_evaluation
        n.eg_evaluation = self.eg_evaluation
        n.white_phase = self.white_phase
        n.black_phase = self.black_phase
        n.state_stack = self.state_stack.copy()
        n.in_check = self.in_check
        n.ks_w, n.qs_w, n.ks_b, n.qs_b = self.ks_w, self.qs_w, self.ks_b, self.qs_b
        n.piece_count = self.piece_count
        n.zobrist_hash = self.zobrist_hash
        return n
    
    def pretty(self) -> str:
        return self.board.pretty()
    
    def fen(self) -> str:
        return self.board.fen()
    
    @property
    def fullmove_number(self) -> int:
        return self.board.fullmove_number
    
    @property
    def turn(self) -> chess.Color:
        return self.board.turn
    
    @property
    def history(self) -> list[chess.Move]:
        return self.board.history
    
    def is_game_over(self) -> bool:
        self_board = self.board
        return chess.CHECKMATE.__contains__(self_board) or chess.DRAW.__contains__(self_board)
    
    @property
    def evaluation(self) -> float:
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
BLACK_EP_MASK: list[chess.Bitboard] = []
WHITE_EP_MASK: list[chess.Bitboard] = []

TIME_LIMIT = 10
MAX_PLY = 99
MINIMUM_MOVE_TIME = min(0.2, TIME_LIMIT)
MAX_PREFILL_TIME = max(0.5, MINIMUM_MOVE_TIME)
END = 0

USE_UCI = "--uci" in sys.argv
CHECK_EXTENSION = False
SELF_PLAY = True
USE_OPENING = False
USE_GAVIOTA = True
PONDER = False

nodes_searched = 0

tt: dict[int, TTEntry] = {}

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

for pivot, rank in ((0, chess.RANK_6), (1, chess.RANK_3)):
    for n, square in enumerate(rank):
        if pivot == 1:
            ep_mask = square.north(1)
        else:
            ep_mask = square.south(1)

        if n == 0:
            ep_mask = ep_mask.west(1).bb() # type: ignore
        elif n == 7:
            ep_mask = ep_mask.east(1).bb() # type: ignore
        else:
            ep_mask = ep_mask.west(1).bb() | ep_mask.east(1).bb() # type: ignore
        
        if pivot == 1:
            BLACK_EP_MASK.append(ep_mask)
        else:
            WHITE_EP_MASK.append(ep_mask)

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
        board.apply(move, None, None, None)
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
    min_date = b.fullmove_number - 3

    expired = []

    for b_hash, entry in tt.items():
        if entry.age < min_date:
            expired.append(b_hash)

    for b_hash in expired:
        del tt[b_hash]

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
        history[turn] = {key: value >> 1 for key, value in history[turn].items()}

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

def get_pv(b: EvalBoard, move: chess.Move) -> list[str]:
    global tt
    nb = b.copy()
    pv: list[str] = [move.uci()]
    nb.apply(move, None, None, None)
    b_hash = nb.zobrist_hash
    while True:
        if nb.piece_count <= 5 and USE_GAVIOTA:
            bestmove = get_best_tablebase_move(nb)[0]
        elif b_hash in tt:
            bestmove = tt[b_hash].move
        else:
            break
        if bestmove not in nb.legal_moves():
            break
        if nb.is_game_over():
            break
        pv.append(bestmove.uci()) # type: ignore
        nb.apply(bestmove, None, None, None)
        b_hash = nb.zobrist_hash
    return pv

def order_moves(b: EvalBoard, ply: int, captures_only: bool = False) -> Generator[tuple[chess.Move, bool, bool, bool]]:
    tt_entry = tt.get(b.zobrist_hash)
    if tt_entry is not None:
        tt_move = tt_entry.move
    else:
        tt_move = None
    
    b_board = b.board
    
    if tt_move is not None:
        yield (tt_move, tt_move.is_capture(b_board), tt_move.is_promotion(), tt_move.is_castling(b_board))
    
    if b.in_check:
        captures_only = False

    piece_values = PIECE_VALUES
    history_side = history[b.turn]

    board_get = b_board.__getitem__
    not_captures_only = not captures_only

    if ply < MAX_PLY:
        killer0, killer1 = killer_moves[ply]
    else:
        killer0 = killer1 = None
    killer0_exists = killer1_exists = False

    winning: list[tuple[float, chess.Move, bool, bool, bool]] = []
    equal: list[tuple[chess.Move, bool, bool, bool]] = []
    losing: list[tuple[float, chess.Move, bool, bool, bool]] = []
    if not_captures_only:
        quiets: list[tuple[float, chess.Move, bool, bool, bool]] = []

    moves_searched = 0
    for move in b_board.legal_moves():
        moves_searched += 1
        if move == tt_move:
            continue

        if move == killer0:
            killer0_exists = True

        if move == killer1:
            killer1_exists = True

        capture = move.is_capture(b_board)

        if move.is_promotion():
            promo = move.promotion
            if not_captures_only or promo is chess.QUEEN:
                winning.append((piece_values[promo], move, capture, True, False)) # type: ignore
                continue
        elif capture:
            victim = board_get(move.destination)
            victim_type = chess.PAWN if victim is None else victim.piece_type

            attacker_type = board_get(move.origin).piece_type # type: ignore
            score = piece_values[victim_type] * 10 - piece_values[attacker_type]

            if score > 0:
                winning.append((score, move, True, False, False))
            elif score == 0:
                equal.append((move, True, False, False))
            else:
                losing.append((score, move, True, False, False))

            continue
        elif not_captures_only:
            quiets.append((history_side.get(move, 0), move, False, False, move.is_castling(b_board))) # type: ignore
    if moves_searched == 0:
        yield (None, False, False, False) # type: ignore

    winning.sort(key=lambda x: x[0], reverse=True)
    for move in winning:
        yield move[1:]

    for move in equal:
        yield move

    if not_captures_only:

        if killer0_exists and killer0 is not None:
            yield (killer0, killer0.is_capture(b_board), killer0.is_promotion(), killer0.is_castling(b_board))

        if killer1_exists and killer1 is not None:
            yield (killer1, killer1.is_capture(b_board), killer1.is_promotion(), killer1.is_castling(b_board))

        quiets.sort(key=lambda x: x[0], reverse=True) # type: ignore
        for move in quiets: # type: ignore
            yield move[1:]
    
    losing.sort(key=lambda x: x[0], reverse=True)
    for move in losing:
        yield move[1:]

def store_killer(move: chess.Move, ply: int) -> None:
    global killer_moves
    if killer_moves[ply][0] != move:
        killer_moves[ply][1] = killer_moves[ply][0]
        killer_moves[ply][0] = move

def store_history(move: chess.Move, depth: int, turn: chess.Color) -> None:
    global history

    history[turn][move] = history[turn].get(move, 0) + (depth * depth)

def store_tt(b: EvalBoard, b_hash: int, move: chess.Move | None, depth: int, score: float, flag: Flag) -> None:
    global tt
    entry = TTEntry(depth, score, flag, move, b.fullmove_number)
    tt[b_hash] = entry

def quiesce(b: EvalBoard, alpha: float, beta: float, ply: int) -> float:
    global tt, nodes_searched, DELTA, END

    if time.perf_counter() >= END:
        raise TimeoutError
    
    nodes_searched += 1

    in_check = b.in_check
    
    if not in_check:
        stand_pat = b.evaluation
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        if stand_pat + DELTA < alpha and not b.in_check:
            if b.turn is chess.WHITE:
                if not (b[(chess.WHITE, chess.PAWN)] & chess.RANK_7):
                    return alpha
            else:
                if not (b[(chess.BLACK, chess.PAWN)] & chess.RANK_2):
                    return alpha
    
    b_hash = b.zobrist_hash
    entry = tt.get(b_hash)
    in_tt = entry is not None
    original_alpha = alpha
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
    
    for move, is_capture, is_promotion, is_castling in order_moves(b, ply, captures_only = True):
        if move is None:
            if in_check:
                return -100000.0 + ply
            return 0.0
        b.apply(move, is_capture, is_promotion, is_castling)
        evaluation = -quiesce(b, -beta, -alpha, ply + 1)
        b.undo()

        if evaluation >= beta:
            tt_score = evaluation
            if 90000.0 < tt_score < math.inf:
                tt_score += ply
            elif -math.inf < tt_score < -90000.0:
                tt_score -= ply
            
            if not in_tt or entry.depth <= 0: # type: ignore
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

    if not in_tt or entry.depth <= 0: # type: ignore
        if alpha > original_alpha:
            tt_flag = Flag.EXACT
        else:
            tt_flag = Flag.UPPER
        
        store_tt(b, b_hash, best_move, 0, tt_score, tt_flag)

    return alpha

def search_moves(b: EvalBoard, depth: int, alpha: float, beta: float, ply: int = 0, is_singular: bool = False, excluded_move: chess.Move | None = None) -> float:
    global tt, nodes_searched, LMR, CHECK_EXTENSION, END, USE_QUIESCE
    
    if time.perf_counter() >= END:
        raise TimeoutError

    nodes_searched += 1

    if depth <= 0:
        return quiesce(b, alpha, beta, ply)
    
    if b.piece_count <= 5 and USE_GAVIOTA:
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
    
    in_check = b.in_check
    
    b_hash = b.zobrist_hash
    entry = tt.get(b_hash)
    in_tt = entry is not None
    original_alpha = alpha
    best_move = None
    moves_searched = 0

    if in_tt and entry.depth >= depth: # type: ignore
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
    
    extension = 0
    
    if (
        not is_singular
        and depth >= 6 
        and entry is not None 
        and abs(entry.score) < 90000.0
        and (entry.flag is Flag.EXACT or entry.flag is Flag.LOWER)
    ):
        margin = 2 * depth  
        singular_beta = entry.score - margin
        
        singular_depth = (depth - 3) // 2

        score = search_moves(b, singular_depth, singular_beta - 1, singular_beta, ply, True, entry.move)
        
        if score < singular_beta:
            extension = 1

    if not in_check and extension == 0:
        player_phase = min(b.white_phase, b.black_phase)
        if player_phase >= 8:
            r = 3
        elif player_phase >= 2:
            r = 2
        else:
            r = 0

        if r != 0 and depth > r:
            b.apply(None, None, None, None)
            null_score = -search_moves(b, depth - 1 - r, -beta, -beta + 1, ply + 1, False)
            b.undo()
            if null_score >= beta:
                return beta
        
    for move, is_capture, is_promotion, is_castling in order_moves(b, ply):
        if move == excluded_move:
            continue
        if move is None:
            if b.in_check:
                return -100000.0 + ply
            return 0.0
        moves_searched += 1
        b.apply(move, is_capture, is_promotion, is_castling)
        evaluation = None

        can_reduce = (
            extension == 0 and
            not is_singular and
            moves_searched > 3 and
            depth >= LMR and
            not is_capture and
            not is_promotion and
            not in_check
        )

        if can_reduce:
            reduced_depth = max(1, depth - LMR)
            evaluation = -search_moves(b, reduced_depth, -alpha - 1, -alpha, ply + 1, False)
            if evaluation > alpha:
                evaluation = -search_moves(b, depth - 1, -beta, -alpha, ply + 1, False)
        else:
            if moves_searched == 1:
                evaluation = -search_moves(b, depth - 1 + extension, -beta, -alpha, ply + 1, is_singular)
            else:
                evaluation = -search_moves(b, depth - 1 + extension, -alpha - 1, -alpha, ply + 1, is_singular)
                if evaluation > alpha and evaluation < beta:
                    evaluation = -search_moves(b, depth - 1 + extension, -beta, -alpha, ply + 1, is_singular)
        
        b.undo()

        if evaluation >= beta:
            tt_score = evaluation
            if 90000.0 < tt_score < math.inf:
                tt_score += ply
            elif -math.inf < tt_score < -90000.0:
                tt_score -= ply
                
            store_tt(b, b_hash, move, depth, tt_score, Flag.LOWER)

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
    
    existing = tt.get(b_hash)

    move_to_store = best_move
    if move_to_store is None and existing is not None:
        move_to_store = existing.move

    store_tt(b, b_hash, move_to_store, depth, tt_score, tt_flag)
    
    return alpha

def get_best_move(b: EvalBoard, time_limit: float = TIME_LIMIT, max_depth: int = MAX_PLY, *, print_info: bool = True) -> tuple[chess.Move | None, float | str]:
    global nodes_searched, USE_UCI, USE_OPENING, USE_GAVIOTA, INITIAL_EPSILON, MAX_PREFILL_TIME, END, PONDER
    
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
                    if USE_UCI:
                        elapsed = time.perf_counter() - start_time
                        elapsed_ms = max(1, int(elapsed * 1000))
                        nps = int(nodes_searched / elapsed) if elapsed > 0 else 0
                        pv = get_pv(b, opening_move)
                        if print_info:
                            print(f"info depth {depth} score {evaluation} nodes {nodes_searched} nps {nps} time {elapsed_ms} pv {' '.join(pv)}", flush=True)
                    elif not USE_UCI and print_info:
                        print(f"Depth: {depth} (prefill)    ", end = '\r')
            except TimeoutError:
                ...
            return (opening_move, evaluation)

    if b.piece_count <= 5 and USE_GAVIOTA:
        gaviota_move, score = get_best_tablebase_move(b)
        if gaviota_move is not None and score is not None:
            if -1 < score < 1:
                score_str = "cp 0.0"
            else:
                plies_to_mate = 100000.0 - abs(score)
                moves_to_mate = math.ceil(plies_to_mate / 2)
                if USE_UCI:
                    score_str = f"mate {moves_to_mate}"
                    elapsed = time.perf_counter() - start_time
                    elapsed_ms = max(1, int(elapsed * 1000))
                    pv = get_pv(b, gaviota_move)
                    if print_info:
                        print(f"info depth 0 score {score_str} nodes 0 nps 0 time {elapsed_ms} pv {' '.join(pv)}", flush=True)
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

                clear_killer()

                for move, is_capture, is_promotion, is_castling in order_moves(b, 0):
                    b_check.apply(move, is_capture, is_promotion, is_castling)
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
                    if print_info:
                        print(f"info depth {depth} score {score_str} nodes {nodes_searched} nps {nps} time {elapsed_ms} pv {' '.join(pv)}", flush=True)
            else:
                if print_info:
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

    while not (board.board in chess.CHECKMATE or board.board in chess.DRAW):
        if not SELF_PLAY:
            best_move = get_input(board)
            board.apply(best_move, None, None, None)
            print(board.pretty())
        s = time.perf_counter()
        best_move, evaluation = get_best_move(board, TIME_LIMIT)
        time.sleep(max(0, min(TIME_LIMIT - (time.perf_counter() - s), MINIMUM_MOVE_TIME)))
        print()
        if best_move == None:
            break
        board.apply(best_move, None, None, None)
        print(board.pretty())
        print(f"Evaluation: {evaluation}")
        print(f"Nodes searched: {nodes_searched}")

if __name__ == "__main__":
    if not USE_UCI:
        main()
    else:
        import uci
        uci.uci_loop()
