from main import *
import bulletchess.utils as utils
import json
import tqdm

def test_position(fen: str, moves: list[chess.Move | None], depth: int) -> bool:
    board = EvalBoard.from_fen(fen)
    for move in moves:
        best_move = get_best_move(board, time_limit=10, max_depth=depth, print_info=False)[0]
        if move != best_move:
            return False
        board.apply(move, None, None, None)
    return True

def test_testcases(fp: str) -> None:
    with open(fp, "r") as f:
        tests: dict[str, list] = json.load(f)
    
    for fen, m in tqdm.tqdm(tests.items()):
        moves: list[str] = m[0]
        depth: int = m[1]
        chess_moves = [chess.Move.from_uci(move) for move in moves]
        if not test_position(fen, chess_moves, depth):
            raise ValueError(f"Position {fen} failed!")

def test_apply_undo(tests: int) -> None:
    for _ in tqdm.tqdm(range(tests)):
        test_position = EvalBoard()
        initial_eval = test_position.evaluation
        while not test_position.is_game_over:
            test_position.apply(utils.random_legal_move(test_position.board), None, None, None)
        while test_position.history:
            test_position.undo()
        if test_position.evaluation != initial_eval:
            raise ValueError("Mismatch with applying/undoing!")

def main() -> None:
    test_testcases("testcases.json")
    test_apply_undo(1_000)

if __name__ == "__main__":
    main()
